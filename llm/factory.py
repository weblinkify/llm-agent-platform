from core.settings import Settings
from llm.base import LLMProvider
from llm.langchain_provider import LangChainLLM
from llm.mock import MockLLM

DEFAULT_MODELS = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-sonnet-5-5",
}


def create_llm(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider
    if provider == "mock":
        return MockLLM(settings.mock_token_delay_ms)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        model = settings.llm_model or DEFAULT_MODELS["openai"]
        return LangChainLLM(
            ChatOpenAI(
                model=model,
                api_key=settings.openai_api_key or None,  # type: ignore[arg-type]
                temperature=settings.llm_temperature,
                stream_usage=True,
            ),
            provider,
            model,
        )
    if provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI

        model = settings.llm_model or settings.azure_openai_chat_deployment
        return LangChainLLM(
            AzureChatOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key or None,  # type: ignore[arg-type]
                api_version=settings.azure_openai_api_version,
                azure_deployment=settings.azure_openai_chat_deployment,
                temperature=settings.llm_temperature,
                stream_usage=True,
            ),
            provider,
            model,
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = settings.llm_model or DEFAULT_MODELS["anthropic"]
        return LangChainLLM(
            ChatAnthropic(  # type: ignore[call-arg]
                model_name=model,
                api_key=settings.anthropic_api_key or None,  # type: ignore[arg-type]
                temperature=settings.llm_temperature,
            ),
            provider,
            model,
        )
    raise ValueError(f"Unknown LLM provider: {provider}")
