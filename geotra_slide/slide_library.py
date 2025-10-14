"""Utility helpers to work with the slide library and master template manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .slide_models import PlaceholderSpec, SlideAsset


class SlideLibrary:
    """Loads metadata for master templates and slide assets."""

    def __init__(self, assets_root: Optional[Path] = None) -> None:
        self.assets_root = Path(assets_root or Path("assets"))
        self.slide_library_dir = self.assets_root / "slide_library"
        self.templates_dir = self.assets_root / "templates"

        self.slide_manifest_path = self.slide_library_dir / "slide_library_manifest.json"
        self.master_manifest_path = self.templates_dir / "master_manifest.json"

        self._slide_assets: Dict[str, SlideAsset] = {}
        self._load_slide_assets()

    # ------------------------------------------------------------------
    # manifest loading
    # ------------------------------------------------------------------
    def _load_slide_assets(self) -> None:
        if not self.slide_manifest_path.exists():
            raise FileNotFoundError(
                f"Slide library manifest not found at {self.slide_manifest_path}"
            )
        data = json.loads(self.slide_manifest_path.read_text(encoding="utf-8"))
        assets = data.get("slide_assets", [])
        self._slide_assets = {
            entry.get("id", ""): SlideAsset.from_dict(entry) for entry in assets
        }

    # ------------------------------------------------------------------
    # lookup helpers
    # ------------------------------------------------------------------
    def list_assets(self) -> Iterable[SlideAsset]:
        return self._slide_assets.values()

    def get_asset(self, asset_id: str) -> SlideAsset:
        try:
            return self._slide_assets[asset_id]
        except KeyError as exc:
            raise KeyError(f"Unknown slide asset id: {asset_id}") from exc

    def get_placeholder(self, asset_id: str, placeholder_name: str) -> PlaceholderSpec:
        asset = self.get_asset(asset_id)
        placeholder = asset.get_placeholder(placeholder_name)
        if placeholder is None:
            raise KeyError(
                f"Placeholder '{placeholder_name}' not found in asset '{asset_id}'"
            )
        return placeholder

    def asset_file_path(self, asset_id: str) -> Path:
        asset = self.get_asset(asset_id)
        return self.slide_library_dir / asset.file_name

    def master_template_path(self) -> Path:
        manifest = json.loads(self.master_manifest_path.read_text(encoding="utf-8"))
        template_file = manifest.get("master_template_file")
        if not template_file:
            raise ValueError("master_manifest.json is missing 'master_template_file'")
        return self.templates_dir / template_file

    # ------------------------------------------------------------------
    # outline helpers
    # ------------------------------------------------------------------
    def build_initial_outline(
        self,
        slide_ids: List[str],
        *,
        title_mapping: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, str]]:
        """Return a minimal outline referencing slide assets.

        The outline only contains per-slide metadata (page number, slide id and
        original file name). Content is filled later when LLM generation is
        executed.
        """

        outline: List[Dict[str, str]] = []
        for idx, slide_id in enumerate(slide_ids, start=1):
            asset = self.get_asset(slide_id)
            outline.append(
                {
                    "slide_id": f"slide_{idx:02d}",
                    "page": str(idx),
                    "asset_id": asset.asset_id,
                    "asset_file": asset.file_name,
                    "title": (title_mapping or {}).get(slide_id),
                }
            )
        return outline


# Convenience alias for export -------------------------------------------------
SlideAsset = SlideAsset
PlaceholderSpec = PlaceholderSpec
