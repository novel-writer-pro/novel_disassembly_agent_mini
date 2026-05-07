"""Local steering library loader for trope/worldview/audience dossiers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SteeringLibraryDoc:
    """Normalized steering library doc slices."""

    slug: str
    worldview_capsule: list[str]
    trope_axes: list[str]
    innovation_directives: list[str]
    taboo_innovations: list[str]
    external_knowledge_refs: list[str]


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
    ) -> dict[str, list[str]]:
        pack = {
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
