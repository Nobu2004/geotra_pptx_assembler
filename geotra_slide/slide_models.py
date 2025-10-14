"""Data models representing slide templates and generated content."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class PlaceholderSpec:
    """Definition of a placeholder that belongs to a slide asset."""

    name: str
    idx: int
    description: str
    edit_policy: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaceholderSpec":
        metadata = {
            key: value
            for key, value in data.items()
            if key not in {"name", "idx", "description", "edit_policy"}
        }
        return cls(
            name=data.get("name", ""),
            idx=int(data.get("idx", -1)),
            description=data.get("description", ""),
            edit_policy=data.get("edit_policy", "generate"),
            metadata=metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": self.name,
            "idx": self.idx,
            "description": self.description,
            "edit_policy": self.edit_policy,
        }
        payload.update(self.metadata)
        return payload


@dataclass(slots=True)
class SlideAsset:
    """Metadata describing a reusable slide stored in the slide library."""

    asset_id: str
    file_name: str
    description: str
    category: Optional[str]
    tags: List[str]
    placeholders: List[PlaceholderSpec]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlideAsset":
        placeholders = [
            PlaceholderSpec.from_dict(item)
            for item in data.get("placeholders", [])
        ]
        return cls(
            asset_id=data.get("id", ""),
            file_name=data.get("file_name", ""),
            description=data.get("description", ""),
            category=data.get("category"),
            tags=list(data.get("tags", [])),
            placeholders=placeholders,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.asset_id,
            "file_name": self.file_name,
            "description": self.description,
            "category": self.category,
            "tags": list(self.tags),
            "placeholders": [ph.to_dict() for ph in self.placeholders],
        }

    def get_placeholder(self, name: str) -> Optional[PlaceholderSpec]:
        return next((ph for ph in self.placeholders if ph.name == name), None)

    def editable_placeholders(self) -> List[PlaceholderSpec]:
        return [
            ph for ph in self.placeholders if ph.edit_policy.lower() == "generate"
        ]


@dataclass(slots=True)
class SlidePlaceholderContent:
    """Generated content for a placeholder."""

    name: str
    text: str
    policy: str
    references: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "placeholder_name": self.name,
            "content": self.text,
            "policy": self.policy,
            "references": list(self.references),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlidePlaceholderContent":
        return cls(
            name=data.get("placeholder_name", ""),
            text=data.get("content", ""),
            policy=data.get("policy", "generate"),
            references=list(data.get("references", [])),
        )


@dataclass(slots=True)
class SlidePage:
    """A single slide within a slide document."""

    slide_id: str
    page_number: int
    asset_id: str
    asset_file: str
    title: Optional[str] = None
    placeholders: List[SlidePlaceholderContent] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "page": self.page_number,
            "asset_id": self.asset_id,
            "asset_file": self.asset_file,
            "title": self.title,
            "placeholders": [ph.to_dict() for ph in self.placeholders],
            "notes": dict(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlidePage":
        return cls(
            slide_id=data.get("slide_id", ""),
            page_number=int(data.get("page", 1)),
            asset_id=data.get("asset_id", ""),
            asset_file=data.get("asset_file", ""),
            title=data.get("title"),
            placeholders=[
                SlidePlaceholderContent.from_dict(item)
                for item in data.get("placeholders", [])
            ],
            notes=dict(data.get("notes", {})),
        )


@dataclass(slots=True)
class SlideDocument:
    """Container for all slides that compose the current deck."""

    slides: List[SlidePage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slides": [slide.to_dict() for slide in self.slides],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlideDocument":
        slides = [
            SlidePage.from_dict(item)
            for item in data.get("slides", [])
        ]
        metadata = dict(data.get("metadata", {}))
        return cls(slides=slides, metadata=metadata)

    def get_slide(self, slide_id: str) -> Optional[SlidePage]:
        return next((slide for slide in self.slides if slide.slide_id == slide_id), None)

    def upsert_slide(self, slide: SlidePage) -> None:
        for idx, existing in enumerate(self.slides):
            if existing.slide_id == slide.slide_id:
                self.slides[idx] = slide
                break
        else:
            self.slides.append(slide)
        self.slides.sort(key=lambda item: item.page_number)
