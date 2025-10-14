"""Structured slide content generation using the OpenAI provider."""

from __future__ import annotations

import json
import logging
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from LLM_API.data_classes import StructuredOutputRequest, StructuredOutputResponse

from .slide_library import SlideLibrary
from .slide_models import (
    PlaceholderSpec,
    SlideAsset,
    SlideDocument,
    SlidePage,
    SlidePlaceholderContent,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class GenerationContext:
    """Input parameters that influence slide generation."""

    user_request: str
    target_company: Optional[str] = None
    external_research: Optional[str] = None
    additional_notes: Optional[str] = None
    internal_document: Optional[str] = None


class SlideContentGenerator:
    """Generate placeholder content for slides via structured LLM output."""

    def __init__(
        self,
        slide_library: SlideLibrary,
        *,
        llm_client=None,
        internal_document_path: Optional[Path] = None,
        max_internal_chars: int = 4000,
    ) -> None:
        self.slide_library = slide_library
        self.llm_client = llm_client
        self.internal_document_path = (
            Path(internal_document_path)
            if internal_document_path is not None
            else Path("data/internal_report.md")
        )
        self.max_internal_chars = max_internal_chars
        self._cached_internal_document: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_for_slide(
        self,
        document: SlideDocument,
        slide_id: str,
        *,
        context: GenerationContext,
    ) -> SlideDocument:
        """Populate a slide within ``document`` using structured LLM output."""

        slide = document.get_slide(slide_id)
        if slide is None:
            raise KeyError(f"Slide '{slide_id}' not found in document")

        asset = self.slide_library.get_asset(slide.asset_id)
        filled_placeholders = self._generate_content_for_asset(slide, asset, context)

        slide.placeholders = filled_placeholders
        slide.notes.setdefault("citations", [])
        slide.notes.setdefault("summary", None)

        if context.additional_notes:
            slide.notes["user_notes"] = context.additional_notes

        document.upsert_slide(slide)
        self._accumulate_references(document, slide.notes.get("citations", []))
        return document

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_content_for_asset(
        self,
        slide: SlidePage,
        asset: SlideAsset,
        context: GenerationContext,
    ) -> List[SlidePlaceholderContent]:
        editable_specs = [
            ph for ph in asset.placeholders if ph.edit_policy.lower() == "generate"
        ]

        llm_results: Dict[str, Dict[str, List[str] | str]] = {}
        slide_summary: Optional[str] = None
        slide_citations: List[str] = []

        if editable_specs and self.llm_client is not None:
            internal_document = (
                context.internal_document or self._load_internal_document()
            )
            prompt = self._build_prompt(slide, asset, context, internal_document)
            schema = self._build_schema(editable_specs)
            request = StructuredOutputRequest(
                prompt=prompt,
                schema=schema,
                schema_name="slide_content",
                instructions=(
                    "プレースホルダーごとに日本語で簡潔な文章を出力し、" "出典はreferencesフィールドに列挙してください。"
                ),
            )

            try:
                response = self.llm_client.generate_structured_output(request)
                parsed = self._extract_parsed_output(response)
                if parsed:
                    placeholders = parsed.get("placeholders", [])
                    for item in placeholders:
                        name = item.get("placeholder_name") or item.get("name")
                        text = item.get("text") or item.get("content", "")
                        references = item.get("references") or item.get("citations") or []
                        if name:
                            llm_results[name] = {
                                "text": text,
                                "references": list(references),
                            }
                    slide_summary = parsed.get("slide_summary") or parsed.get("summary")
                    slide_citations = list(parsed.get("citations", []))
            except Exception as exc:  # pragma: no cover - safety net
                LOGGER.warning("Structured output generation failed: %s", exc)

        placeholders: List[SlidePlaceholderContent] = []
        target_company = context.target_company or _infer_target_entity(
            context.user_request
        )

        for spec in asset.placeholders:
            policy = spec.edit_policy.lower()
            if policy == "generate":
                generated = llm_results.get(spec.name)
                text = (generated or {}).get("text") or spec.description
                references = list((generated or {}).get("references", []))
            elif policy == "fixed":
                text = _normalize_fixed_text(spec.description)
                references = []
            elif policy == "populate":
                text = _populate_with_context(spec.description, target_company)
                references = []
            else:
                text = spec.description
                references = []

            placeholders.append(
                SlidePlaceholderContent(
                    name=spec.name,
                    text=text.strip(),
                    policy=policy,
                    references=references,
                )
            )

        if slide_summary:
            slide.notes["summary"] = slide_summary
        if slide_citations:
            slide.notes["citations"] = slide_citations

        return placeholders

    def _build_prompt(
        self,
        slide: SlidePage,
        asset: SlideAsset,
        context: GenerationContext,
        internal_document: Optional[str],
    ) -> str:
        target_company = context.target_company or _infer_target_entity(
            context.user_request
        )
        placeholder_lines = []
        for spec in asset.placeholders:
            placeholder_lines.append(
                f"- {spec.name} [{spec.edit_policy}]: {spec.description}"
            )

        prompt_sections = [
            "あなたは日本語のプレゼンテーションライターです。",
            "テンプレートの説明とユーザーの要望を踏まえ、指定されたプレースホルダーに適切なテキストを生成してください。",
            "生成時のルール:",
            "1. 箇条書きではなく、テンプレートの意図に沿った簡潔な文章にする。",
            "2. 断定は避け、必要に応じて出典番号を含める。",
            "3. プレースホルダーの説明に従う。",
            "",
            f"[スライド情報]\nID: {slide.slide_id}\nページ番号: {slide.page_number}",
            f"テンプレートファイル: {asset.file_name}\nカテゴリ: {asset.category or '不明'}",
            f"用途: {asset.description}",
            f"スライドタイトル: {slide.title or '未設定'}",
            f"想定読者(推定): {target_company or '未特定'}",
            "",
            "[ユーザーからのリクエスト]",
            context.user_request,
            "",
            "[プレースホルダー詳細]",
            "\n".join(placeholder_lines),
        ]

        if context.external_research:
            prompt_sections.extend(
                [
                    "",
                    "[外部リサーチ要約]",
                    _truncate_text(context.external_research, 1500),
                ]
            )

        if internal_document:
            prompt_sections.extend(
                [
                    "",
                    "[内部ドキュメント抜粋]",
                    _truncate_text(internal_document, self.max_internal_chars),
                ]
            )

        if context.additional_notes:
            prompt_sections.extend(
                [
                    "",
                    "[補足指示]",
                    context.additional_notes,
                ]
            )

        prompt_sections.append(
            "出力はJSONのみ。各プレースホルダーのcontentは200文字以内。"
        )

        return "\n".join(prompt_sections)

    def _build_schema(self, placeholders: Sequence[PlaceholderSpec]) -> Dict[str, object]:
        placeholder_enum = [spec.name for spec in placeholders]
        return {
            "type": "object",
            "properties": {
                "slide_summary": {
                    "type": "string",
                    "description": "スライド全体の要約(任意)",
                },
                "citations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "使用した情報源のリスト",
                },
                "placeholders": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "placeholder_name": {
                                "type": "string",
                                "enum": placeholder_enum,
                            },
                            "text": {
                                "type": "string",
                                "description": "プレースホルダーに挿入する本文",
                            },
                            "references": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "参照した情報源",
                                "default": [],
                            },
                        },
                        "required": ["placeholder_name", "text"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["placeholders"],
            "additionalProperties": False,
        }

    def _extract_parsed_output(
        self, response: StructuredOutputResponse
    ) -> Optional[Dict[str, object]]:
        if response is None:
            return None
        if response.parsed_output:
            return response.parsed_output
        if response.text:
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                LOGGER.debug("Failed to parse structured output text: %s", response.text)
        if response.error:
            LOGGER.warning("Structured output error: %s", response.error)
        if response.validation_error:
            LOGGER.warning("Validation error: %s", response.validation_error)
        return None

    def _load_internal_document(self) -> Optional[str]:
        if self._cached_internal_document is not None:
            return self._cached_internal_document
        if not self.internal_document_path.exists():
            LOGGER.info("Internal document not found at %s", self.internal_document_path)
            self._cached_internal_document = None
            return None
        raw = self.internal_document_path.read_text(encoding="utf-8")
        self._cached_internal_document = raw[: self.max_internal_chars]
        return self._cached_internal_document

    def _accumulate_references(self, document: SlideDocument, citations: List[str]) -> None:
        if not citations:
            return
        existing = set(document.metadata.get("references", []))
        for citation in citations:
            existing.add(citation)
        document.metadata["references"] = sorted(existing)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _normalize_fixed_text(description: str) -> str:
    text = description or ""
    text = re.sub(r"[「」]", "", text)
    text = re.sub(r"(と記載|と記述|を記載|を記述).*", "", text)
    return text.strip()


def _populate_with_context(description: str, target_company: Optional[str]) -> str:
    text = description or ""
    company = target_company or "御社"
    text = text.replace("相手企業名+", company)
    text = text.replace("相手企業名", company)
    text = re.sub(r"20XX[./]?\d{0,2}", datetime.now().strftime("%Y.%m"), text)
    text = re.sub(r"YYYY\.M", datetime.now().strftime("%Y.%m"), text)
    text = re.sub(r"20XX", str(datetime.now().year), text)
    return _normalize_fixed_text(text)


def _infer_target_entity(user_request: str) -> Optional[str]:
    if not user_request:
        return None
    patterns = [
        r"([A-Za-z0-9一-龥ァ-ヿー]+)社",
        r"([A-Za-z0-9一-龥ァ-ヿー]+)向け",
        r"([A-Za-z0-9一-龥ァ-ヿー]+)様",
        r"([A-Za-z0-9一-龥ァ-ヿー]+)の",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_request)
        if match:
            return match.group(1)
    tokens = re.findall(r"[A-Za-z]{2,}", user_request)
    if tokens:
        return tokens[0]
    return None


def _truncate_text(text: str, limit: int) -> str:
    if text is None:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return textwrap.shorten(text, width=limit, placeholder="…")

