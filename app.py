"""Streamlit UI for interacting with the GEOTRA slide generation pipeline."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

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

from LLM_API.data_classes import StructuredOutputRequest, StructuredOutputResponse

from geotra_slide.slide_document import SlideDocumentStore
from geotra_slide.slide_generation import GenerationContext, SlideContentGenerator
from geotra_slide.slide_library import SlideLibrary, SlideAsset
from geotra_slide.slide_models import SlideDocument, SlidePage
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

    def __init__(self, *, summary: str = "スタブ生成によるスライド概要") -> None:
        self.summary = summary

    def generate_structured_output(self, request: StructuredOutputRequest) -> StructuredOutputResponse:
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
                    "references": [],
                }
            )

        parsed = {
            "slide_summary": self.summary,
            "citations": [],
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


def _instantiate_llm(choice: str):
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
    return StubStructuredOutputLLM()


def _asset_display_name(asset: SlideAsset) -> str:
    tags = ", ".join(asset.tags)
    return f"{asset.asset_id}｜{asset.description}{'｜' + tags if tags else ''}"


def _load_document_from_upload(upload) -> Optional[SlideDocument]:
    if upload is None:
        return None
    data = json.load(upload)
    return SlideDocument.from_dict(data)


def _build_slide_page(asset: SlideAsset, *, title: Optional[str]) -> SlidePage:
    return SlidePage(
        slide_id="slide_01",
        page_number=1,
        asset_id=asset.asset_id,
        asset_file=asset.file_name,
        title=title or asset.description,
    )


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
    assets_map = {asset.asset_id: asset for asset in assets}

    with st.sidebar:
        st.header("スライド設定")
        asset_id = st.selectbox(
            "使用するスライドアセット",
            options=list(assets_map.keys()),
            format_func=lambda key: _asset_display_name(assets_map[key]),
        )
        selected_asset = assets_map[asset_id]

        title_input = st.text_input("スライドタイトル", value=selected_asset.description)

        llm_option = st.radio(
            "生成モード",
            ("スタブ生成", "OpenAI (環境変数)"),
            index=0,
            help="OpenAIキーが未設定の場合はスタブ生成を利用してください。",
        )

        uploaded = st.file_uploader("既存のslide.jsonを読み込む", type="json")
        loaded_document = _load_document_from_upload(uploaded)
        if loaded_document:
            st.success("slide.jsonを読み込みました。下部で内容を確認できます。")
            st.session_state["document"] = loaded_document.to_dict()

        with st.expander("テンプレートのプレースホルダー", expanded=False):
            for placeholder in selected_asset.placeholders:
                st.markdown(
                    f"**{placeholder.name}** — {placeholder.edit_policy}\n{placeholder.description}"
                )

    st.subheader("ユーザー入力")
    user_request = st.text_area(
        "相談・依頼内容",
        height=150,
        placeholder="例：競合A社の環境施策に関する進捗報告をまとめたい",
    )
    col1, col2 = st.columns(2)
    with col1:
        target_company = st.text_input("ターゲット企業 / 想定読者", value="")
        external_research = st.text_area(
            "外部リサーチ要約 (任意)",
            height=120,
            placeholder="Web検索や資料の要約を貼り付けます",
        )
    with col2:
        additional_notes = st.text_area(
            "補足指示 (任意)",
            height=120,
            placeholder="特に強調したいポイントや制約条件を入力",
        )
        internal_override = st.checkbox(
            "内部ドキュメントを読み込まない",
            help="チェックすると内部ドキュメントの読み込みをスキップします。",
        )

    if "document" in st.session_state:
        document = SlideDocument.from_dict(st.session_state["document"])
    else:
        slide = _build_slide_page(selected_asset, title=title_input)
        document = SlideDocument(slides=[slide], metadata={})

    if st.button("スライドを生成", type="primary"):
        if not user_request:
            st.error("まずは相談内容を入力してください。")
        else:
            llm_client = _instantiate_llm(llm_option)
            if llm_client is None:
                st.info("LLMクライアントを初期化できなかったため、スタブ生成を利用します。")
                llm_client = StubStructuredOutputLLM()
            generator = SlideContentGenerator(
                library,
                llm_client=llm_client,
                internal_document_path=Path("data/internal_report.md"),
            )
            slide = document.get_slide("slide_01")
            if slide is None:
                slide = _build_slide_page(selected_asset, title=title_input)
                document.upsert_slide(slide)
            context = GenerationContext(
                user_request=user_request,
                target_company=target_company or None,
                external_research=external_research or None,
                additional_notes=additional_notes or None,
                internal_document=(
                    "内部ドキュメントの参照は不要です。"
                    if internal_override
                    else None
                ),
            )
            try:
                updated_document = generator.generate_for_slide(
                    document,
                    slide_id=slide.slide_id,
                    context=context,
                )
                st.session_state["document"] = updated_document.to_dict()
                st.success("スライド内容を更新しました。")
            except Exception as exc:
                st.error("スライド生成中にエラーが発生しました。")
                st.exception(exc)

    st.divider()

    if "document" in st.session_state:
        document = SlideDocument.from_dict(st.session_state["document"])
        slide = document.get_slide("slide_01")
        if slide:
            st.subheader("生成結果")
            if slide.title:
                st.markdown(f"### {slide.title}")
            for placeholder in slide.placeholders:
                st.markdown(f"**{placeholder.name} ({placeholder.policy})**")
                st.write(placeholder.text or "未生成")
                if placeholder.references:
                    st.caption("参照: " + ", ".join(placeholder.references))
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
            preview_bytes = None
            try:
                pptx_buffer = renderer.render_document(document)
                pptx_bytes = pptx_buffer.getvalue()
                preview_bytes = renderer.render_preview_image(
                    document, pptx_bytes=pptx_bytes
                )
            except Exception as exc:  # pragma: no cover - depends on assets
                st.warning("PPTX生成に失敗しました。詳細は下記ログを確認してください。")
                st.exception(exc)

            if pptx_bytes:
                if preview_bytes:
                    st.image(preview_bytes, caption="スライドプレビュー", use_column_width=True)
                else:
                    st.info(
                        "プレビュー画像を生成できませんでした。LibreOfficeのインストール状況を確認してください。"
                    )

                st.download_button(
                    "PPTXをダウンロード",
                    data=pptx_bytes,
                    file_name="generated_slide.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )

            save_to_disk = st.checkbox("slide.jsonをプロジェクト内に保存", value=False)
            if save_to_disk:
                output_path = Path("output/slide.json")
                _save_document(document, output_path)
                st.success(f"{output_path} に保存しました。")

    st.caption("OpenAIキーが未設定の場合はスタブ生成モードでプレースホルダーの流れを確認できます。")


if __name__ == "__main__":  # pragma: no cover - Streamlit handles execution
    main()
