from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.domain.state import AgentState


def build_retro_subgraph(
    metrics_wait: Callable[..., Any],
    generate_retro: Callable[..., Any],
    knowledge_approval: Callable[..., Any],
    apply_knowledge: Callable[..., Any],
    route_after_knowledge: Callable[[AgentState], str],
):
    """复盘子图持有 24h -> 审批 -> 48h -> 审批的长期暂停循环。"""

    graph = StateGraph(AgentState)
    graph.add_node("entry", lambda state: {})
    graph.add_node("metrics_wait", metrics_wait)
    graph.add_node("generate_retro", generate_retro)
    graph.add_node("knowledge_approval", knowledge_approval)
    graph.add_node("apply_knowledge", apply_knowledge)
    graph.add_edge(START, "entry")
    graph.add_conditional_edges(
        "entry",
        lambda state: "knowledge_approval" if state.get("stage") == "knowledge_approval" else "metrics_wait",
        {"metrics_wait": "metrics_wait", "knowledge_approval": "knowledge_approval"},
    )
    graph.add_edge("metrics_wait", "generate_retro")
    graph.add_edge("generate_retro", "knowledge_approval")
    graph.add_edge("knowledge_approval", "apply_knowledge")
    graph.add_conditional_edges(
        "apply_knowledge",
        route_after_knowledge,
        {"metrics_wait": "metrics_wait", "finalize": END},
    )
    return graph.compile()
