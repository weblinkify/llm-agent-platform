"""Deterministic offline LLM used for CI, evals and the zero-key demo.

It is a test double, not a language model: routing uses keyword rules, grounded
answers are extractive (the best-supported sentences from the supplied
documents, with their IDs), summaries return the agent's fact-based draft, and
action plans are parsed with regular expressions.
"""

import re
from typing import cast

from pydantic import BaseModel

from agents.schemas import ActionPlan, PlannedAction
from llm.base import LLMResult, LLMTask, SchemaT, TokenCallback, Usage, estimate_tokens
from rag.bm25 import tokenize

INSUFFICIENT = "INSUFFICIENT_CONTEXT"

_DOC = re.compile(
    r'<untrusted_document id="([^"]+)" title="[^"]*">\n(.*?)\n</untrusted_document>',
    re.S,
)
_ACTION = (
    "create a",
    "create an",
    "open a",
    "open an",
    "raise a",
    "notify",
    "update incident",
    "update inc",
    "close inc",
    "resolve inc",
    "escalate inc",
    "send a notification",
    "log a ticket",
)
_LIVE_INCIDENT = re.compile(
    r"\binc-\d{4}\b"
    r"|\b(active|current|ongoing|right now|currently|affecting)\b.*\b(incident|outage|network)"
    r"|\b(incident|outage|network)s?\b.*\b(active|affecting|in [A-Z]|right now|today)\b"
    r"|\bnetwork status\b|\bis the network\b",
    re.I,
)
_KNOWLEDGE = (
    "sla",
    "policy",
    "procedure",
    "runbook",
    "process",
    "how do",
    "how should",
    "how long",
    "how fast",
    "how quickly",
    "when must",
    "when should",
    "requirement",
    "prerequisite",
    "guideline",
    "what is the",
    "what are the",
    "who handles",
    "which devices",
    "which iphone",
)
_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")


def mock_route(message: str) -> str:
    text = message.lower()
    if any(k in text for k in _ACTION):
        return "action"
    if re.search(r"\b1\d{4}\b", text) and "inc-" not in text:
        return "customer"
    if re.search(r"\b(investigate|look up|check)\b.*\bcustomer\b", text):
        return "customer"
    if _LIVE_INCIDENT.search(message) and not re.search(r"\bsla\b|\bpolicy\b", text):
        return "incident"
    if any(k in text for k in _KNOWLEDGE):
        return "knowledge"
    if any(k in text for k in ("incident", "outage", "degradation")):
        return "incident"
    return "knowledge"


def _clean(line: str) -> str:
    return _LIST_ITEM.sub("", line).replace("**", "").strip(" |")


def extractive_answer(prompt: str, max_sentences: int = 3) -> str:
    """Pick the sentences that share the most (stemmed) terms with the question.
    A selected sentence ending in ':' brings the list that follows it."""
    question = prompt.rsplit("Question:", 1)[-1].strip()
    q_terms = set(tokenize(question))
    candidates: list[tuple[float, int, str, str, list[str]]] = []
    position = 0
    for doc_rank, (doc_id, body) in enumerate(_DOC.findall(prompt)):
        lines = [line for line in body.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if line.lstrip().startswith(("#", "|")):
                continue
            followers = [_clean(f) for f in lines[i + 1 : i + 6] if _LIST_ITEM.match(f)]
            for sentence in re.split(r"(?<=[.!?])\s+", _clean(line)):
                if len(sentence) < 20:
                    continue
                overlap = len(q_terms & set(tokenize(sentence)))
                if overlap < 2 and not (overlap and len(q_terms) <= 2):
                    continue
                score = overlap + (0.3 if re.search(r"\d", sentence) else 0) - 0.1 * doc_rank
                tail = followers if sentence.endswith(":") else []
                candidates.append((score, position, sentence, doc_id, tail))
                position += 1
    if not candidates:
        return INSUFFICIENT
    best = sorted(candidates, key=lambda c: (-c[0], c[1]))[:max_sentences]
    best.sort(key=lambda c: c[1])
    parts: list[str] = []
    for _, _, sentence, doc_id, tail in best:
        if tail:
            parts.append(f"{sentence} [{doc_id}]\n" + "\n".join(f"- {t}" for t in tail))
        else:
            parts.append(f"{sentence.rstrip('.')}. [{doc_id}]")
    return "\n".join(parts)


class MockLLM:
    provider = "mock"
    model = "mock-extractive-v1"

    def _usage(self, prompt: str, output: str) -> Usage:
        return Usage(
            self.provider,
            self.model,
            estimate_tokens(prompt),
            estimate_tokens(output),
            0.0,
        )

    async def generate(
        self,
        *,
        task: LLMTask,
        system: str,
        prompt: str,
        on_token: TokenCallback | None = None,
    ) -> LLMResult:
        if task == "answer":
            text = extractive_answer(prompt)
        elif task == "summarize":
            text = prompt.split("Draft:", 1)[-1].strip()
        else:
            text = prompt
        if on_token:
            for word in re.findall(r"\S+\s*", text):
                await on_token(word)
        return LLMResult(text=text, usage=self._usage(system + prompt, text))

    async def structured(
        self, *, task: LLMTask, system: str, prompt: str, schema: type[SchemaT]
    ) -> tuple[SchemaT, Usage]:
        if task == "route":
            result: BaseModel = schema.model_validate(
                {"next_agent": mock_route(prompt), "reason": "keyword rules (mock)"}
            )
        elif task == "plan_actions":
            result = parse_action_request(prompt)
        else:
            raise ValueError(f"Mock structured output not supported for task {task}")
        return cast(SchemaT, result), self._usage(system + prompt, result.model_dump_json())


_SEVERITY = re.compile(r"\b(P[1-4])\b|\b(critical|high|medium|low) (priority|severity)\b", re.I)
_SEVERITY_WORDS = {"critical": "P1", "high": "P2", "medium": "P3", "low": "P4"}
_STATUS = re.compile(r"\b(?:to|as|status)\s+(resolved|monitoring|active)\b", re.I)


def parse_action_request(message: str) -> ActionPlan:
    text = message.lower()
    customers = re.findall(r"\b(1\d{4})\b", message)
    incidents = [i.upper() for i in re.findall(r"\bINC-\d{4}\b", message, re.I)]
    severity = "P2"
    if match := _SEVERITY.search(message):
        severity = (match.group(1) or _SEVERITY_WORDS[match.group(2).lower()]).upper()
    actions: list[PlannedAction] = []
    wants_update = re.search(r"\b(update|close|resolve|escalate)\b[^.]*\binc-\d{4}", text)
    if wants_update and incidents:
        status_match = _STATUS.search(message)
        actions.append(
            PlannedAction(
                tool="update_incident",
                arguments={
                    "incident_id": incidents[0],
                    "status": status_match.group(1).upper() if status_match else None,
                    "severity": severity if _SEVERITY.search(message) else None,
                    "note": message,
                },
            )
        )
    if re.search(r"\b(create|open|raise|log)\b[^.]*\b(incident|ticket)\b", text):
        actions.append(
            PlannedAction(
                tool="create_incident",
                arguments={
                    "title": "Customer impact"
                    + (f" linked to {incidents[0]}" if incidents else ""),
                    "description": message,
                    "severity": severity,
                    "customer_ids": customers,
                    "related_incident_id": incidents[0] if incidents else None,
                },
            )
        )
    if re.search(r"\bnotify|\bnotification|\balert the\b", text):
        channel = "support-team"
        for name in ("l2-mobile-core", "l2-fixed-access", "l3-network", "duty-manager"):
            if name.replace("-", " ") in text or name in text:
                channel = name
        actions.append(
            PlannedAction(
                tool="create_notification",
                arguments={
                    "channel": channel,
                    "message": "Customer-affecting issue"
                    + (f" related to {incidents[0]}" if incidents else "")
                    + " requires support attention.",
                    "incident_id": incidents[0] if incidents else None,
                },
            )
        )
    return ActionPlan(customer_ids=customers, incident_ids=incidents, actions=actions)
