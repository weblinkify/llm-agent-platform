from contextvars import ContextVar
from dataclasses import dataclass, field

from llm.base import Usage


@dataclass
class RequestUsage:
    calls: list[Usage] = field(default_factory=list)

    @property
    def input_tokens(self) -> int:
        return sum(u.input_tokens for u in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(u.output_tokens for u in self.calls)

    @property
    def cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.calls)


current_usage: ContextVar[RequestUsage | None] = ContextVar("current_usage", default=None)
