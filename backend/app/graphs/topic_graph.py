from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.domain.state import AgentState


def build_topic_subgraph(
    generate_topics: Callable[..., Any],
    topic_approval: Callable[..., Any],
    route_topic_approval: Callable[[AgentState], str],
):
    """选题子图内部处理“生成 -> 人选 -> 不满意重做”的循环。"""

    graph = StateGraph(AgentState)
    graph.add_node("entry", lambda state: {})
    graph.add_node("generate_topics", generate_topics)
    graph.add_node("topic_approval", topic_approval)
    graph.add_edge(START, "entry")
    graph.add_conditional_edges(
        "entry",
        lambda state: "topic_approval" if state.get("stage") == "topic_approval" else "generate_topics",
        {"generate_topics": "generate_topics", "topic_approval": "topic_approval"},
    )
    graph.add_edge("generate_topics", "topic_approval")
    graph.add_conditional_edges(
        "topic_approval",
        route_topic_approval,
        {"generate_topics": "generate_topics", "generate_storyboard": END},
    )
    return graph.compile()
