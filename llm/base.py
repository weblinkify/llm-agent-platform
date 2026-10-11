from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

LLMTask = Literal["route", "answer", "summarize", "plan_actions", "judge"]
TokenCallback = Callable[[str], Awaitable[None]]
SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(frozen=True)
class Usage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class LLMResult:
    text: str
    usage: Usage


class LLMProvider(Protocol):
    provider: str
    model: str

    async def generate(
        self,
        *,
        task: LLMTask,
        system: str,
        prompt: str,
        on_token: TokenCallback | None = None,
    ) -> LLMResult: ...

    async def structured(
        self, *, task: LLMTask, system: str, prompt: str, schema: type[SchemaT]
    ) -> tuple[SchemaT, Usage]: ...


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
