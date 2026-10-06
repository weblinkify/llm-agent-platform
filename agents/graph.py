from langgraph.graph import (
    StateGraph,
    END,
)

from agents.state import AgentState
from agents.supervisor import supervisor_agent
from agents.knowledge import knowledge_agent
from agents.customer import customer_agent
from agents.incident import incident_agent
from agents.action import action_agent


def build_graph(llm):

    graph = StateGraph(AgentState)

    graph.add_node(
        "supervisor",
        lambda state: supervisor_agent(state, llm),
    )

    graph.add_node(
        "knowledge",
        lambda state: knowledge_agent(state, llm),
    )

    graph.add_node(
        "customer",
        lambda state: customer_agent(state, llm),
    )

    graph.add_node(
        "incident",
        lambda state: incident_agent(state, llm),
    )

    graph.add_node(
        "action",
        lambda state: action_agent(state),
    )

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        lambda state: state["next_agent"],
        {
            "knowledge": "knowledge",
            "customer": "customer",
            "incident": "incident",
            "action": "action",
        },
    )

    graph.add_edge(
        "knowledge",
        END,
    )

    graph.add_edge(
        "customer",
        END,
    )

    graph.add_edge(
        "incident",
        END,
    )

    graph.add_edge(
        "action",
        END,
    )

    return graph.compile()
