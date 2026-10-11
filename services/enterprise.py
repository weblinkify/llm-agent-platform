"""Simulated enterprise systems (CRM, product catalogue, incident management,
network status, notifications). They are seeded from `data/enterprise` and are
only reachable by agents through the MCP server."""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter

from services.models import (
    Customer,
    Incident,
    IncidentStatus,
    NetworkStatus,
    Notification,
    Product,
    Severity,
)


class NotFoundError(LookupError):
    pass


def _load[ModelT: BaseModel](path: Path, model: type[ModelT]) -> list[ModelT]:
    return TypeAdapter(list[model]).validate_json(path.read_text())  # type: ignore[valid-type]


class EnterpriseSystems:
    def __init__(self, data_dir: Path) -> None:
        self._lock = threading.Lock()
        self.customers = {c.customer_id: c for c in _load(data_dir / "customers.json", Customer)}
        self.products = {p.product_id: p for p in _load(data_dir / "products.json", Product)}
        self.incidents = {i.incident_id: i for i in _load(data_dir / "incidents.json", Incident)}
        self.regions: dict[str, dict[str, object]] = {
            r["location"].lower(): r for r in json.loads((data_dir / "network.json").read_text())
        }
        self.notifications: list[Notification] = []
        self._next_incident = 2001

    # Customers
    def get_customer(self, customer_id: str) -> Customer:
        try:
            return self.customers[customer_id]
        except KeyError:
            raise NotFoundError(f"Customer {customer_id} not found") from None

    def search_customers(self, query: str, limit: int = 10) -> list[Customer]:
        q = query.lower()
        return [
            c
            for c in self.customers.values()
            if q in c.name.lower() or q in c.city.lower() or q == c.customer_id
        ][:limit]

    def get_customer_services(self, customer_id: str) -> list[Product]:
        customer = self.get_customer(customer_id)
        return [self.products[pid] for pid in customer.services if pid in self.products]

    # Products
    def get_product(self, product_id: str) -> Product:
        try:
            return self.products[product_id.upper()]
        except KeyError:
            raise NotFoundError(f"Product {product_id} not found") from None

    def search_products(
        self, query: str = "", five_g_only: bool = False, limit: int = 10
    ) -> list[Product]:
        q = query.lower()
        return [
            p
            for p in self.products.values()
            if (not q or q in f"{p.name} {p.category} {p.description}".lower())
            and (p.five_g_enabled or not five_g_only)
        ][:limit]

    # Incidents
    def get_incident(self, incident_id: str) -> Incident:
        try:
            return self.incidents[incident_id.upper()]
        except KeyError:
            raise NotFoundError(f"Incident {incident_id} not found") from None

    def search_incidents(
        self,
        location: str | None = None,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[Incident]:
        return [
            i
            for i in self.incidents.values()
            if (not location or i.location.lower() == location.lower())
            and (not status or i.status == status.upper())
            and (not severity or i.severity == severity.upper())
        ]

    def create_incident(
        self,
        title: str,
        description: str,
        severity: Severity,
        location: str,
        customer_ids: list[str],
        related_incident_id: str | None,
    ) -> Incident:
        for cid in customer_ids:
            self.get_customer(cid)
        affected: list[str] = []
        if related_incident_id:
            affected = self.get_incident(related_incident_id).affected_services
        with self._lock:
            incident_id = f"INC-{self._next_incident}"
            self._next_incident += 1
            now = datetime.now(UTC)
            incident = Incident(
                incident_id=incident_id,
                title=title,
                status="OPEN",
                severity=severity,
                location=location,
                affected_services=affected,
                description=description,
                created_at=now,
                updated_at=now,
                customer_ids=customer_ids,
            )
            self.incidents[incident_id] = incident
        return incident

    def update_incident(
        self,
        incident_id: str,
        status: IncidentStatus | None,
        severity: Severity | None,
        note: str | None,
    ) -> Incident:
        incident = self.get_incident(incident_id)
        changes: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if status:
            changes["status"] = status
        if severity:
            changes["severity"] = severity
        if note:
            changes["description"] = f"{incident.description}\n[update] {note}"
        updated = incident.model_copy(update=changes)
        self.incidents[incident.incident_id] = updated
        return updated

    # Network
    def get_network_status(self, location: str) -> NetworkStatus:
        region = self.regions.get(location.lower())
        if region is None:
            raise NotFoundError(f"No network region named {location}")
        active = [
            i.incident_id
            for i in self.search_incidents(location=location)
            if i.status in ("ACTIVE", "OPEN")
        ]
        return NetworkStatus(
            location=str(region["location"]),
            status="DEGRADED" if active else "NORMAL",
            sites=int(str(region["sites"])),
            technologies=[str(t) for t in region["technologies"]],  # type: ignore[attr-defined]
            active_incidents=active,
        )

    def known_locations(self) -> list[str]:
        return [str(r["location"]) for r in self.regions.values()]

    # Notifications
    def create_notification(
        self, channel: str, message: str, incident_id: str | None
    ) -> Notification:
        if incident_id:
            self.get_incident(incident_id)
        notification = Notification(
            notification_id=f"NTF-{uuid4().hex[:8].upper()}",
            channel=channel,
            message=message,
            incident_id=incident_id,
            status="SENT",
            sent_at=datetime.now(UTC),
        )
        self.notifications.append(notification)
        return notification
