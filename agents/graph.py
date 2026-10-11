from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.action import action_execute, action_plan, approval_gate
from agents.customer import customer
from agents.guard import output_guard
from agents.incident import incident
from agents.knowledge import knowledge
from agents.runtime import Deps, emit
from agents.state import AgentState
from agents.supervisor import supervisor
from observability.tracing import tracer

Node = Any  # LangGraph node protocols are too narrow for typed partials


def traced(name: str, fn: Callable[..., Awaitable[dict[str, Any]]], deps: Deps) -> Node:
    bound = partial(fn, deps=deps)

    async def run(state: AgentState) -> dict[str, Any]:
        with tracer.start_as_current_span(f"agent.{name}"):
            emit({"type": "agent", "agent": name})
            return await bound(state)

    return run


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver[str]) -> CompiledStateGraph[Any]:
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", traced("supervisor", supervisor, deps))
    graph.add_node("knowledge", traced("knowledge", knowledge, deps))
    graph.add_node("customer", traced("customer", customer, deps))
    graph.add_node("incident", traced("incident", incident, deps))
    graph.add_node("action_plan", traced("action", action_plan, deps))
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("action_execute", traced("action", action_execute, deps))
    graph.add_node("guard", traced("guard", output_guard, deps))

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        lambda s: "action_plan" if s["agent"] == "action" else s["agent"],
        ["knowledge", "customer", "incident", "action_plan"],
    )
    for node in ("knowledge", "customer", "incident"):
        graph.add_edge(node, "guard")
    graph.add_conditional_edges(
        "action_plan",
        lambda s: "approval_gate" if s.get("status") == "pending_approval" else "guard",
        ["approval_gate", "guard"],
    )
    graph.add_edge("approval_gate", "action_execute")
    graph.add_edge("action_execute", "guard")
    graph.add_edge("guard", END)
    return graph.compile(checkpointer=checkpointer)
