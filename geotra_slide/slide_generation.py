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

from LLM_API.data_classes import (
    BaseRequest,
    StructuredOutputRequest,
    StructuredOutputResponse,
    WebSearchRequest,
)

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
class PlanningContext:
    """Context used when deriving the high-level slide structure."""

    conversation_history: str
    goal: str
    target_company: Optional[str] = None
    additional_requirements: Optional[str] = None


@dataclass
class GenerationContext:
    """Input parameters that influence slide generation."""

    user_request: str
    target_company: Optional[str] = None
    external_research: Optional[str] = None
    additional_notes: Optional[str] = None
    internal_document: Optional[str] = None
    perform_web_search: bool = False


class SlideStructurePlanner:
    """Create a textual slide structure from a planning conversation."""

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def build_structure(self, context: PlanningContext) -> str:
        if self.llm_client is None:
            raise RuntimeError("LLM client is required to generate slide structure")

        prompt_sections = [
            "あなたは熟練のスライド構成プランナーです。",
            "以下の対話ログを読み取り、ユーザーの目的を達成するためのスライド全体像を200字以内で日本語でまとめてください。",
            "会話ログから導かれる章立てや盛り込むべき観点を文章で説明してください。",
            "---",
            context.conversation_history,
            "---",
            f"最終目標: {context.goal}",
        ]
        if context.target_company:
            prompt_sections.append(f"想定読者・企業: {context.target_company}")
        if context.additional_requirements:
            prompt_sections.append(f"追加要望: {context.additional_requirements}")

        prompt = "\n".join(section for section in prompt_sections if section)
        request = BaseRequest(prompt=prompt)
        response = self.llm_client.generate_content(request)
        if getattr(response, "text", "").strip():
            return response.text.strip()
        raise RuntimeError("スライド構成の生成に失敗しました。")


class SlideOutlineGenerator:
    """Generate slide.json outlines based on slide structure guidance."""

    def __init__(self, slide_library: SlideLibrary, llm_client=None) -> None:
        self.slide_library = slide_library
        self.llm_client = llm_client

    def generate_outline(
        self,
        *,
        slide_structure: str,
        context: GenerationContext,
    ) -> SlideDocument:
        """Return a ``SlideDocument`` with slide shells selected by the LLM."""

        assets = list(self.slide_library.list_assets())
        if not assets:
            raise RuntimeError("スライドライブラリにアセットが存在しません。")

        if self.llm_client is None:
            slides = self._fallback_outline(assets, slide_structure)
            return SlideDocument(slides=slides, metadata={"slide_structure": slide_structure})

        schema = self._build_schema(assets)
        prompt = self._build_prompt(slide_structure, context, assets)
        request = StructuredOutputRequest(
            prompt=prompt,
            schema=schema,
            schema_name="slide_outline",
            instructions=(
                "slide_structureを踏まえ、利用するスライドテンプレートを選定してください。"
                " 出力はJSONのみで、slides配列にはページ順に並べてください。"
            ),
        )

        response = self.llm_client.generate_structured_output(request)
        parsed = self._extract_parsed_output(response)
        if not parsed:
            slides = self._fallback_outline(assets, slide_structure)
        else:
            slides = self._build_slides_from_parsed(parsed)

        document = SlideDocument(slides=slides, metadata={"slide_structure": slide_structure})
        if context.additional_notes:
            document.metadata.setdefault("user_notes", context.additional_notes)
        return document

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _build_schema(self, assets: Sequence[SlideAsset]) -> Dict[str, object]:
        asset_enum = [asset.asset_id for asset in assets]
        return {
            "type": "object",
            "properties": {
                "slides": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "slide_id": {
                                "type": "string",
                                "description": "スライド識別子 (例: slide_01)",
                            },
                            "page_number": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "ページ番号",
                            },
                            "asset_id": {
                                "type": "string",
                                "enum": asset_enum,
                            },
                            "title": {"type": "string"},
                            "notes": {
                                "type": "string",
                                "description": "スライド意図のメモ (任意)",
                            },
                        },
                        "required": ["asset_id"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["slides"],
            "additionalProperties": False,
        }

    def _build_prompt(
        self,
        slide_structure: str,
        context: GenerationContext,
        assets: Sequence[SlideAsset],
    ) -> str:
        asset_lines = []
        for asset in assets:
            asset_lines.append(
                f"- {asset.asset_id}: {asset.description[:120]}"
            )

        sections = [
            "あなたはGEOTRAのスライドライブラリから最適なテンプレートを選定するアシスタントです。",
            "以下の候補リストから目的に合うものを選び、ページ順にslides配列へ出力してください。",
            "同じasset_idを複数回使っても構いません。",
            "",
            "[候補テンプレート一覧]",
            "\n".join(asset_lines[:40]),
            "",
            "[ユーザーの目的と文脈]",
            slide_structure,
        ]

        if context.user_request:
            sections.extend(["", "[最終的な依頼内容]", context.user_request])
        if context.target_company:
            sections.append(f"想定読者: {context.target_company}")
        if context.additional_notes:
            sections.append(f"補足条件: {context.additional_notes}")

        sections.append(
            "slides内の各要素はJSONオブジェクトで、slide_idはslide_01のように連番、page_numberは1から開始してください。"
        )

        return "\n".join(section for section in sections if section)

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
                LOGGER.debug("Failed to parse outline structured output: %s", response.text)
        return None

    def _build_slides_from_parsed(
        self, payload: Dict[str, object]
    ) -> List[SlidePage]:
        slides_payload = payload.get("slides", []) if isinstance(payload, dict) else []
        slides: List[SlidePage] = []
        for idx, raw in enumerate(slides_payload, start=1):
            if not isinstance(raw, dict):
                continue
            asset_id = raw.get("asset_id")
            if not asset_id:
                continue
            asset = self.slide_library.get_asset(asset_id)
            slide_id = raw.get("slide_id") or f"slide_{idx:02d}"
            page_number = int(raw.get("page_number") or raw.get("page") or idx)
            title = raw.get("title")
            notes = {}
            if raw.get("notes"):
                notes["outline_notes"] = raw.get("notes")
            slides.append(
                SlidePage(
                    slide_id=slide_id,
                    page_number=page_number,
                    asset_id=asset.asset_id,
                    asset_file=asset.file_name,
                    title=title,
                    notes=notes,
                )
            )
        slides.sort(key=lambda slide: slide.page_number)
        if not slides:
            return self._fallback_outline(list(self.slide_library.list_assets()), "")
        return slides

    def _fallback_outline(
        self, assets: Sequence[SlideAsset], slide_structure: str
    ) -> List[SlidePage]:
        slides: List[SlidePage] = []
        for idx, asset in enumerate(assets[:2], start=1):
            slides.append(
                SlidePage(
                    slide_id=f"slide_{idx:02d}",
                    page_number=idx,
                    asset_id=asset.asset_id,
                    asset_file=asset.file_name,
                    title=f"アウトラインスライド {idx}",
                    notes={"outline_notes": slide_structure[:200]},
                )
            )
        return slides


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
        research_snippet = self._maybe_perform_web_search(slide, context)
        filled_placeholders = self._generate_content_for_asset(
            slide, asset, context, research_snippet=research_snippet
        )

        slide.placeholders = filled_placeholders
        slide.notes.setdefault("citations", [])
        slide.notes.setdefault("summary", None)

        if context.additional_notes:
            slide.notes["user_notes"] = context.additional_notes

        document.upsert_slide(slide)
        self._accumulate_references(document, slide.notes.get("citations", []))
        return document

    def generate_for_document(
        self, document: SlideDocument, *, context: GenerationContext
    ) -> SlideDocument:
        """Populate every slide in ``document`` sequentially."""

        for slide in list(document.slides):
            document = self.generate_for_slide(
                document, slide.slide_id, context=context
            )
        return document

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_content_for_asset(
        self,
        slide: SlidePage,
        asset: SlideAsset,
        context: GenerationContext,
        *,
        research_snippet: Optional[str] = None,
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
            prompt = self._build_prompt(
                slide,
                asset,
                context,
                internal_document,
                research_snippet=research_snippet,
            )
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
        *,
        research_snippet: Optional[str] = None,
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
        elif research_snippet:
            prompt_sections.extend(
                [
                    "",
                    "[自動Webリサーチ結果]",
                    _truncate_text(research_snippet, 1500),
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

    def _maybe_perform_web_search(
        self, slide: SlidePage, context: GenerationContext
    ) -> Optional[str]:
        if not context.perform_web_search:
            return None
        if self.llm_client is None or not hasattr(self.llm_client, "web_search"):
            return None
        try:
            prompt = (
                f"{context.user_request}\n対象スライド: {slide.title or slide.asset_id}"
            )
            request = WebSearchRequest(
                prompt=prompt,
                max_search_results=3,
                model_name=getattr(self.llm_client, "model_name", None),
            )
            response = self.llm_client.web_search(request)
            if response is None:
                return None
            if getattr(response, "text", None):
                return response.text
            if getattr(response, "citations", None):
                urls = [c.url for c in response.citations if getattr(c, "url", None)]
                if urls:
                    return "検索結果: " + ", ".join(urls)
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            LOGGER.debug("Web search skipped due to error: %s", exc)
        return None

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

