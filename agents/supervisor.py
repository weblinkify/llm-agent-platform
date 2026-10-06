from langchain_openai import AzureChatOpenAI
from pydantic import BaseModel, Field

from agents.state import AgentState


class RoutingDecision(BaseModel):

    next_agent: str = Field(
        description=(
            "One of: knowledge, customer, "
            "incident, action"
        )
    )


def supervisor_agent(
    state: AgentState,
    llm: AzureChatOpenAI,
) -> AgentState:

    structured_llm = llm.with_structured_output(
        RoutingDecision
    )

    prompt = f"""
You are the supervisor of a telecommunications
AI operations platform.

Route the request to exactly one specialist.

Specialists:

knowledge:
Questions about documentation, policy,
procedures and technical information.

customer:
Customer lookup, services and troubleshooting.

incident:
Incident investigation and network status.

action:
Creating/updating incidents or notifying teams.

User request:

{state["user_input"]}

Return the best specialist.
"""

    decision = structured_llm.invoke(prompt)

    return {
        **state,
        "next_agent": decision.next_agent,
    }