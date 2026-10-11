import time

from opentelemetry.trace import Span

from llm.base import LLMProvider, LLMResult, LLMTask, SchemaT, TokenCallback, Usage
from observability.context import current_usage
from observability.metrics import LLM_COST, LLM_LATENCY, LLM_TOKENS
from observability.tracing import tracer


class TracedLLM:
    """Wraps a provider with an OpenTelemetry span, Prometheus metrics and
    per-request token/cost accounting."""

    def __init__(self, inner: LLMProvider) -> None:
        self.inner = inner
        self.provider = inner.provider
        self.model = inner.model

    def _record(self, task: LLMTask, usage: Usage, started: float) -> None:
        LLM_LATENCY.labels(self.provider, task).observe(time.perf_counter() - started)
        LLM_TOKENS.labels(self.provider, self.model, "input").inc(usage.input_tokens)
        LLM_TOKENS.labels(self.provider, self.model, "output").inc(usage.output_tokens)
        LLM_COST.labels(self.provider, self.model).inc(usage.cost_usd)
        if (acc := current_usage.get()) is not None:
            acc.calls.append(usage)

    async def generate(
        self,
        *,
        task: LLMTask,
        system: str,
        prompt: str,
        on_token: TokenCallback | None = None,
    ) -> LLMResult:
        with tracer.start_as_current_span(f"llm.{task}") as span:
            started = time.perf_counter()
            result = await self.inner.generate(
                task=task, system=system, prompt=prompt, on_token=on_token
            )
            self._set_attrs(span, task, result.usage)
            self._record(task, result.usage, started)
            return result

    async def structured(
        self, *, task: LLMTask, system: str, prompt: str, schema: type[SchemaT]
    ) -> tuple[SchemaT, Usage]:
        with tracer.start_as_current_span(f"llm.{task}") as span:
            started = time.perf_counter()
            parsed, usage = await self.inner.structured(
                task=task, system=system, prompt=prompt, schema=schema
            )
            self._set_attrs(span, task, usage)
            self._record(task, usage, started)
            return parsed, usage

    @staticmethod
    def _set_attrs(span: Span, task: LLMTask, usage: Usage) -> None:
        span.set_attribute("gen_ai.system", usage.provider)
        span.set_attribute("gen_ai.request.model", usage.model)
        span.set_attribute("gen_ai.operation.name", task)
        span.set_attribute("gen_ai.usage.input_tokens", usage.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", usage.output_tokens)
        span.set_attribute("llm.cost_usd", usage.cost_usd)
