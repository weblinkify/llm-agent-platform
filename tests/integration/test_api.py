import json
from collections.abc import Callable

from fastapi.testclient import TestClient

from core.models import Role

Auth = Callable[..., dict[str, str]]

SCENARIOS = {
    "incident": "Are there any active network incidents affecting Helsinki?",
    "knowledge": "What is the SLA for a Priority 1 network incident?",
    "customer": "Why can't customer 10001 activate 5G?",
    "action": "Customer 10002 is affected by INC-1003. Create a support incident and notify the support team.",
}


def chat(client: TestClient, headers: dict[str, str], message: str) -> dict:
    response = client.post("/chat", json={"message": message}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_health_ready_info_metrics(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "healthy"}
    ready = client.get("/ready").json()
    assert ready["status"] == "ready" and ready["chunks"] > 30
    assert client.get("/info").json()["llm_provider"] == "mock"
    assert client.get("/").json()["version"] == "1.0.0"
    metrics = client.get("/metrics")
    assert metrics.status_code == 200 and "telco_http_requests_total" in metrics.text


def test_chat_requires_authentication(client: TestClient) -> None:
    assert client.post("/chat", json={"message": "hi"}).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.post("/chat", json={"message": "hi"}, headers=bad).status_code == 401


def test_demo_token_and_me(client: TestClient) -> None:
    token = client.post("/auth/demo-token", json={"role": "AI_ENGINEER"}).json()
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"}).json()
    assert me["role"] == "AI_ENGINEER" and not me["can_approve"] and me["can_read_audit"]


def test_scenario_1_incident_investigation(client: TestClient, auth: Auth) -> None:
    body = chat(client, auth(Role.SUPPORT_AGENT), SCENARIOS["incident"])
    assert body["agent"] == "incident" and body["status"] == "completed"
    assert "INC-1003" in body["answer"] and "DEGRADED" in body["answer"]
    assert body["approval"] is None
    assert {"get_network_status", "search_incidents"} <= {t["tool"] for t in body["tool_calls"]}


def test_scenario_2_knowledge_with_citations(client: TestClient, auth: Auth) -> None:
    body = chat(client, auth(Role.READ_ONLY_USER), SCENARIOS["knowledge"])
    assert body["agent"] == "knowledge" and body["status"] == "completed"
    assert "4 hours" in body["answer"] and "[DOC-001]" in body["answer"]
    assert body["citations"][0]["doc_id"] == "DOC-001" and body["citations"][0]["snippet"]
    assert body["usage"]["llm_calls"] == 2


def test_scenario_3_customer_troubleshooting(client: TestClient, auth: Auth) -> None:
    body = chat(client, auth(Role.SUPPORT_AGENT), SCENARIOS["customer"])
    assert body["agent"] == "customer"
    failed = {c["check"] for c in body["data"]["checks"] if not c["passed"]}
    assert failed == {"5G-enabled plan", "5G-compatible SIM"}
    assert "MOB-5G-PLUS" in body["answer"]
    assert "email" not in body["data"]["customer"] and "name" not in body["data"]["customer"]
    assert body["approval"] is None


def test_scenario_4_action_requires_approval_then_executes(client: TestClient, auth: Auth) -> None:
    requester, approver = auth(Role.SUPPORT_AGENT, "agent-anna"), auth(Role.ADMIN, "admin-ola")
    body = chat(client, requester, SCENARIOS["action"])
    assert body["agent"] == "action" and body["status"] == "pending_approval"
    approval = body["approval"]
    assert [a["tool"] for a in approval["actions"]] == ["create_incident", "create_notification"]
    assert not {"create_incident", "create_notification"} & {t["tool"] for t in body["tool_calls"]}

    pending = client.get("/approvals", headers=approver).json()
    assert approval["approval_id"] in {a["approval_id"] for a in pending}

    own = client.post(
        f"/approvals/{approval['approval_id']}", json={"decision": "approve"}, headers=requester
    )
    assert own.status_code == 403  # separation of duties

    done = client.post(
        f"/approvals/{approval['approval_id']}",
        json={"decision": "approve", "reason": "verified impact"},
        headers=approver,
    )
    assert done.status_code == 200
    result = done.json()
    assert result["status"] == "completed" and "Created incident INC-" in result["answer"]
    assert [t["tool"] for t in result["tool_calls"]] == ["create_incident", "create_notification"]
    assert result["approval"]["status"] == "APPROVED"

    again = client.post(
        f"/approvals/{approval['approval_id']}", json={"decision": "approve"}, headers=approver
    )
    assert again.status_code == 409


def test_rejected_action_executes_nothing(client: TestClient, auth: Auth) -> None:
    body = chat(client, auth(Role.ADMIN, "admin-a"), "Update INC-1004 to resolved")
    approval_id = body["approval"]["approval_id"]
    result = client.post(
        f"/approvals/{approval_id}",
        json={"decision": "reject", "reason": "not fixed"},
        headers=auth(Role.SUPPORT_AGENT, "agent-b"),
    ).json()
    assert result["status"] == "rejected" and "not fixed" in result["answer"]
    assert result["tool_calls"] == []


def test_non_approver_cannot_approve(client: TestClient, auth: Auth) -> None:
    body = chat(client, auth(Role.SUPPORT_AGENT), "Notify the l3 network team about INC-1004")
    response = client.post(
        f"/approvals/{body['approval']['approval_id']}",
        json={"decision": "approve"},
        headers=auth(Role.AI_ENGINEER),
    )
    assert response.status_code == 403
    assert (
        client.post(
            "/approvals/APR-NOPE", json={"decision": "approve"}, headers=auth(Role.ADMIN)
        ).status_code
        == 404
    )


def test_read_only_user_is_denied_customer_data_and_actions(client: TestClient, auth: Auth) -> None:
    ro = auth(Role.READ_ONLY_USER)
    assert chat(client, ro, SCENARIOS["customer"])["status"] == "denied"
    body = chat(client, ro, SCENARIOS["action"])
    assert body["status"] == "denied" and body["approval"] is None


def test_audit_log_records_every_step(client: TestClient, auth: Auth) -> None:
    body = chat(client, auth(Role.SUPPORT_AGENT), SCENARIOS["knowledge"])
    assert client.get("/audit", headers=auth(Role.SUPPORT_AGENT)).status_code == 403
    events = client.get(
        f"/audit?request_id={body['request_id']}", headers=auth(Role.AI_ENGINEER)
    ).json()
    kinds = {e["kind"] for e in events}
    assert {"request", "agent_step", "response"} <= kinds


def test_tools_endpoint_reflects_role(client: TestClient, auth: Auth) -> None:
    tools = {t["name"]: t for t in client.get("/tools", headers=auth(Role.READ_ONLY_USER)).json()}
    assert len(tools) == 12
    assert tools["search_knowledge_base"]["allowed"] and not tools["create_incident"]["allowed"]


def test_stream_emits_agent_tool_token_and_final_events(client: TestClient, auth: Auth) -> None:
    events: list[dict] = []
    with client.stream(
        "POST",
        "/chat/stream",
        json={"message": SCENARIOS["knowledge"]},
        headers=auth(Role.SUPPORT_AGENT),
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
    types = [e["type"] for e in events]
    assert types[0] == "agent" and types[-1] == "final"
    assert {"route", "tool_call", "tool_result", "token"} <= set(types)
    assert events[-1]["response"]["agent"] == "knowledge"


def test_stream_reports_pending_approval(client: TestClient, auth: Auth) -> None:
    with client.stream(
        "POST",
        "/chat/stream",
        json={"message": SCENARIOS["action"]},
        headers=auth(Role.SUPPORT_AGENT),
    ) as response:
        types = [
            json.loads(line[5:])["type"]
            for line in response.iter_lines()
            if line.startswith("data:")
        ]
    assert "approval_required" in types and "approval_pending" in types


def test_rate_limit(settings, auth: Auth) -> None:  # type: ignore[no-untyped-def]
    from apps.api.main import create_app

    with TestClient(
        create_app(settings.model_copy(update={"rate_limit_per_minute": 2}))
    ) as limited:
        headers = auth(Role.READ_ONLY_USER)
        codes = [
            limited.post("/chat", json={"message": "SLA?"}, headers=headers).status_code
            for _ in range(3)
        ]
    assert codes == [200, 200, 429]


def test_validation_errors(client: TestClient, auth: Auth) -> None:
    assert client.post("/chat", json={"message": ""}, headers=auth(Role.ADMIN)).status_code == 422
    assert (
        client.post("/chat", json={"message": "x" * 4001}, headers=auth(Role.ADMIN)).status_code
        == 422
    )


def test_incident_lookup_by_id_and_unknown(client: TestClient, auth: Auth) -> None:
    body = chat(client, auth(Role.READ_ONLY_USER), "What is the status of INC-1004?")
    assert body["agent"] == "incident" and "Packet loss" in body["answer"]
    assert "Network status in Oulu: DEGRADED" in body["answer"]
    missing = chat(client, auth(Role.READ_ONLY_USER), "What is the status of INC-9999?")
    assert "not found" in missing["answer"]
    overview = chat(client, auth(Role.READ_ONLY_USER), "Is there any outage right now?")
    assert overview["agent"] == "incident" and "3 active incidents" in overview["answer"]


def test_customer_without_id_and_unknown_customer(client: TestClient, auth: Auth) -> None:
    assert (
        "customer ID"
        in chat(client, auth(Role.ADMIN), "Check this customer account please")["answer"]
    )
    assert "not found" in chat(client, auth(Role.ADMIN), "Investigate customer 19999")["answer"]


def test_out_of_domain_question_is_refused(client: TestClient, auth: Auth) -> None:
    body = chat(client, auth(Role.ADMIN), "Give me a lasagna recipe")
    assert body["status"] == "insufficient_context" and body["citations"] == []
