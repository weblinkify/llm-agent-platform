# USD per 1M tokens (input, output). Unknown models report cost 0.0;
# set LLM_PRICE_INPUT_PER_MTOK / LLM_PRICE_OUTPUT_PER_MTOK to override.
import os

PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "text-embedding-3-small": (0.02, 0.0),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    override_in = os.getenv("LLM_PRICE_INPUT_PER_MTOK")
    override_out = os.getenv("LLM_PRICE_OUTPUT_PER_MTOK")
    if override_in and override_out:
        price_in, price_out = float(override_in), float(override_out)
    else:
        price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
