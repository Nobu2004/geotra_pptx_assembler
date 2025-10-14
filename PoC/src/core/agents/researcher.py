# src/core/agents/researcher.py

from typing import List, Dict
import re
from .. import schemas
from ..tools.file_search import markdown_search_tool
from ..tools.web_search import web_search_tool

def research_agent_node(state: schemas.GraphState) -> Dict[str, schemas.ResearchReport]:
    """
    リサーチャーエージェントとして機能するLangGraphのノード。
    ユーザーの要求に基づいて内部文書とウェブを検索し、結果を統合して
    一つのResearchReportを作成する。

    Args:
        state: 現在のGraphState。'initial_user_request' を使用する。

    Returns:
        更新されたStateの一部。'research_report' キーを含む辞書。
    """
    print("--- 🕵️ リサーチャーエージェントを実行中... ---")
    
    query = state.get("initial_user_request")
    if not query:
        # この状況は通常発生しないが、安全のためのガード節
        print("  [警告] リサーチクエリが見つかりません。リサーチをスキップします。")
        return {}

    # --- 責務の分離: 各ツールを独立して呼び出す ---
    # 1. 内部文書の検索（全体）
    internal_findings = markdown_search_tool.search(query)
    print(f"  内部文書から {len(internal_findings)} 件の情報を発見しました。")

    # 2. ウェブの検索
    web_findings = web_search_tool.search(query)
    print(f"  ウェブから {len(web_findings)} 件の情報を発見しました。")
    
    # 3. 結果の統合
    all_findings = internal_findings + web_findings
    if not all_findings:
        print("  [情報] 関連する情報は見つかりませんでした。")
        # 空のレポートでも、後続の処理のためにスキーマに沿ったオブジェクトを返す
        report = schemas.ResearchReport(findings=[], summary="関連情報は見つかりませんでした。")
    else:
        # ここでLLMを呼び出し、発見した全情報から要約を生成することも可能（将来的な拡張）
        # 現段階では、発見した情報の件数を要約とする
        summary_text = (
            f"合計 {len(all_findings)} 件の関連情報を発見しました。\n"
            f"内訳: 内部文書 {len(internal_findings)} 件, ウェブ {len(web_findings)} 件。"
        )
        report = schemas.ResearchReport(findings=all_findings, summary=summary_text)

    # 4. スライドごとの内部要約を作成
    slide_summaries: Dict[str, str] = {}
    blueprints = state.get("slide_blueprints", [])
    for bp in blueprints:
        sq = getattr(bp, "search_query", None) or f"{bp.slide_title} {query}"
        bp_findings = markdown_search_tool.search(sq, top_k=3)
        if not bp_findings:
            slide_summaries[bp.slide_id] = "関連する要約は見つかりませんでした。"
            continue
        # 簡易要約: 連結→句点で分割→スコア付け→上位3文を再構成
        joined = " ".join([f.content for f in bp_findings])
        sentences = [s.strip() for s in re.split(r"[。\.]", joined) if len(s.strip()) > 10]
        # スコア: 名詞らしきトークン頻度の合計
        def tokenize(t: str) -> List[str]:
            return [w for w in re.split(r"[\s、，,・:：;；()（）\-]+", t) if len(w) >= 2]
        freq: Dict[str, int] = {}
        for s in sentences:
            for w in tokenize(s):
                freq[w] = freq.get(w, 0) + 1
        scored = []
        for s in sentences:
            score = sum(freq.get(w, 0) for w in tokenize(s))
            scored.append((score, s))
        scored.sort(reverse=True)
        top = [s for _, s in scored[:3]]
        if not top:
            slide_summaries[bp.slide_id] = "関連する要約は見つかりませんでした。"
        else:
            # 2-3文で統合要約
            y = []
            for s in top:
                s = re.sub(r"(といった|など).*", "などを整理。", s)
                y.append(s)
            slide_summaries[bp.slide_id] = "。".join(y)[:300]

    print("--- ✅ リサーチレポートが完成しました ---")
    return {"research_report": report, "slide_summaries": slide_summaries}

