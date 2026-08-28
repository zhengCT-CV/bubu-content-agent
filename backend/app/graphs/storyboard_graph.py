from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.domain.state import AgentState


def build_storyboard_subgraph(
    generate_storyboard: Callable[..., Any],
    review_storyboard: Callable[..., Any],
    storyboard_approval: Callable[..., Any],
    route_storyboard_review: Callable[[AgentState], str],
    route_storyboard_approval: Callable[[AgentState], str],
):
    """分镜子图把自动 Reviewer 返工循环和人工编辑 Gate 放在同一边界。"""

    graph = StateGraph(AgentState)
    graph.add_node("entry", lambda state: {})
    graph.add_node("generate_storyboard", generate_storyboard)
    graph.add_node("review_storyboard", review_storyboard)
    graph.add_node("storyboard_approval", storyboard_approval)
    graph.add_edge(START, "entry")
    graph.add_conditional_edges(
        "entry",
        lambda state: (
            "storyboard_approval" if state.get("stage") == "storyboard_approval" else "generate_storyboard"
        ),
        {
            "generate_storyboard": "generate_storyboard",
            "storyboard_approval": "storyboard_approval",
        },
    )
    graph.add_edge("generate_storyboard", "review_storyboard")
    graph.add_conditional_edges(
        "review_storyboard",
        route_storyboard_review,
        {
            "generate_storyboard": "generate_storyboard",
            "storyboard_approval": "storyboard_approval",
        },
    )
    graph.add_conditional_edges(
        "storyboard_approval",
        route_storyboard_approval,
        {
            "generate_storyboard": "generate_storyboard",
            "storyboard_approval": "storyboard_approval",
            "generate_prompts": END,
        },
    )
    return graph.compile()
