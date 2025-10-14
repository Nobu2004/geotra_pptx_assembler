"""Utilities for reading and writing slide.json documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .slide_models import SlideDocument, SlidePage


class SlideDocumentStore:
    """Persist `SlideDocument` instances to disk as JSON files."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------
    def load(self) -> SlideDocument:
        if not self.path.exists():
            raise FileNotFoundError(f"slide.json not found at {self.path}")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return SlideDocument.from_dict(data)

    def save(self, document: SlideDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = document.to_dict()
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------
    @classmethod
    def create_from_outline(
        cls,
        path: Path,
        outline: list[dict],
        *,
        metadata: Optional[dict] = None,
    ) -> SlideDocument:
        """Create `SlideDocument` from an outline and persist it."""

        slides = [SlidePage.from_dict(item) for item in outline]
        document = SlideDocument(slides=slides, metadata=metadata or {})
        store = cls(path)
        store.save(document)
        return document

