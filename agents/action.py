from agents.state import AgentState
from tools.action import (
    create_incident,
    notify_support_team,
)


def action_agent(
    state: AgentState,
) -> AgentState:

    user_input = state["user_input"]

    approval_granted = state.get(
        "approval_granted",
        False,
    )

    if not approval_granted:
        return {
            **state,
            "requires_approval": True,
            "final_answer": (
                "This operation requires human approval "
                "before an enterprise action can be executed."
            ),
            "next_agent": "end",
        }

    if "create" in user_input.lower() and "incident" in user_input.lower():
        incident = create_incident(
            title="Customer operational issue",
            description=user_input,
            severity="P2",
        )

        notification = notify_support_team(
            message=(
                f"New incident {incident['incident_id']} requires support attention."
            )
        )

        return {
            **state,
            "requires_approval": False,
            "final_answer": (
                f"Incident {incident['incident_id']} created and support team notified."
            ),
            "tool_results": [
                incident,
                notification,
            ],
            "next_agent": "end",
        }

    return {
        **state,
        "final_answer": ("I could not identify a supported enterprise action."),
        "next_agent": "end",
    }
