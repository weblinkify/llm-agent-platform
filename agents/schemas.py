from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["knowledge", "customer", "incident", "action"]


class RoutingDecision(BaseModel):
    next_agent: AgentName = Field(description="The specialist that should handle the request.")
    reason: str = Field(description="One short sentence explaining the choice.")


class PlannedAction(BaseModel):
    tool: Literal["create_incident", "update_incident", "create_notification"]
    arguments: dict[str, Any]


class ActionPlan(BaseModel):
    customer_ids: list[str] = Field(
        default_factory=list, description="Customer IDs named by the user."
    )
    incident_ids: list[str] = Field(
        default_factory=list, description="Incident IDs named by the user."
    )
    actions: list[PlannedAction] = Field(default_factory=list)
