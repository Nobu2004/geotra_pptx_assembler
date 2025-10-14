# src/core/graph.py

from langgraph.graph import StateGraph, END
from . import schemas
from .agents.pm_agent import deck_planner_node
from .agents.researcher import research_agent_node
from .agents.writer import writer_agent_node
from .renderer import PPTXRenderer

def create_graph():
    renderer = PPTXRenderer()
    builder = StateGraph(schemas.GraphState)

    builder.add_node("deck_planner", lambda state: deck_planner_node(state, renderer))
    builder.add_node("research", research_agent_node)
    builder.add_node("writer", lambda state: writer_agent_node(state, renderer))

    builder.set_entry_point("deck_planner")
    
    # --- ▼▼▼ 変更点: 計画承認後にリサーチへ進む条件分岐 ▼▼▼ ---
    def should_continue(state: schemas.GraphState):
        if state.get("is_plan_confirmed"):
            return "research" # 承認されていればリサーチへ
        else:
            return END # 承認されていなければ一旦停止

    builder.add_conditional_edges(
        "deck_planner",
        should_continue,
        {"research": "research", END: END}
    )
    # --- ▲▲▲ 変更ここまで ▲▲▲ ---

    builder.add_edge("research", "writer")
    builder.add_edge("writer", END)

    graph = builder.compile()
    return graph
