import re

from langchain_openai import AzureChatOpenAI

from agents.state import AgentState
from tools.incidents import (
    get_incident,
    get_network_status,
    search_incidents,
)


def incident_agent(
    state: AgentState,
    llm: AzureChatOpenAI,
) -> AgentState:

    user_input = state["user_input"]

    incident_match = re.search(
        r"INC-\d+",
        user_input,
        re.IGNORECASE,
    )

    if incident_match:

        incident_id = incident_match.group(0).upper()

        incident = get_incident(incident_id)

        if not incident["found"]:
            answer = f"Incident {incident_id} was not found."

        else:
            answer = (
                f"Incident {incident_id}: "
                f"{incident['title']}. "
                f"Status: {incident['status']}. "
                f"Severity: {incident['severity']}. "
                f"Location: {incident['location']}."
            )

        return {
            **state,
            "incident_id": incident_id,
            "incident_data": incident,
            "final_answer": answer,
            "next_agent": "end",
        }

    location = "Helsinki"

    network = get_network_status(location)

    incidents = search_incidents(
        location=location,
        status="ACTIVE",
    )

    if incidents:
        answer = (
            f"There are {len(incidents)} active incident(s) "
            f"affecting {location}. "
            f"Network status: {network['status']}."
        )
    else:
        answer = (
            f"No active incidents were found in {location}. "
            f"Network status: {network['status']}."
        )

    return {
        **state,
        "incident_data": {
            "network": network,
            "incidents": incidents,
        },
        "final_answer": answer,
        "next_agent": "end",
    }