# src/core/tools/llm.py

import os
from typing import List, Optional

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
except Exception:
    ChatGoogleGenerativeAI = None  # type: ignore
    HumanMessage = None  # type: ignore


def _get_llm() -> Optional["ChatGoogleGenerativeAI"]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or ChatGoogleGenerativeAI is None:
        return None
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.2,
            max_output_tokens=512,
        )
        return llm
    except Exception:
        return None


def summarize_map_reduce(chunks: List[str], instruction: str) -> Optional[str]:
    """LLMが使えれば、map-reduceで要約を返す。使えなければNone。

    instruction: 日本語での要約方針（箇条書き/短文など）を含むテキスト
    """
    llm = _get_llm()
    if llm is None or not chunks:
        return None
    try:
        # map: 各チャンクを短く要約
        mapped: List[str] = []
        for chunk in chunks:
            msg = HumanMessage(
                content=(
                    "以下の内容を日本語で2文以内に要約してください。重要語を残し、口語は排除:\n\n" + chunk
                )
            )
            resp = llm.invoke([msg])
            mapped.append(str(resp.content).strip())

        # reduce: 全体統合
        joined = "\n".join(mapped)
        reduce_msg = HumanMessage(
            content=(
                "以下の要点群を統合し、" + instruction + " 日本語で最大3文にまとめてください。\n\n" + joined
            )
        )
        final = llm.invoke([reduce_msg])
        return str(final.content).strip()
    except Exception:
        return None


def generate_placeholder_text(summary: str, description: str, constraints: dict) -> Optional[str]:
    """LLMが使えれば、プレースホルダー向けの短文を生成して返す。なければNone。"""
    llm = _get_llm()
    if llm is None:
        return None
    try:
        style = constraints.get("mode", "paragraph")
        max_len = constraints.get("max_len", 120)
        bullet_count = constraints.get("bullet_count", 3)
        noun_phrase = constraints.get("noun_phrase", False)

        style_instr = {
            "title": f"1文の短いタイトル（最大{max_len}文字）",
            "label": f"名詞句の短いラベル（最大{max_len}文字）",
            "bullets": f"箇条書き{bullet_count}点。各行は{max_len}文字以内",
            "paragraph": f"1段落（最大{max_len}文字）",
        }.get(style, f"1段落（最大{max_len}文字）")

        noun_note = "名詞句のみで表現してください。" if noun_phrase else ""

        prompt = (
            "あなたは日本語のプレゼン資料ライターです。\n"
            "与えられた要約とプレースホルダーの目的に従い、簡潔で明確な文を生成します。\n"
            "禁止: 逐語引用、会話調、冗長表現。\n"
            f"出力形式: {style_instr}。{noun_note}\n\n"
            f"[要約]\n{summary}\n\n[プレースホルダーの目的]\n{description}\n\n"
            "出力のみ返してください。余計な説明は不要です。"
        )
        resp = llm.invoke([HumanMessage(content=prompt)])
        return str(resp.content).strip()
    except Exception:
        return None


