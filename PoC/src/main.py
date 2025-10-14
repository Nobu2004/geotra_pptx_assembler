# src/main.py

import streamlit as st
import base64
import tempfile
from pathlib import Path
import time

from core.graph import create_graph
from core.renderer import PPTXRenderer
from core import schemas
from core import pptx_utils

# --- アプリケーション設定 ---
st.set_page_config(page_title="AIリサーチ・アシスタント", layout="wide")

# --- ヘルパー関数 (変更なし) ---
def get_pptx_download_link(pptx_bytes: bytes, filename: str) -> str:
    b64 = base64.b64encode(pptx_bytes).decode()
    return f'<a href="data:application/vnd.openxmlformats-officedocument.presentationml.presentation;base64,{b64}" download="{filename}">📥 プレゼンテーションをダウンロード</a>'

# (プレビュー生成関数は簡略化のため省略)

# --- 状態管理 ---
@st.cache_resource
def load_core_logic():
    return create_graph(), PPTXRenderer()

st.session_state.graph, st.session_state.renderer = load_core_logic()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "こんにちは！どのようなプレゼンテーションを作成しますか？まずは「consult」モードでご相談ください。"}]
if "graph_state" not in st.session_state:
    st.session_state.graph_state = None

# --- UI ---
st.title("🤖 意思決定を支援する知的リサーチ・アシスタント")

# --- サイドバー: スライド一覧とプレビュー選択 ---
with st.sidebar:
    st.header("スライド一覧")
    selected_slide_id = None
    if st.session_state.get("graph_state") and st.session_state.graph_state.get("slide_blueprints"):
        blueprints = st.session_state.graph_state["slide_blueprints"]
        titles = [f"{i+1}. {bp.slide_title}" for i, bp in enumerate(blueprints)]
        ids = [bp.slide_id for bp in blueprints]
        default_idx = st.session_state.graph_state.get("active_slide_index", 0)
        choice = st.selectbox("プレビューするスライド", options=list(zip(ids, titles)), index=min(default_idx, len(ids)-1), format_func=lambda x: x[1] if isinstance(x, tuple) else x)
        if isinstance(choice, tuple):
            selected_slide_id = choice[0]
        else:
            selected_slide_id = ids[0] if ids else None
        st.session_state.graph_state["active_slide_index"] = ids.index(selected_slide_id) if selected_slide_id in ids else 0
    else:
        st.info("構成案ができると、ここにスライド一覧が表示されます。")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("💬 チャット")
    
    # --- ▼▼▼ 新UI: モード選択と承認ボタン ---
    # 承認待ち状態かどうかを判断
    plan_proposed = bool(st.session_state.graph_state) and (not st.session_state.graph_state.get("is_plan_confirmed", False))
    # Chat入力の無効化フラグは常に厳密なboolにする
    disabled_chat_input = True if plan_proposed is True else False

    if plan_proposed:
        st.info("AIがプレゼンテーションの構成案を提示しました。内容を確認し、実行を承認してください。")
        if st.button("👍 この構成でスライド生成を開始する", type="primary"):
            # 承認フラグを立てて即時にグラフを継続実行
            st.session_state.graph_state["is_plan_confirmed"] = True
            with st.spinner("承認されました。AIチームがリサーチと執筆を開始します..."):
                final_state = st.session_state.graph.invoke(st.session_state.graph_state)
                st.session_state.graph_state = final_state
            st.session_state.messages.append({"role": "assistant", "content": "リサーチと執筆が完了しました。プレビューをご確認ください。"})
            st.rerun()
    else:
        mode = st.radio(
            "モード選択:",
            (schemas.DialogueMode.CONSULT.value, schemas.DialogueMode.EDIT.value),
            horizontal=True, captions=["AIへの相談・壁打ち", "スライドの生成・修正指示"]
        )
        st.session_state.dialogue_mode = schemas.DialogueMode(mode)
    # --- ▲▲▲ UIここまで ---

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("メッセージを入力してください", disabled=disabled_chat_input):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # --- ▼▼▼ 新ロジック: 状態に応じたワークフロー実行 ---
            if st.session_state.dialogue_mode == schemas.DialogueMode.CONSULT:
                with st.spinner("思考中です..."):
                    time.sleep(1) # TODO: LLM call
                    response = f"相談ですね。「{prompt}」について..."
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

            elif st.session_state.graph_state and st.session_state.graph_state.get("is_plan_confirmed"):
                # 承認後の実行
                with st.spinner("承認されました。AIチームがリサーチと執筆を開始します..."):
                    # 承認フラグが立った状態で、再度グラフを呼び出す
                    final_state = st.session_state.graph.invoke(st.session_state.graph_state)
                    st.session_state.graph_state = final_state
                response = f"リサーチと執筆が完了しました。プレビューをご確認ください。"
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

            else: # 最初のEDITモードでの指示
                with st.spinner("AIチームがプレゼンテーションの構成を計画中です..."):
                    initial_state = {
                        "initial_user_request": prompt,
                        "messages": st.session_state.messages,
                        "is_plan_confirmed": False,
                    }
                    # グラフを呼び出すと、計画を立てた後、承認待ちで一旦停止する
                    intermediate_state = st.session_state.graph.invoke(initial_state)
                    st.session_state.graph_state = intermediate_state
                
                response = intermediate_state.get("deck_plan_summary", "エラー：計画を立てられませんでした。")
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            # --- ▲▲▲ ロジックここまで ---
        st.rerun()

with col2:
    st.subheader("🖼️ プレビュー")
    if st.session_state.graph_state and st.session_state.graph_state.get("slide_blueprints"):
        blueprints = st.session_state.graph_state["slide_blueprints"]
        if blueprints:
            # 選択されたスライドのテキストプレビュー（content_write_log）
            selected_idx = st.session_state.graph_state.get("active_slide_index", 0)
            selected_idx = max(0, min(selected_idx, len(blueprints)-1))
            selected_bp = blueprints[selected_idx]

            # 直近生成結果のログがあれば、該当スライドのみ表示
            write_log = st.session_state.graph_state.get("content_write_log", [])
            if write_log:
                st.caption("このスライドに書き込んだプレースホルダーと内容")
                for entry in write_log:
                    if entry.get("slide_id") == selected_bp.slide_id:
                        st.markdown(f"- [{entry.get('policy')}] {entry.get('placeholder_name')}: {entry.get('content')}")

            # PPTXのダウンロードリンクは常に提供
            pptx_bytes = st.session_state.renderer.render_presentation(blueprints).getvalue()
            st.markdown(get_pptx_download_link(pptx_bytes, "generated_presentation.pptx"), unsafe_allow_html=True)
            st.success(f"{len(blueprints)}枚のスライドが生成済みです。サイドバーから閲覧スライドを選択できます。")
    else:
        st.info("ここにスライドのプレビューが表示されます。")
