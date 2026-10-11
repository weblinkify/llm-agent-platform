"""Smoke-test a running stack through the web proxy (stdlib only).

python scripts/smoke_test.py http://localhost:3000/api
"""

import json
import sys
import urllib.request
from typing import Any

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000/api"


def request(path: str, body: dict[str, Any] | None = None, token: str | None = None) -> Any:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers)  # noqa: S310
    with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def token(role: str) -> str:
    return str(request("/auth/demo-token", {"role": role})["access_token"])


def main() -> None:
    info = request("/info")
    print("info:", info)
    support, admin = token("SUPPORT_AGENT"), token("ADMIN")
    expectations = {
        "Are there any active network incidents affecting Helsinki?": ("incident", "INC-1003"),
        "What is the SLA for a Priority 1 network incident?": ("knowledge", "4 hours"),
        "Why can't customer 10001 activate 5G?": ("customer", "5G-compatible SIM"),
    }
    for message, (agent, needle) in expectations.items():
        body = request("/chat", {"message": message}, support)
        assert body["agent"] == agent and needle in body["answer"], body
        print(f"ok  {agent:9} {message}")
    action = request(
        "/chat",
        {
            "message": "Customer 10002 is affected by INC-1003. "
            "Create a support incident and notify the support team."
        },
        support,
    )
    assert action["status"] == "pending_approval", action
    approval_id = action["approval"]["approval_id"]
    result = request(f"/approvals/{approval_id}", {"decision": "approve", "reason": "smoke"}, admin)
    assert result["status"] == "completed" and "Created incident" in result["answer"], result
    print(f"ok  action    approval {approval_id} -> {result['answer'].splitlines()[1]}")
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
