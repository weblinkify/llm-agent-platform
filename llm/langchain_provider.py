from typing import Any, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage, SystemMessage

from llm.base import LLMResult, LLMTask, SchemaT, TokenCallback, Usage, estimate_tokens
from llm.pricing import cost_usd


class LangChainLLM:
    """Adapter from any LangChain chat model to the LLMProvider protocol."""

    def __init__(self, chat: BaseChatModel, provider: str, model: str) -> None:
        self.chat = chat
        self.provider = provider
        self.model = model

    def _usage(self, message: BaseMessage | None, prompt: str, text: str) -> Usage:
        meta: dict[str, Any] = dict(getattr(message, "usage_metadata", None) or {})
        tokens_in = int(meta.get("input_tokens") or estimate_tokens(prompt))
        tokens_out = int(meta.get("output_tokens") or estimate_tokens(text))
        return Usage(
            self.provider,
            self.model,
            tokens_in,
            tokens_out,
            cost_usd(self.model, tokens_in, tokens_out),
        )

    async def generate(
        self,
        *,
        task: LLMTask,
        system: str,
        prompt: str,
        on_token: TokenCallback | None = None,
    ) -> LLMResult:
        messages = [SystemMessage(system), HumanMessage(prompt)]
        if on_token is None:
            reply = await self.chat.ainvoke(messages)
            return LLMResult(reply.text, self._usage(reply, system + prompt, reply.text))
        merged: AIMessageChunk | None = None
        async for chunk in self.chat.astream(messages):
            if chunk.text:
                await on_token(chunk.text)
            merged = chunk if merged is None else merged + chunk
        text = merged.text if merged else ""
        return LLMResult(text, self._usage(merged, system + prompt, text))

    async def structured(
        self, *, task: LLMTask, system: str, prompt: str, schema: type[SchemaT]
    ) -> tuple[SchemaT, Usage]:
        runnable = self.chat.with_structured_output(schema, include_raw=True)
        out = cast(
            dict[str, Any],
            await runnable.ainvoke([SystemMessage(system), HumanMessage(prompt)]),
        )
        if out.get("parsed") is None:
            raise ValueError(f"Model returned unparseable output for {schema.__name__}")
        parsed = cast(SchemaT, out["parsed"])
        return parsed, self._usage(out.get("raw"), system + prompt, parsed.model_dump_json())
