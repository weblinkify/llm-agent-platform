import re
from typing import Any

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    # Finnish personal identity code (henkilötunnus)
    (re.compile(r"\b\d{6}[-+AaBCDEFUVWXY]\d{3}[0-9A-Ya-y]\b"), "[PERSONAL_ID]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD_NUMBER]"),
    (
        re.compile(r"(?<!\w)(?:\+\d{1,3}|0)[ -]?\d{1,3}(?:[ -]?\d{2,4}){2,4}(?!\w)"),
        "[PHONE]",
    ),
]

PII_FIELDS = frozenset({"name", "email", "phone"})


def redact_text(text: str) -> str:
    for pattern, token in _PATTERNS:
        text = pattern.sub(token, text)
    return text


def redact(value: Any) -> Any:
    """Recursively redact PII in strings, dicts and lists."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            k: f"[{k.upper()}]" if k in PII_FIELDS and isinstance(v, str) else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value
