import re

from langchain_openai import AzureChatOpenAI

from agents.state import AgentState
from tools.customer import (
    get_customer,
    get_customer_services,
)


def customer_agent(
    state: AgentState,
    llm: AzureChatOpenAI,
) -> AgentState:

    user_input = state["user_input"]

    match = re.search(
        r"\b\d{5}\b",
        user_input,
    )

    if not match:
        return {
            **state,
            "final_answer": ("I need a valid customer ID to investigate the customer."),
            "next_agent": "end",
        }

    customer_id = match.group(0)

    customer = get_customer(customer_id)

    if not customer["found"]:
        return {
            **state,
            "customer_id": customer_id,
            "final_answer": (f"Customer {customer_id} was not found."),
            "next_agent": "end",
        }

    services = get_customer_services(customer_id)

    return {
        **state,
        "customer_id": customer_id,
        "customer_data": {
            "customer": customer,
            "services": services,
        },
        "final_answer": (
            f"Customer {customer_id} is active. "
            f"Current services: "
            f"{', '.join(services['services'])}."
        ),
        "next_agent": "end",
    }
