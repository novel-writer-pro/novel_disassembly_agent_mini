"""Domain dictionary: auto-build tokenization dictionary from analysis results.

Collects entity names, event labels, and other domain-specific terms from
completed chapter analyses to improve BM25 tokenization and keyword matching.

Two output files are maintained side-by-side in ``runtime_cache_dir``:

- ``domain-dict.txt``: plain term list (one term per line).
- ``jieba-user-dict.txt``: ``<term> <freq> <pos>`` per line, consumable by
  ``jieba.load_userdict`` and ``pg_jieba`` userdict loaders.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import FactRecord, GraphNode

# jieba userdict freq must exceed the built-in dictionary's top frequencies so
# multi-char domain terms stay glued during tokenization (empirical floor ~50).
_JIEBA_DEFAULT_FREQ = 100
_JIEBA_DEFAULT_POS = "n"

# A proper-noun term must fit in this length budget. Long inputs (e.g. fact
# narrative summaries) being added as a single jieba userdict line collapses an
# entire sentence into one token, which DESTROYS BM25 recall — the inverse of
# the intended effect.
_TERM_MIN_LEN = 2
_TERM_MAX_LEN = 12  # 12 chars covers nearly all proper nouns + short titles

# Reject any term containing characters that strongly indicate it is a
# sentence/paragraph rather than a noun phrase.
_TERM_REJECT_CHARS = frozenset(
    "，。、；：！？“”‘’（）《》〈〉【】「」『』·…—— "
    ",.;:!?\"'()<>[]{}|\\/\t\n\r"
)


def _is_valid_term(term: str) -> bool:
    """True iff term is shaped like a proper-noun (short, no sentence punctuation)."""
    if not term:
        return False
    if len(term) < _TERM_MIN_LEN or len(term) > _TERM_MAX_LEN:
        return False
    for ch in term:
        if ch in _TERM_REJECT_CHARS:
            return False
    return True


class DomainDictionaryService:
    """Builds and maintains a domain-specific dictionary from analysis results."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def _dict_path(self) -> Path:
        return Path(self.settings.runtime_cache_dir) / "domain-dict.txt"

    def _jieba_dict_path(self) -> Path:
        return Path(self.settings.runtime_cache_dir) / "jieba-user-dict.txt"

    def _load_existing(self) -> set[str]:
        """Return existing valid terms; silently drops sentence-like noise on read."""
        path = self._dict_path()
        if not path.exists():
            return set()
        return {
            line.strip()
            for line in path.read_text(encoding='utf-8').splitlines()
            if _is_valid_term(line.strip())
        }

    def update_from_branch(self, branch_id: str) -> int:
        """Rebuild dictionary from all entities and labels in a branch."""
        existing = self._load_existing()

        entity_labels = self.session.scalars(
            select(GraphNode.label)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.node_type.in_(['entity', 'character']))
        ).all()

        fact_labels = self.session.scalars(
            select(FactRecord.label)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.fact_type.in_(['entity', 'event', 'foreshadowing']))
        ).all()

        new_terms: set[str] = set()
        for label in entity_labels + fact_labels:
            term = str(label).strip()
            if not _is_valid_term(term) or term in existing:
                continue
            new_terms.add(term)
            for sub in self._extract_sub_terms(term):
                if _is_valid_term(sub) and sub not in existing:
                    new_terms.add(sub)

        if not new_terms:
            return 0

        all_terms = sorted(existing | new_terms)
        self._persist(all_terms)
        return len(new_terms)

    def update_from_chapter(
        self,
        branch_id: str,
        chapter_index: int,
    ) -> int:
        """Incrementally add terms from a single chapter's analysis."""
        existing = self._load_existing()

        facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
        ).all()

        new_terms: set[str] = set()
        for fact in facts:
            term = fact.label.strip()
            if not _is_valid_term(term) or term in existing:
                continue
            new_terms.add(term)
            for sub in self._extract_sub_terms(term):
                if _is_valid_term(sub) and sub not in existing:
                    new_terms.add(sub)

        if not new_terms:
            return 0

        all_terms = sorted(existing | new_terms)
        self._persist(all_terms)
        return len(new_terms)

    def get_terms(self) -> list[str]:
        """Return all domain dictionary terms."""
        return sorted(self._load_existing())

    def _persist(self, all_terms: list[str]) -> None:
        valid_terms = sorted(t for t in all_terms if _is_valid_term(t))

        plain = self._dict_path()
        plain.parent.mkdir(parents=True, exist_ok=True)
        plain.write_text('\n'.join(valid_terms) + '\n', encoding='utf-8')

        jieba = self._jieba_dict_path()
        lines = [
            f"{term} {_JIEBA_DEFAULT_FREQ} {_JIEBA_DEFAULT_POS}"
            for term in valid_terms
        ]
        jieba.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    @staticmethod
    def _extract_sub_terms(term: str) -> list[str]:
        """Extract meaningful sub-terms from a compound label."""
        results: list[str] = []
        chars = [c for c in term if '\u4e00' <= c <= '\u9fff']
        if 4 <= len(chars) <= 8:
            results.append(''.join(chars[:2]))
            results.append(''.join(chars[-2:]))
        return [r for r in results if len(r) >= 2]
