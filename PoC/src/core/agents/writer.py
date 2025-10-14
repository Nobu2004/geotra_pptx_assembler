# src/core/agents/writer.py

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from .. import schemas
from ..tools.file_search import markdown_search_tool

# ( _create_writer_prompt, _parse_llm_output は変更なし)
def _create_writer_prompt(report: schemas.ResearchReport, blueprint: schemas.SlideBlueprint, asset_info: dict) -> str:
    prompt = f"""あなたはプロのプレゼンテーションライターです。
以下のリサーチ結果とスライドの設計指示に基づき、各プレースホルダーに挿入するテキストを生成してください。

# リサーチ結果の要約
{report.summary}

# リサーチ結果の詳細
"""
    for i, finding in enumerate(report.findings):
        prompt += f"[{i+1}] {finding.content} (出典: {finding.source})\n"

    prompt += f"""
# スライドの設計指示
スライドタイトル: {blueprint.slide_title}
スライドの目的: {asset_info.get('description', 'N/A')}

以下のプレースホルダーの 'content' を生成してください。
- 各プレースホルダーの目的を厳密に守ってください。
- リサーチ結果を最大限に活用し、主張には必ず出典 `[番号]` を含めてください。
- 出力は必ず指定されたJSON形式に従ってください。

[
"""
    for content_item in blueprint.content_map:
        ph_name = content_item.placeholder_name
        ph_asset_info = next((ph for ph in asset_info.get("placeholders", []) if ph["name"] == ph_name), None)
        if ph_asset_info and ph_asset_info.get("edit_policy") == "generate":
            ph_description = ph_asset_info.get("description", "（目的不明）")
            prompt += f'  {{ "placeholder_name": "{ph_name}", "content": "（{ph_description}）" }},\n'
    prompt += "]\n"
    return prompt

def _parse_llm_output(response_str: str) -> List[schemas.PlaceholderContent]:
    try:
        parsed_list = json.loads(response_str)
        return [schemas.PlaceholderContent(**item) for item in parsed_list]
    except (json.JSONDecodeError, TypeError) as e:
        print(f"!!! LLM出力のパースに失敗しました: {e}")
        print(f"  不正な出力: {response_str}")
        return []


def _extract_target_entity(user_request: Optional[str]) -> Optional[str]:
    if not user_request:
        return None
    # 単純規則: 「Xの」や「X社」の X を抽出
    m = re.search(r"([A-Za-z0-9一-龥ァ-ヿー]+)の", user_request)
    if m:
        return m.group(1)
    m = re.search(r"([A-Za-z0-9一-龥ァ-ヿー]+)社", user_request)
    if m:
        return m.group(1)
    m = re.match(r"^([A-Z]{2,})", user_request.strip())
    if m:
        return m.group(1)
    return None


def _generate_fixed_text(description: str) -> str:
    # 「〜と記載/記述」などの前までを抽出
    m = re.search(r"(.+?)と記載", description)
    if m:
        return m.group(1).strip()
    m = re.search(r"(.+?)と記述", description)
    if m:
        return m.group(1).strip()
    return description.strip()


def _generate_populate_text(description: str, user_request: Optional[str]) -> str:
    company = _extract_target_entity(user_request) or "御社"
    ym = datetime.now().strftime("%Y.%m")
    text = description
    # よくある置換: 相手企業名、年月
    text = re.sub(r"相手企業名\+?", company, text)
    text = re.sub(r"相手企業名", company, text)
    text = re.sub(r"20XX\.Y|20XXY|YYYY\.M|20XX\.M|20XX/\d{1,2}", ym, text)
    return _generate_fixed_text(text)


def _tokenize(text: str) -> List[str]:
    # 日本語・英数混在の簡易トークナイズ
    if not text:
        return []
    # 句読点や記号で分割
    parts = re.split(r"[\s\n、。,.；;:：()（）\-\[\]{}]+", text)
    # 短すぎる語を除外
    return [p for p in parts if len(p) >= 2]


def _select_relevant_findings(report: schemas.ResearchReport, name: str, description: str, top_k: int = 3) -> List[Tuple[schemas.ResearchFinding, int]]:
    query_terms = set(_tokenize((name or "") + " " + (description or "")))
    if not query_terms:
        return [(f, 0) for f in report.findings[:top_k]]
    scored: List[Tuple[schemas.ResearchFinding, int]] = []
    for f in report.findings:
        text = f.content
        score = sum(text.count(term) for term in query_terms)
        scored.append((f, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def _decide_style(description: str) -> dict:
    desc = description or ""
    style = {
        "mode": "bullets",  # bullets | label | paragraph | title
        "max_len": 90,
        "bullet_count": 3,
    }
    if re.search(r"タイトル|title", desc, re.IGNORECASE):
        style["mode"] = "title"
        style["max_len"] = 24
    if re.search(r"名称|ラベル|一言|短く|\d+字", desc):
        style["mode"] = "label"
        # 数値指定
        m = re.search(r"(\d+)字", desc)
        if m:
            style["max_len"] = int(m.group(1))
        else:
            style["max_len"] = 20
    if re.search(r"箇条書き|項目|リスト", desc):
        style["mode"] = "bullets"
        m = re.search(r"(\d+)項目|最大(\d+)件", desc)
        if m:
            style["bullet_count"] = int(next(g for g in m.groups() if g))
    if re.search(r"本文|説明|背景|詳細", desc):
        style["mode"] = "paragraph"
        style["max_len"] = 120
    return style


def _build_placeholder_query(slide_title: str, asset_info: dict, description: str, user_request: str, slide_summary: str | None) -> str:
    tags = " ".join(asset_info.get("tags", []))
    category = asset_info.get("category", "")
    base = " ".join(filter(None, [slide_title, category, tags, description, user_request]))
    if slide_summary:
        base = base + " " + slide_summary
    return base[:500]


def _summarize_for_placeholder(report: schemas.ResearchReport, placeholder_name: str, description: str) -> str:
    # タイトル系は短く
    if re.search(r"title|タイトル", placeholder_name, re.IGNORECASE):
        base = description or (report.summary or "")
        base = re.sub(r"[\n\s]+", " ", base).strip()
        base = re.sub(r"(を記載.*)$", "", base)
        return (base[:24] + "…") if len(base) > 24 else base

    # 関連度の高い finding から要約
    picked = _select_relevant_findings(report, placeholder_name, description, top_k=5)
    # picked から抽象度の高い統合要約を作る
    raw = " ".join([f.content for f, _ in picked])
    # 文に分割
    sents = [s.strip() for s in re.split(r"[。\.]+", raw) if len(s.strip()) > 12]
    # キーフレーズ抽出（頻出語）
    tokens = _tokenize(raw)
    freq: Dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    # スコアリングして上位文を選択
    scored: List[Tuple[int, str]] = []
    for s in sents:
        score = sum(freq.get(w, 0) for w in _tokenize(s))
        # 口語・不要語を抑制
        if re.search(r"(えー|あの|えっと|ですね|ですか|はい|ええ)", s):
            continue
        scored.append((score, s))
    scored.sort(reverse=True)
    top = [s for _, s in scored[:3]]
    if top:
        # 抽象化: 箇条書きではなく一文に寄せる
        abstract = " / ".join([re.sub(r"(といった|など).*", "など。", s) for s in top])
        abstract = re.sub(r"\s+", " ", abstract)
        return abstract[:120]

    base = (report.summary or description or "").strip()
    base = re.sub(r"[\n\s]+", " ", base)
    return base[:100]


def _generate_from_report(report: schemas.ResearchReport, placeholder_name: str, description: str) -> str:
    # タイトル系: 説明→要約→短文化
    if re.search(r"title|タイトル", placeholder_name, re.IGNORECASE):
        base = description or (report.summary or "")
        base = re.sub(r"[\n\s]+", " ", base).strip()
        # 末尾の「〜を記載」系は落とす
        base = re.sub(r"(を記載.*)$", "", base)
        return (base[:24] + "…") if len(base) > 24 else base

    # 本文系: プレースホルダー固有の関連情報から要約
    return _summarize_for_placeholder(report, placeholder_name, description)


def writer_agent_node(state: schemas.GraphState, renderer) -> Dict[str, List[schemas.SlideBlueprint]]:
    print("--- ✍️ ライターエージェントを実行中... ---")
    report = state.get("research_report")
    slide_summaries: Dict[str, str] = state.get("slide_summaries", {})
    current_blueprints = state.get("slide_blueprints", [])

    if not report or not current_blueprints:
        print("  [警告] レポートまたは設計図が存在しないため、執筆をスキップします。")
        return {}
    
    updated_blueprints: List[schemas.SlideBlueprint] = []
    content_write_log: List[Dict] = []
    user_request = state.get("initial_user_request")

    for blueprint in current_blueprints:
        asset_info = renderer.slide_asset_map.get(blueprint.asset_id)
        if not asset_info:
            updated_blueprints.append(blueprint)
            continue

        manifest_placeholders = asset_info.get("placeholders", [])

        # 既存の content_map を辞書化
        content_map_by_name: Dict[str, schemas.PlaceholderContent] = {
            item.placeholder_name: item for item in blueprint.content_map
        }

        used_sentences: set[str] = set()
        # 各プレースホルダーの policy に沿って内容決定
        for ph in manifest_placeholders:
            ph_name = ph.get("name", "")
            edit_policy = ph.get("edit_policy", "generate")
            description = ph.get("description", "")

            if edit_policy == "fixed":
                content_text = _generate_fixed_text(description)
            elif edit_policy == "populate":
                content_text = _generate_populate_text(description, user_request)
            else:  # generate
                # スライド固有の要約＋プレースホルダー由来の検索クエリで再検索
                slide_summary = slide_summaries.get(blueprint.slide_id)
                query = _build_placeholder_query(blueprint.slide_title, asset_info, description, user_request or "", slide_summary)
                local_findings = markdown_search_tool.search(query, top_k=5) or []
                # ローカルファインディングがあればそれを主に使い、なければ全体レポート
                if local_findings:
                    temp_report = schemas.ResearchReport(findings=local_findings, summary=slide_summary or report.summary)
                    content_text = _generate_from_report(temp_report, ph_name, description)
                else:
                    content_text = _generate_from_report(report, ph_name, description)

                # スタイル適用と重複抑止
                style = _decide_style(description)
                if style["mode"] in ("label", "title"):
                    content_text = re.sub(r"[\n]+", " ", content_text).strip()
                    if len(content_text) > style["max_len"]:
                        content_text = content_text[: style["max_len"]] + "…"
                elif style["mode"] == "bullets":
                    lines = [ln.strip() for ln in content_text.splitlines() if ln.strip()]
                    uniq = []
                    for ln in lines:
                        if ln in used_sentences:
                            continue
                        used_sentences.add(ln)
                        uniq.append(ln)
                        if len(uniq) >= style["bullet_count"]:
                            break
                    content_text = "\n".join(uniq)
                else:  # paragraph
                    content_text = re.sub(r"\s+", " ", content_text).strip()
                    if len(content_text) > style["max_len"]:
                        content_text = content_text[: style["max_len"]] + "…"

            content_item = schemas.PlaceholderContent(
                placeholder_name=ph_name,
                content=content_text
            )
            content_map_by_name[ph_name] = content_item
            content_write_log.append({
                "slide_id": blueprint.slide_id,
                "slide_title": blueprint.slide_title,
                "asset_id": blueprint.asset_id,
                "placeholder_name": ph_name,
                "policy": edit_policy,
                "content": content_text
            })

        # 反映
        blueprint.content_map = list(content_map_by_name.values())
        updated_blueprints.append(blueprint)
        print(f"  ✅ '{blueprint.slide_title}' のコンテンツを生成しました。")

    return {"slide_blueprints": updated_blueprints, "content_write_log": content_write_log}

