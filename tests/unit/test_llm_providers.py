from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agents.schemas import RoutingDecision
from core.settings import Settings
from llm.factory import create_llm
from llm.langchain_provider import LangChainLLM
from llm.traced import TracedLLM
from observability.context import RequestUsage, current_usage


def fake(*replies: str) -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter(AIMessage(r) for r in replies))


async def test_langchain_adapter_generate_and_stream() -> None:
    llm = LangChainLLM(
        fake("Restore within 4 hours [DOC-001]", "streamed answer"), "openai", "gpt-4o-mini"
    )
    result = await llm.generate(task="answer", system="s", prompt="q")
    assert result.text.startswith("Restore") and result.usage.input_tokens > 0
    tokens: list[str] = []

    async def collect(t: str) -> None:
        tokens.append(t)

    streamed = await llm.generate(task="answer", system="s", prompt="q", on_token=collect)
    assert streamed.text == "streamed answer" and len(tokens) > 1


async def test_langchain_adapter_structured() -> None:
    class StructuredFake(GenericFakeChatModel):
        def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:  # type: ignore[override]
            from langchain_core.runnables import RunnableLambda

            return RunnableLambda(
                lambda _: {
                    "raw": AIMessage("{}"),
                    "parsed": schema(next_agent="incident", reason="r"),
                }
            )

    llm = LangChainLLM(StructuredFake(messages=iter([])), "anthropic", "claude-sonnet-5-5")
    parsed, usage = await llm.structured(
        task="route", system="s", prompt="p", schema=RoutingDecision
    )
    assert parsed.next_agent == "incident" and usage.provider == "anthropic"


async def test_traced_llm_accumulates_request_usage() -> None:
    usage = RequestUsage()
    current_usage.set(usage)
    llm = TracedLLM(LangChainLLM(fake("hello there"), "openai", "gpt-4o-mini"))
    await llm.generate(task="summarize", system="s", prompt="p")
    assert len(usage.calls) == 1 and usage.cost_usd > 0


@pytest.mark.parametrize("provider", ["openai", "azure_openai", "anthropic"])
def test_factory_builds_real_providers(settings: Settings, provider: str) -> None:
    pytest.importorskip("langchain_anthropic" if provider == "anthropic" else "langchain_openai")
    configured = settings.model_copy(
        update={
            "llm_provider": provider,
            "openai_api_key": "sk-test",
            "anthropic_api_key": "sk-ant-test",
            "azure_openai_api_key": "k",
            "azure_openai_endpoint": "https://example.openai.azure.com",
            "azure_openai_chat_deployment": "gpt-4o-mini",
        }
    )
    llm = create_llm(configured)
    assert llm.provider == provider and llm.model


def test_factory_rejects_unknown_provider(settings: Settings) -> None:
    with pytest.raises(ValueError):
        create_llm(settings.model_copy(update={"llm_provider": "nope"}))


def test_tracing_setup_with_endpoint(settings: Settings) -> None:
    from observability import tracing

    tracing.setup_tracing(
        settings.model_copy(update={"otel_exporter_otlp_endpoint": "http://localhost:4318"})
    )
    assert tracing._configured
