from storage.models import Approval, ApprovalStatus, AuditEvent


class InMemoryAuditLog:
    def __init__(self, max_events: int = 5000) -> None:
        self._events: list[AuditEvent] = []
        self._max = max_events

    async def write(self, event: AuditEvent) -> None:
        self._events.append(event)
        del self._events[: -self._max]

    async def list(self, limit: int = 100, request_id: str | None = None) -> list[AuditEvent]:
        events = [e for e in self._events if request_id is None or e.request_id == request_id]
        return list(reversed(events[-limit:]))


class InMemoryApprovalStore:
    def __init__(self) -> None:
        self._items: dict[str, Approval] = {}

    async def create(self, approval: Approval) -> Approval:
        self._items[approval.approval_id] = approval
        return approval

    async def get(self, approval_id: str) -> Approval | None:
        return self._items.get(approval_id)

    async def list(self, status: ApprovalStatus | None = None) -> list[Approval]:
        items = [a for a in self._items.values() if status is None or a.status == status]
        return sorted(items, key=lambda a: a.created_at, reverse=True)

    async def save(self, approval: Approval) -> None:
        self._items[approval.approval_id] = approval
