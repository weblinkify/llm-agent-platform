from fastapi import FastAPI
from pydantic import BaseModel

from agents.graph import build_graph
from agents.llm_mock import MockLLM

app = FastAPI(
    title="Telco AI Operations Assistant",
    version="1.0.0",
)

llm = MockLLM()
agent = build_graph(llm)


class ChatRequest(BaseModel):
    message: str
    approval_granted: bool = False


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Telco AI Operations Assistant",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
    }


@app.get("/ready")
async def readiness():
    return {
        "status": "ready",
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    state = {
        "user_input": request.message,
        "messages": [],
        "approval_granted": request.approval_granted,
        "requires_approval": False,
        "audit_events": [],
    }

    result = agent.invoke(state)

    return {
        "answer": result.get(
            "final_answer",
            "No answer generated.",
        ),
        "requires_approval": result.get(
            "requires_approval",
            False,
        ),
        "customer": result.get("customer_data"),
        "incident": result.get("incident_data"),
        "sources": result.get(
            "retrieved_documents",
            [],
        ),
    }
