import re
from dataclasses import dataclass, field

_RULES: dict[str, re.Pattern[str]] = {
    "override_instructions": re.compile(
        r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|all|your)\b"
        r"[^.\n]{0,20}\b(instructions?|rules|prompts?|guidelines)",
        re.I,
    ),
    "role_hijack": re.compile(
        r"\byou are now\b|\bact as (an? )?(admin|system|developer)"
        r"|\b(developer|maintenance|god|dan) mode\b",
        re.I,
    ),
    "system_prompt_exfiltration": re.compile(
        r"\b(reveal|print|show|repeat|leak|output)\b[^.\n]{0,30}\b(system prompt|hidden "
        r"instructions|your instructions|initial prompt)",
        re.I,
    ),
    "approval_bypass": re.compile(
        r"\b(approval|authori[sz]ation|permission)s? (is |are )?(not required|unnecessary|waived)"
        r"|\bwithout (asking for |any |human )?(approval|confirmation)|\bskip (the )?approval",
        re.I,
    ),
    "tool_invocation": re.compile(
        r"\b(call|invoke|execute|run)\b[^.\n]{0,20}\b(create_incident|update_incident|"
        r"create_notification|tool|function)\b",
        re.I,
    ),
    "fake_authority": re.compile(
        r"\b(system notice|system message|assistant instructions)\b\s*(to|for)?", re.I
    ),
    "hidden_markup": re.compile(r"<!--.*?-->|\[//\]: #", re.S),
}

# Rules strong enough to flag on their own; others only add to the score.
_STRONG = {
    "override_instructions",
    "system_prompt_exfiltration",
    "approval_bypass",
    "role_hijack",
}
THRESHOLD = 2


@dataclass(frozen=True)
class InjectionVerdict:
    suspicious: bool
    score: int
    rules: list[str] = field(default_factory=list)


def scan(text: str) -> InjectionVerdict:
    """Heuristic prompt-injection detector.

    Used on retrieved chunks (which are quarantined when suspicious) and on user
    input (which is flagged and audited). It is one layer of defence; the others
    are untrusted-content wrapping, RBAC, plan validation and human approval.
    """
    hits = [name for name, pattern in _RULES.items() if pattern.search(text)]
    score = sum(2 if name in _STRONG else 1 for name in hits)
    return InjectionVerdict(suspicious=score >= THRESHOLD, score=score, rules=hits)


def wrap_untrusted(source_id: str, title: str, text: str) -> str:
    """Spotlight retrieved content so the model treats it as data, not instructions."""
    safe = text.replace("<", "&lt;").replace(">", "&gt;")
    return f'<untrusted_document id="{source_id}" title="{title}">\n{safe}\n</untrusted_document>'
