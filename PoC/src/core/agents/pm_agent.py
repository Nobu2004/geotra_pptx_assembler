# src/core/agents/pm_agent.py

import uuid
import json
from pathlib import Path
from typing import Dict, List

from .. import schemas
from ..renderer import PPTXRenderer

# --- ▼▼▼ 修正箇所 ▼▼▼ ---
# pm_agent.py のある場所から一つ上の階層 (src/core/) を指すようにパスを修正
DECK_TEMPLATES_PATH = Path(__file__).parent.parent / "deck_templates.json"
# --- ▲▲▲ 修正ここまで ▲▲▲ ---

def _load_deck_templates() -> List[Dict]:
    """deck_templates.jsonを読み込む"""
    with open(DECK_TEMPLATES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)["deck_templates"]

def _find_best_deck_template(user_request: str, templates: List[Dict]) -> Dict | None:
    """ユーザーリクエストに最も合致するデッキテンプレートを探す"""
    print(f"  ユーザーリクエスト '{user_request}' に最適なデッキテンプレートを検索中...")
    best_template = None
    max_score = 0
    request_text = user_request.lower()

    for template in templates:
        score = 0
        for keyword in template.get("keywords", []):
            if keyword.lower() in request_text:
                score += 1
        if score > max_score:
            max_score = score
            best_template = template
    
    if best_template:
        print(f"  最適なテンプレートとして '{best_template['name']}' を選択しました。")
    else:
        print("  [警告] 合致するデッキテンプレートが見つかりませんでした。")
    return best_template

def _select_slide_asset(search_query: str, renderer: PPTXRenderer) -> str | None:
    """特定のトピック（検索クエリ）に最も合致するスライド資産を検索する"""
    best_match_id = None
    max_score = 0
    keywords = {keyword.strip().lower() for keyword in search_query.split(',')}

    for asset_id, asset_info in renderer.slide_asset_map.items():
        score = 0
        search_tags = " ".join(asset_info.get("tags", [])).lower()
        search_category = asset_info.get("category", "").lower()
        
        for keyword in keywords:
            if not keyword: continue
            if keyword in search_tags: score += 5
            if keyword in search_category: score += 3
        
        if score > max_score:
            max_score = score
            best_match_id = asset_id
    
    return best_match_id

def deck_planner_node(state: schemas.GraphState, renderer: PPTXRenderer) -> Dict:
    """
    デッキテンプレートに基づき、プレゼンテーション全体の構成を計画し、
    複数のSlideBlueprintを作成する。
    """
    print("--- 🧠 デッキプランナーを実行中... ---")
    user_request = state["initial_user_request"]
    
    deck_templates = _load_deck_templates()
    selected_template = _find_best_deck_template(user_request, deck_templates)
    
    if not selected_template:
        # TODO: テンプレートが見つからない場合のフォールバック処理
        print("  フォールバック処理: 単一スライドを生成します。")
        # (ここでは簡略化のため、エラーを返す代わりに空のリストを返す)
        return {"slide_blueprints": []}

    blueprints = []
    plan_lines: List[str] = []
    story = selected_template.get("story", [])
    print(f"  ストーリー '{selected_template['name']}' に基づいて設計図を作成します。")

    for i, slide_info in enumerate(story):
        search_query = slide_info["search_query"]
        selected_asset_id = _select_slide_asset(search_query, renderer)
        
        if not selected_asset_id:
            print(f"  [警告] '{slide_info['slide_name']}' に合致する資産が見つかりません。スキップします。")
            continue

        asset_info = renderer.slide_asset_map[selected_asset_id]
        
        initial_content_map = [
            schemas.PlaceholderContent(placeholder_name=ph["name"], content="")
            for ph in asset_info.get("placeholders", [])
        ]

        blueprint = schemas.SlideBlueprint(
            slide_id=f"slide_{i+1}_{str(uuid.uuid4())[:8]}",
            slide_title=slide_info["slide_name"],
            asset_id=selected_asset_id,
            content_map=initial_content_map,
            search_query=search_query
        )
        blueprints.append(blueprint)
        print(f"  ✓ 設計図 {i+1}: '{blueprint.slide_title}' (資産ID: {selected_asset_id}) を作成しました。")
        plan_lines.append(f"{i+1}. {blueprint.slide_title}（資産ID: {selected_asset_id}）")

    plan_header = f"テンプレート『{selected_template['name']}』に基づく構成案です。合計 {len(blueprints)} 枚を提案します。\n"
    plan_body = "\n".join([f"- {line}" for line in plan_lines]) if plan_lines else "(スライドがありません)"
    plan_footer = "\n\nこの構成で問題なければ『承認』を押してください。承認後にリサーチと執筆を実行します。"
    deck_plan_summary = plan_header + plan_body + plan_footer

    return {
        "slide_blueprints": blueprints,
        "active_slide_index": 0,
        "deck_plan_summary": deck_plan_summary
    }
