"""Domain dictionary: auto-build tokenization dictionary from analysis results.

Collects entity names, event labels, and other domain-specific terms from
completed chapter analyses to improve BM25 tokenization and keyword matching.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import FactRecord, GraphNode


class DomainDictionaryService:
    """Builds and maintains a domain-specific dictionary from analysis results."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def _dict_path(self) -> Path:
        return Path(self.settings.runtime_cache_dir) / "domain-dict.txt"

    def _load_existing(self) -> set[str]:
        path = self._dict_path()
        if not path.exists():
            return set()
        return {
            line.strip()
            for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip() and len(line.strip()) >= 2
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
            if len(term) >= 2 and term not in existing:
                new_terms.add(term)
                sub_terms = self._extract_sub_terms(term)
                for sub in sub_terms:
                    if sub not in existing:
                        new_terms.add(sub)

        if not new_terms:
            return 0

        all_terms = sorted(existing | new_terms)
        path = self._dict_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(all_terms) + '\n', encoding='utf-8')
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
            if len(term) >= 2 and term not in existing:
                new_terms.add(term)
                for sub in self._extract_sub_terms(term):
                    if sub not in existing:
                        new_terms.add(sub)

        if not new_terms:
            return 0

        all_terms = sorted(existing | new_terms)
        path = self._dict_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(all_terms) + '\n', encoding='utf-8')
        return len(new_terms)

    def get_terms(self) -> list[str]:
        """Return all domain dictionary terms."""
        return sorted(self._load_existing())

    @staticmethod
    def _extract_sub_terms(term: str) -> list[str]:
        """Extract meaningful sub-terms from a compound label."""
        results: list[str] = []
        chars = [c for c in term if '\u4e00' <= c <= '\u9fff']
        if 4 <= len(chars) <= 8:
            results.append(''.join(chars[:2]))
            results.append(''.join(chars[-2:]))
        return [r for r in results if len(r) >= 2]
