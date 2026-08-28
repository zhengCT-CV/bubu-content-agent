from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.domain.state import AgentState


def build_prompt_subgraph(
    generate_prompts: Callable[..., Any],
    prompt_approval: Callable[..., Any],
    route_prompt_approval: Callable[[AgentState], str],
):
    """视觉 Prompt 生成后直接进入人工确认，支持整包或单格重生成。"""

    graph = StateGraph(AgentState)
    graph.add_node("entry", lambda state: {})
    graph.add_node("generate_prompts", generate_prompts)
    graph.add_node("prompt_approval", prompt_approval)
    graph.add_edge(START, "entry")
    graph.add_conditional_edges(
        "entry",
        lambda state: "prompt_approval" if state.get("stage") == "prompt_approval" else "generate_prompts",
        {
            "generate_prompts": "generate_prompts",
            "prompt_approval": "prompt_approval",
        },
    )
    graph.add_edge("generate_prompts", "prompt_approval")
    graph.add_conditional_edges(
        "prompt_approval",
        route_prompt_approval,
        {"generate_prompts": "generate_prompts", "create_prediction": END},
    )
    return graph.compile()
