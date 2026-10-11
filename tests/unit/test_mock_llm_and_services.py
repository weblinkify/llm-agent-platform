import pytest

from agents.action import describe, ungrounded_ids
from agents.customer import five_g_checks
from agents.schemas import PlannedAction, RoutingDecision
from core.settings import Settings
from llm.mock import INSUFFICIENT, MockLLM, extractive_answer, mock_route, parse_action_request
from llm.pricing import cost_usd
from services.enterprise import EnterpriseSystems, NotFoundError


@pytest.mark.parametrize(
    ("message", "agent"),
    [
        ("What is the SLA for a Priority 1 network incident?", "knowledge"),
        ("Are there any active network incidents affecting Helsinki?", "incident"),
        ("Why can't customer 10001 activate 5G?", "customer"),
        ("Customer 10002 is affected by INC-1003. Create a support incident.", "action"),
        ("What is the status of INC-1004?", "incident"),
    ],
)
def test_mock_routing(message: str, agent: str) -> None:
    assert mock_route(message) == agent


def test_extractive_answer_cites_and_refuses() -> None:
    prompt = (
        '<untrusted_document id="DOC-1" title="SLA">\nA Priority 1 incident must be restored '
        "within 4 hours.\n</untrusted_document>\n\nQuestion: How fast is a priority 1 incident restored?"
    )
    assert "[DOC-1]" in extractive_answer(prompt)
    assert (
        extractive_answer(prompt.replace("priority 1 incident restored", "lasagna")) == INSUFFICIENT
    )


async def test_mock_llm_structured_and_generate() -> None:
    llm = MockLLM()
    decision, usage = await llm.structured(
        task="route", system="s", prompt="notify the team", schema=RoutingDecision
    )
    assert decision.next_agent == "action" and usage.cost_usd == 0
    tokens: list[str] = []

    async def collect(t: str) -> None:
        tokens.append(t)

    result = await llm.generate(
        task="summarize", system="s", prompt="Facts: x\nDraft:\nhello world", on_token=collect
    )
    assert result.text == "hello world" and "".join(tokens) == "hello world"


def test_parse_action_request() -> None:
    plan = parse_action_request(
        "Customer 10002 is affected by INC-1003. Create a P1 incident and notify the duty manager."
    )
    tools = [a.tool for a in plan.actions]
    assert tools == ["create_incident", "create_notification"]
    assert plan.actions[0].arguments["severity"] == "P1"
    assert plan.actions[1].arguments["channel"] == "duty-manager"
    update = parse_action_request("Update INC-1004 to resolved")
    assert update.actions[0].tool == "update_incident"
    assert update.actions[0].arguments["status"] == "RESOLVED"


def test_ungrounded_ids_detected() -> None:
    action = PlannedAction(
        tool="create_incident",
        arguments={"customer_ids": ["10002", "10009"], "related_incident_id": "INC-1003"},
    )
    assert ungrounded_ids(action, "customer 10002 affected by INC-1003") == ["10009"]
    assert "Create" in describe(action.model_dump())


def test_pricing() -> None:
    assert cost_usd("gpt-4o-mini", 1_000_000, 0) == pytest.approx(0.15)
    assert cost_usd("unknown-model", 1000, 1000) == 0.0


def test_enterprise_systems(settings: Settings) -> None:
    systems = EnterpriseSystems(settings.enterprise_data_dir)
    assert systems.get_network_status("helsinki").status == "DEGRADED"
    assert systems.get_network_status("Vantaa").status == "NORMAL"
    with pytest.raises(NotFoundError):
        systems.get_customer("99999")
    incident = systems.create_incident("Test incident", "desc", "P3", "Oulu", ["10005"], "INC-1004")
    assert incident.affected_services == ["FIB-100", "FIB-1000"]
    updated = systems.update_incident(incident.incident_id, "RESOLVED", None, "fixed")
    assert updated.status == "RESOLVED" and "fixed" in updated.description
    assert systems.search_products(five_g_only=True)
    assert systems.search_customers("oulu")


def test_five_g_checks_explain_customer_10001(settings: Settings) -> None:
    systems = EnterpriseSystems(settings.enterprise_data_dir)
    customer = systems.get_customer("10001").model_dump()
    services = [p.model_dump() for p in systems.get_customer_services("10001")]
    failed = {c["check"] for c in five_g_checks(customer, services) if not c["passed"]}
    assert failed == {"5G-enabled plan", "5G-compatible SIM"}
