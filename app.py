"""Streamlit UI for interacting with the GEOTRA slide generation pipeline."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:  # pragma: no cover - exercised indirectly in import-time checks
    import streamlit as st
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional dependency
    STREAMLIT_IMPORT_ERROR = exc

    class _StreamlitStub:
        """Fallback shim so test imports succeed without Streamlit."""

        def cache_resource(self, *args, **kwargs):  # noqa: D401 - simple decorator shim
            def decorator(func):
                return func

            return decorator

        def __getattr__(self, name):
            raise RuntimeError(
                "Streamlit is required to run the web UI. Install the 'streamlit' package "
                "to enable UI features."
            ) from STREAMLIT_IMPORT_ERROR

    st = _StreamlitStub()
else:  # pragma: no cover - import branch depends on optional dependency
    STREAMLIT_IMPORT_ERROR = None

from LLM_API.data_classes import (
    BaseResponse,
    StructuredOutputRequest,
    StructuredOutputResponse,
    WebSearchResponse,
)

from geotra_slide.slide_document import SlideDocumentStore
from geotra_slide.slide_generation import (
    GenerationContext,
    PlanningContext,
    SlideContentGenerator,
    SlideOutlineGenerator,
    SlideStructurePlanner,
)
from geotra_slide.slide_library import SlideLibrary
from geotra_slide.slide_models import SlideDocument
from geotra_slide.pptx_renderer import SlideDeckRenderer


def _extract_request_excerpt(prompt: str, *, max_width: int = 80) -> str:
    """Return a concise summary of the user request embedded in ``prompt``."""

    if not prompt:
        return "ユーザー入力なし"

    marker = "[ユーザーからのリクエスト]"
    if marker in prompt:
        section = prompt.split(marker, 1)[1]
        section = section.split("[", 1)[0]
    else:
        section = prompt
    section = section.strip().replace("\n", " ")
    if not section:
        return "ユーザー入力なし"
    return textwrap.shorten(section, width=max_width, placeholder="…")


class StubStructuredOutputLLM:
    """Simple stub that mimics structured output generation for demos/tests."""

    def __init__(
        self,
        *,
        summary: str = "スタブ生成によるスライド概要",
        slide_library: Optional[SlideLibrary] = None,
    ) -> None:
        self.summary = summary
        self.slide_library = slide_library

    # ------------------------------------------------------------------
    # LLM compatible interface
    # ------------------------------------------------------------------
    def generate_content(self, request) -> BaseResponse:
        excerpt = _extract_request_excerpt(getattr(request, "prompt", ""))
        structure = (
            f"{excerpt}を整理した2枚構成案です。"
            " 表紙で目的を示し、続いて要点をまとめます。"
        )
        return BaseResponse(text=structure, model_used="stub-text")

    def generate_structured_output(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse:
        schema_props = request.schema.get("properties", {})
        if "slides" in schema_props:
            return self._generate_outline_response(request)
        return self._generate_placeholder_response(request)

    def web_search(self, request) -> WebSearchResponse:  # noqa: D401 - simple stub
        return WebSearchResponse(
            text="スタブによる簡易Web検索サマリー",
            model_used="stub-web",
            citations=[],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_outline_response(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse:
        assets = list(self.slide_library.list_assets()) if self.slide_library else []
        excerpt = _extract_request_excerpt(request.prompt)
        slides: List[Dict[str, Any]] = []
        if assets:
            for idx, asset in enumerate(assets[:2], start=1):
                slides.append(
                    {
                        "slide_id": f"slide_{idx:02d}",
                        "page_number": idx,
                        "asset_id": asset.asset_id,
                        "title": f"{excerpt} - {asset.description[:12]}",
                        "notes": f"スタブで選定: {asset.asset_id}",
                    }
                )
        else:
            slides.append(
                {
                    "slide_id": "slide_01",
                    "page_number": 1,
                    "asset_id": "stub_asset",
                    "title": f"{excerpt} - 概要",
                    "notes": "スタブで生成",
                }
            )

        payload = {"slides": slides}
        return StructuredOutputResponse(
            text=json.dumps(payload, ensure_ascii=False),
            parsed_output=payload,
            model_used="stub-structured",
        )

    def _generate_placeholder_response(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse:
        placeholder_names: Iterable[str] = (
            request.schema
            .get("properties", {})
            .get("placeholders", {})
            .get("items", {})
            .get("properties", {})
            .get("placeholder_name", {})
            .get("enum", [])
        )
        user_excerpt = _extract_request_excerpt(request.prompt)
        placeholders: List[Dict[str, object]] = []
        for name in placeholder_names:
            text = f"{user_excerpt}に基づき、{name}の内容を整理したドラフトです。"
            placeholders.append(
                {
                    "placeholder_name": name,
                    "text": text[:200],
                    "references": ["internal_report.md"],
                }
            )

        parsed = {
            "slide_summary": self.summary,
            "citations": ["internal_report.md"],
            "placeholders": placeholders,
        }
        return StructuredOutputResponse(
            text=json.dumps(parsed, ensure_ascii=False),
            parsed_output=parsed,
            model_used="stub-structured",
        )


@st.cache_resource(show_spinner=False)
def load_resources(path: Path = Path("assets")) -> Tuple[SlideLibrary, SlideDeckRenderer]:
    """Load the slide library and initialise the PPTX renderer."""

    library = SlideLibrary(path)
    renderer = SlideDeckRenderer(library)
    return library, renderer


def _instantiate_llm(choice: str, slide_library: SlideLibrary):
    if choice == "OpenAI (環境変数)":
        try:
            from LLM_API.providers.openai import OpenAIModel

            return OpenAIModel()
        except Exception as exc:  # pragma: no cover - depends on runtime secrets
            st.warning(
                "OpenAIクライアントの初期化に失敗しました。環境変数OPENAI_API_KEYを確認してください。"
            )
            st.text(str(exc))
            return None
    return StubStructuredOutputLLM(slide_library=slide_library)


def _load_document_from_upload(upload) -> Optional[SlideDocument]:
    if upload is None:
        return None
    data = json.load(upload)
    return SlideDocument.from_dict(data)


def _save_document(document: SlideDocument, path: Path) -> None:
    store = SlideDocumentStore(path)
    store.save(document)


def main() -> None:
    if STREAMLIT_IMPORT_ERROR is not None:  # pragma: no cover - requires missing dependency
        raise RuntimeError(
            "Streamlit is not installed. Run 'pip install streamlit' to launch the UI."
        ) from STREAMLIT_IMPORT_ERROR

    st.set_page_config(page_title="GEOTRA PPTX Assembler", layout="wide")
    st.title("GEOTRA PPTX Assembler")

    library, renderer = load_resources()
    assets = sorted(library.list_assets(), key=lambda asset: asset.asset_id)
    if not assets:
        st.error("スライドアセットが見つかりません。assets/slide_library を確認してください。")
        return

    st.session_state.setdefault("slide_structure", "")
    st.session_state.setdefault("document", None)
    st.session_state.setdefault("slide_structure_editor", st.session_state["slide_structure"])
    st.session_state.setdefault("preview_index", 1)

    with st.sidebar:
        st.header("ジェネレーション設定")
        llm_option = st.radio(
            "生成モード",
            ("スタブ生成", "OpenAI (環境変数)"),
            index=0,
            help="OpenAIキーが未設定の場合はスタブ生成を利用してください。",
        )
        perform_web_search = st.checkbox(
            "Web検索を有効化",
            value=False,
            help="OpenAIモードでのみ有効です。スタブでは簡易サマリーを使用します。",
        )
        uploaded = st.file_uploader("既存のslide.jsonを読み込む", type="json")
        loaded_document = _load_document_from_upload(uploaded)
        if loaded_document:
            st.success("slide.jsonを読み込みました。構成と内容を下部に表示します。")
            st.session_state["document"] = loaded_document.to_dict()
            structure_meta = loaded_document.metadata.get("slide_structure")
            if structure_meta:
                st.session_state["slide_structure"] = structure_meta
                st.session_state["slide_structure_editor"] = structure_meta

        with st.expander("テンプレート一覧", expanded=False):
            for asset in assets[:20]:
                st.markdown(
                    f"- **{asset.asset_id}**: {asset.description[:80]}…"
                )
            if len(assets) > 20:
                st.caption(f"他 {len(assets) - 20} 件のテンプレートがあります。")

    st.subheader("ユーザーとの対話情報")
    conversation_history = st.text_area(
        "対話ログ",
        height=180,
        placeholder="例：ユーザーと交わした要件整理のメモを貼り付けてください",
    )
    goal_input = st.text_area(
        "最終的な依頼内容 / ゴール",
        height=140,
        placeholder="例：競合A社に対する最新の進捗報告資料を作成したい",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        target_company = st.text_input("ターゲット企業 / 想定読者", value="")
        external_research = st.text_area(
            "外部リサーチ要約 (任意)",
            height=120,
            placeholder="Web検索や社外資料の要約を貼り付けます",
        )
    with col_b:
        additional_notes = st.text_area(
            "補足指示 (任意)",
            height=120,
            placeholder="強調したいポイントや除外したい内容など",
        )
        internal_override = st.checkbox(
            "内部ドキュメントを読み込まない",
            help="チェックすると内部ドキュメントの読み込みをスキップします。",
        )

    st.subheader("スライド構成の設定")
    structure_mode = st.radio(
        "スライド構成の入力方法",
        ("対話から生成", "手動入力"),
        index=0,
        horizontal=True,
    )

    placeholder_text = (
        "例：1. 表紙で狙いを明示\n2. 進捗ハイライト\n3. 次のアクション"
        if structure_mode == "手動入力"
        else "ボタンで自動生成後に必要に応じて編集できます"
    )

    slide_structure_editor = st.text_area(
        "スライド構成 (自動生成後に編集可能)",
        key="slide_structure_editor",
        height=160,
        placeholder=placeholder_text,
    )
    st.session_state["slide_structure"] = slide_structure_editor

    step_cols = st.columns(3)

    with step_cols[0]:
        if st.button("1. スライド構成を生成 / 適用", type="primary"):
            if structure_mode == "手動入力":
                manual_structure = st.session_state.get("slide_structure_editor", "").strip()
                if not manual_structure:
                    st.error("手動入力モードではスライド構成を入力してください。")
                else:
                    st.session_state["slide_structure"] = manual_structure
                    st.session_state["slide_structure_editor"] = manual_structure
                    st.session_state["document"] = None
                    st.session_state["preview_index"] = 1
                    st.success("手動入力したスライド構成を適用しました。")
            else:
                if not conversation_history or not goal_input:
                    st.error("対話ログとゴールの両方を入力してください。")
                else:
                    llm_client = _instantiate_llm(llm_option, library)
                    if llm_client is None:
                        st.info("LLMクライアントを初期化できなかったため、スタブ生成を利用します。")
                        llm_client = StubStructuredOutputLLM(slide_library=library)
                    planner = SlideStructurePlanner(llm_client)
                    planning_context = PlanningContext(
                        conversation_history=conversation_history,
                        goal=goal_input,
                        target_company=target_company or None,
                        additional_requirements=additional_notes or None,
                    )
                    try:
                        structure_text = planner.build_structure(planning_context)
                        st.session_state["slide_structure"] = structure_text
                        st.session_state["slide_structure_editor"] = structure_text
                        st.session_state["document"] = None
                        st.session_state["preview_index"] = 1
                        st.success("スライド構成を生成しました。必要に応じて編集してください。")
                    except Exception as exc:
                        st.error("スライド構成の生成中にエラーが発生しました。")
                        st.exception(exc)

    with step_cols[1]:
        if st.button("2. スライドアウトラインを生成", type="secondary"):
            structure_text = st.session_state.get("slide_structure", "")
            if not structure_text.strip():
                st.error("先にスライド構成を生成するか、手動で入力してください。")
            else:
                llm_client = _instantiate_llm(llm_option, library)
                if llm_client is None:
                    st.info("LLMクライアントを初期化できなかったため、スタブ生成を利用します。")
                    llm_client = StubStructuredOutputLLM(slide_library=library)
                outline_generator = SlideOutlineGenerator(library, llm_client=llm_client)
                outline_context = GenerationContext(
                    user_request=goal_input or structure_text,
                    target_company=target_company or None,
                    additional_notes=additional_notes or None,
                )
                try:
                    document = outline_generator.generate_outline(
                        slide_structure=structure_text,
                        context=outline_context,
                    )
                    st.session_state["document"] = document.to_dict()
                    st.session_state["preview_index"] = 1
                    st.success("スライドアウトラインを生成しました。")
                except Exception as exc:
                    st.error("スライドアウトラインの生成中にエラーが発生しました。")
                    st.exception(exc)

    with step_cols[2]:
        if st.button("3. プレースホルダーを埋める", type="secondary"):
            document_data = st.session_state.get("document")
            if not document_data:
                st.error("先にスライドアウトラインを生成してください。")
            else:
                llm_client = _instantiate_llm(llm_option, library)
                if llm_client is None:
                    st.info("LLMクライアントを初期化できなかったため、スタブ生成を利用します。")
                    llm_client = StubStructuredOutputLLM(slide_library=library)
                content_generator = SlideContentGenerator(
                    library,
                    llm_client=llm_client,
                    internal_document_path=Path("data/internal_report.md"),
                )
                document = SlideDocument.from_dict(document_data)
                generation_context = GenerationContext(
                    user_request=goal_input or st.session_state.get("slide_structure", ""),
                    target_company=target_company or None,
                    external_research=external_research or None,
                    additional_notes=additional_notes or None,
                    internal_document=(
                        "内部ドキュメントの参照は不要です。" if internal_override else None
                    ),
                    perform_web_search=perform_web_search,
                )
                try:
                    updated_document = content_generator.generate_for_document(
                        document,
                        context=generation_context,
                    )
                    st.session_state["document"] = updated_document.to_dict()
                    st.session_state["preview_index"] = 1
                    st.success("プレースホルダーを更新しました。")
                except Exception as exc:
                    st.error("プレースホルダー生成中にエラーが発生しました。")
                    st.exception(exc)

    st.divider()

    document_data = st.session_state.get("document")
    if document_data:
        document = SlideDocument.from_dict(document_data)
        if not document.slides:
            st.info("スライドアウトラインが空です。構成の再生成を試してください。")
        else:
            st.subheader("生成結果")
            tabs = st.tabs(
                [
                    f"{idx + 1}. {slide.title or slide.asset_id}"
                    for idx, slide in enumerate(document.slides)
                ]
            )
            for tab, slide in zip(tabs, document.slides):
                with tab:
                    st.markdown(f"**テンプレートID**: `{slide.asset_id}`")
                    st.markdown(f"**テンプレートファイル**: {slide.asset_file}")
                    st.markdown(f"**タイトル**: {slide.title or '未設定'}")
                    if slide.notes.get("outline_notes"):
                        st.info(f"アウトラインメモ: {slide.notes['outline_notes']}")
                    if slide.notes.get("summary"):
                        st.success(f"スライド要約: {slide.notes['summary']}")
                    st.markdown("**プレースホルダー**")
                    if not slide.placeholders:
                        st.write("未生成です。ステップ3を実行してください。")
                    else:
                        for placeholder in slide.placeholders:
                            st.markdown(
                                f"- **{placeholder.name} ({placeholder.policy})**: {placeholder.text or '未生成'}"
                            )
                            if placeholder.references:
                                st.caption(
                                    "参照: " + ", ".join(sorted(set(placeholder.references)))
                                )

            citations = document.metadata.get("references", [])
            if citations:
                st.markdown("#### 参考文献")
                for ref in citations:
                    st.markdown(f"- {ref}")

            json_payload = json.dumps(document.to_dict(), ensure_ascii=False, indent=2)
            st.download_button(
                "slide.jsonをダウンロード",
                data=json_payload.encode("utf-8"),
                file_name="slide.json",
                mime="application/json",
            )

            pptx_bytes = None
            try:
                pptx_buffer = renderer.render_document(document)
                pptx_bytes = pptx_buffer.getvalue()
            except Exception as exc:  # pragma: no cover - depends on assets
                st.warning("PPTX生成に失敗しました。詳細は下記ログを確認してください。")
                st.exception(exc)

            if pptx_bytes:
                max_slides = len(document.slides)
                default_preview = st.session_state.get("preview_index", 1)
                default_preview = max(1, min(default_preview, max_slides))
                if st.session_state.get("preview_index") != default_preview:
                    st.session_state["preview_index"] = default_preview
                preview_index = st.number_input(
                    "プレビューするスライド番号",
                    min_value=1,
                    max_value=max_slides,
                    value=default_preview,
                    key="preview_index",
                    step=1,
                )
                preview_bytes = renderer.render_preview_image(
                    document,
                    pptx_bytes=pptx_bytes,
                    slide_index=int(preview_index) - 1,
                )
                if preview_bytes:
                    st.image(
                        preview_bytes,
                        caption=f"スライド {int(preview_index)} プレビュー",
                        use_container_width=True,
                    )
                else:
                    st.info(
                        "プレビュー画像を生成できませんでした。LibreOfficeのインストール状況を確認してください。"
                    )

                st.download_button(
                    "PPTXをダウンロード",
                    data=pptx_bytes,
                    file_name="generated_slides.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )

            save_to_disk = st.checkbox("slide.jsonをプロジェクト内に保存", value=False)
            if save_to_disk:
                output_path = Path("output/slide.json")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                _save_document(document, output_path)
                st.success(f"{output_path} に保存しました。")

    st.caption("各ステップは独立して実行できます。必要に応じて構成を編集した上で再生成してください。")


if __name__ == "__main__":  # pragma: no cover - Streamlit handles execution
    main()
