"""Local steering library loader for trope/worldview/audience dossiers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, TypedDict




class SteeringDocSummary(TypedDict):
    slug: str
    labels: list[str]
    summary: str
    worldview_capsule: list[str]
    trope_axes: list[str]
    innovation_directives: list[str]
    taboo_innovations: list[str]
    external_knowledge_refs: list[str]


class SteeringPack(TypedDict):
    worldview_capsule: list[str]
    trope_axes: list[str]
    innovation_directives: list[str]
    taboo_innovations: list[str]
    external_knowledge_refs: list[str]


SteeringHitReasons: TypeAlias = dict[str, dict[str, list[str]]]
SteeringDocSummaryBuckets: TypeAlias = dict[str, list[SteeringDocSummary]]


class SteeringRetrievalMeta(TypedDict):
    query_text: str
    selected_trope_docs: list[str]
    selected_worldview_docs: list[str]
    selected_audience_docs: list[str]
    hit_reasons: SteeringHitReasons
    selected_doc_summaries: SteeringDocSummaryBuckets


class SteeringRetrievalPayload(TypedDict):
    steering_pack: SteeringPack
    retrieval_meta: SteeringRetrievalMeta


@dataclass(frozen=True, slots=True)
class SteeringLibraryDoc:
    """Normalized steering library doc slices."""

    slug: str
    worldview_capsule: list[str]
    trope_axes: list[str]
    innovation_directives: list[str]
    taboo_innovations: list[str]
    external_knowledge_refs: list[str]
    labels: list[str]

    def compact_summary(self) -> SteeringDocSummary:
        """Return a retrieval-facing summary payload for experiment outputs."""

        summary_parts: list[str] = []
        if self.labels:
            summary_parts.append(f"标签：{' / '.join(self.labels[:2])}")
        if self.worldview_capsule:
            summary_parts.append(f"世界观：{self.worldview_capsule[0]}")
        if self.trope_axes:
            summary_parts.append(f"套路轴：{self.trope_axes[0]}")
        if self.innovation_directives:
            summary_parts.append(f"创新导向：{self.innovation_directives[0]}")
        if self.external_knowledge_refs:
            summary_parts.append(f"读者/应用提示：{self.external_knowledge_refs[0]}")
        summary = "；".join(part for part in summary_parts if part) or f"参考文档：{self.slug}"
        return {
            "slug": self.slug,
            "labels": self.labels,
            "summary": summary,
            "worldview_capsule": self.worldview_capsule[:2],
            "trope_axes": self.trope_axes[:2],
            "innovation_directives": self.innovation_directives[:2],
            "taboo_innovations": self.taboo_innovations[:2],
            "external_knowledge_refs": self.external_knowledge_refs[:2],
        }


class SteeringLibraryService:
    """Load markdown-first steering docs from local rag/ directories."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path("rag")

    @staticmethod
    def _section_items(text: str, section_name: str) -> list[str]:
        lines = text.splitlines()
        capture = False
        items: list[str] = []
        target = f"## {section_name}".strip().lower()
        for raw in lines:
            line = raw.strip()
            lowered = line.lower()
            if lowered == target:
                capture = True
                continue
            if capture and line.startswith("## "):
                break
            if capture and line.startswith("- "):
                item = line[2:].strip()
                if item:
                    items.append(item)
        return items

    def _load_doc(self, directory: str, slug: str) -> SteeringLibraryDoc:
        path = self.root / directory / f"{slug}.md"
        text = path.read_text(encoding="utf-8")
        return SteeringLibraryDoc(
            slug=slug,
            worldview_capsule=self._section_items(text, "worldview_capsule"),
            trope_axes=self._section_items(text, "trope_axes"),
            innovation_directives=self._section_items(text, "innovation_directives"),
            taboo_innovations=self._section_items(text, "taboo_innovations"),
            external_knowledge_refs=(
                self._section_items(text, "audience_expectation_notes")
                + self._section_items(text, "reader_expectations")
                + self._section_items(text, "useful_for_imitation")
            ),
            labels=self._section_items(text, "label"),
        )

    @staticmethod
    def _merge_unique(base: list[str], extra: list[str]) -> list[str]:
        seen = {item for item in base if item.strip()}
        merged = [item for item in base if item.strip()]
        for item in extra:
            if item.strip() and item not in seen:
                seen.add(item)
                merged.append(item)
        return merged

    def assemble_pack(
        self,
        *,
        trope_docs: list[str] | None = None,
        worldview_docs: list[str] | None = None,
        audience_docs: list[str] | None = None,
    ) -> SteeringPack:
        pack: SteeringPack = {
            "worldview_capsule": [],
            "trope_axes": [],
            "innovation_directives": [],
            "taboo_innovations": [],
            "external_knowledge_refs": [],
        }
        for slug in trope_docs or []:
            doc = self._load_doc("trope-library", slug)
            pack["worldview_capsule"] = self._merge_unique(pack["worldview_capsule"], doc.worldview_capsule)
            pack["trope_axes"] = self._merge_unique(pack["trope_axes"], doc.trope_axes)
            pack["innovation_directives"] = self._merge_unique(pack["innovation_directives"], doc.innovation_directives)
            pack["taboo_innovations"] = self._merge_unique(pack["taboo_innovations"], doc.taboo_innovations)
            pack["external_knowledge_refs"] = self._merge_unique(pack["external_knowledge_refs"], doc.external_knowledge_refs)
        for slug in worldview_docs or []:
            doc = self._load_doc("worldview-dossiers", slug)
            pack["worldview_capsule"] = self._merge_unique(pack["worldview_capsule"], doc.worldview_capsule)
            pack["innovation_directives"] = self._merge_unique(pack["innovation_directives"], doc.innovation_directives)
            pack["taboo_innovations"] = self._merge_unique(pack["taboo_innovations"], doc.taboo_innovations)
            pack["external_knowledge_refs"] = self._merge_unique(pack["external_knowledge_refs"], doc.external_knowledge_refs)
        for slug in audience_docs or []:
            doc = self._load_doc("audience-expectation-notes", slug)
            pack["external_knowledge_refs"] = self._merge_unique(pack["external_knowledge_refs"], doc.external_knowledge_refs)
            pack["innovation_directives"] = self._merge_unique(pack["innovation_directives"], doc.innovation_directives)
        return pack

    @staticmethod
    def _score_doc(doc: SteeringLibraryDoc, query_text: str) -> tuple[int, list[str]]:
        lowered = query_text.lower()
        score = 0
        reasons: list[str] = []
        if doc.slug.replace("-", " ").lower() in lowered:
            score += 3
            reasons.append(f"slug_match:{doc.slug}")
        for label in doc.labels:
            if label.lower() in lowered:
                score += 2
                reasons.append(f"label_match:{label}")
        for item in doc.worldview_capsule[:2] + doc.trope_axes[:2] + doc.innovation_directives[:2]:
            candidate = item.lower()
            matched = False
            for token in [candidate[:4], candidate[:6], candidate[:8]]:
                if token and token in lowered:
                    score += 1
                    reasons.append(f"content_hint:{item}")
                    matched = True
                    break
            if not matched:
                for word in [part.strip() for part in item.replace("：", " ").replace("/", " ").split() if part.strip()]:
                    sub = word.lower()[:4]
                    if sub and sub in lowered:
                        score += 1
                        reasons.append(f"content_hint:{item}")
                        break
        return score, reasons

    def retrieve_pack(
        self,
        *,
        query_text: str,
        trope_docs: list[str] | None = None,
        worldview_docs: list[str] | None = None,
        audience_docs: list[str] | None = None,
    ) -> SteeringRetrievalPayload:
        trope_candidates = trope_docs or [p.stem for p in sorted((self.root / "trope-library").glob("*.md"))]
        worldview_candidates = worldview_docs or [p.stem for p in sorted((self.root / "worldview-dossiers").glob("*.md"))]
        audience_candidates = audience_docs or [p.stem for p in sorted((self.root / "audience-expectation-notes").glob("*.md"))]

        def _rank(directory: str, slugs: list[str]) -> list[tuple[SteeringLibraryDoc, int, list[str]]]:
            ranked: list[tuple[SteeringLibraryDoc, int, list[str]]] = []
            for slug in slugs:
                doc = self._load_doc(directory, slug)
                score, reasons = self._score_doc(doc, query_text)
                if score > 0:
                    ranked.append((doc, score, reasons))
            ranked.sort(key=lambda item: (-item[1], item[0].slug))
            return ranked

        trope_ranked = _rank("trope-library", trope_candidates)
        worldview_ranked = _rank("worldview-dossiers", worldview_candidates)
        audience_ranked = _rank("audience-expectation-notes", audience_candidates)

        selected_trope_ranked = trope_ranked[:2]
        selected_worldview_ranked = worldview_ranked[:2]
        selected_audience_ranked = audience_ranked[:2]
        selected_trope = [item[0].slug for item in selected_trope_ranked]
        selected_worldview = [item[0].slug for item in selected_worldview_ranked]
        selected_audience = [item[0].slug for item in selected_audience_ranked]
        pack = self.assemble_pack(
            trope_docs=selected_trope,
            worldview_docs=selected_worldview,
            audience_docs=selected_audience,
        )
        return {
            "steering_pack": pack,
            "retrieval_meta": {
                "query_text": query_text,
                "selected_trope_docs": selected_trope,
                "selected_worldview_docs": selected_worldview,
                "selected_audience_docs": selected_audience,
                "hit_reasons": {
                    "trope": {item[0].slug: item[2] for item in selected_trope_ranked},
                    "worldview": {item[0].slug: item[2] for item in selected_worldview_ranked},
                    "audience": {item[0].slug: item[2] for item in selected_audience_ranked},
                },
                "selected_doc_summaries": {
                    "trope": [item[0].compact_summary() for item in selected_trope_ranked],
                    "worldview": [item[0].compact_summary() for item in selected_worldview_ranked],
                    "audience": [item[0].compact_summary() for item in selected_audience_ranked],
                },
            },
        }
