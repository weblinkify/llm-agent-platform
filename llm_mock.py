from agents.supervisor import RoutingDecision


class MockResponse:
    def __init__(self, content: str):
        self.content = content


class MockStructuredLLM:
    def invoke(self, prompt):
        text = str(prompt).lower()

        if "create a support incident" in text or "notify the support team" in text:
            return RoutingDecision(next_agent="action")

        if "customer 10001" in text or "activate 5g" in text:
            return RoutingDecision(next_agent="customer")

        if "active network incident" in text or "network incidents" in text:
            return RoutingDecision(next_agent="incident")

        if "sla" in text or "priority 1" in text:
            return RoutingDecision(next_agent="knowledge")

        return RoutingDecision(next_agent="knowledge")


class MockLLM:
    def with_structured_output(self, schema):
        return MockStructuredLLM()

    def invoke(self, prompt):
        return MockResponse(
            "Mock knowledge response: Priority 1 incidents have the highest severity and require immediate response."
        )
