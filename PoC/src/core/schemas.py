# src/core/schemas.py

from pydantic import BaseModel, Field
from typing import List, Literal, Optional, TypedDict
from enum import Enum

# --- Enum定義 ---
class DialogueMode(str, Enum):
    EDIT = "edit"
    CONSULT = "consult"

class EditPolicy(str, Enum):
    GENERATE = "generate"
    POPULATE = "populate"
    FIXED = "fixed"

# --- エージェント間データスキーマ ---
class ResearchFinding(BaseModel):
    content: str = Field(description="抽出または要約された情報本体。")
    source: str = Field(description="情報の出典（URL、ファイル名、ページ番号など）。")

class ResearchReport(BaseModel):
    findings: List[ResearchFinding] = Field(description="発見された情報のリスト。")
    summary: str = Field(description="調査結果全体の要約。")

class PlaceholderContent(BaseModel):
    placeholder_name: str = Field(description="対象となるプレースホルダーのPowerPoint内部名。")
    content: str = Field(description="挿入するテキストコンテンツ。")

# --- スライド設計図スキーマ ---
class SlideBlueprint(BaseModel):
    slide_id: str = Field(description="スライドを一意に識別するためのID。")
    slide_title: str = Field(description="このスライドのタイトル。")
    asset_id: str = Field(description="使用するサンプルスライドのID。")
    content_map: List[PlaceholderContent] = Field(description="各プレースホルダーに割り当てるコンテンツのリスト。")
    search_query: Optional[str] = Field(default=None, description="内部文書検索に使うこのスライド固有のクエリ。")

# --- LangGraph State ---
class GraphState(TypedDict):
    """
    LangGraphのStateオブジェクト。
    """
    # --- 基本情報 ---
    initial_user_request: str
    messages: list
    
    # --- ▼▼▼ 新規追加 ▼▼▼ ---
    # デッキ計画と承認の状態
    deck_plan_summary: Optional[str]
    is_plan_confirmed: bool
    # --- ▲▲▲ 追加ここまで ▲▲▲ ---

    # --- 生成物 ---
    research_report: Optional[ResearchReport]
    slide_blueprints: List[SlideBlueprint]
    active_slide_index: int
    # 追加: ライターが生成したプレースホルダー書き込みログ
    content_write_log: Optional[list]
    # 追加: スライドごとの内部文書要約
    slide_summaries: Optional[dict]
