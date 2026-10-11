from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["P1", "P2", "P3", "P4"]
IncidentStatus = Literal["ACTIVE", "MONITORING", "RESOLVED", "OPEN"]


class Device(BaseModel):
    model: str
    five_g_capable: bool


class Sim(BaseModel):
    type: str
    five_g_supported: bool


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    phone: str
    city: str
    segment: Literal["CONSUMER", "BUSINESS"]
    account_status: Literal["ACTIVE", "SUSPENDED"]
    services: list[str]
    device: Device
    sim: Sim


class Product(BaseModel):
    product_id: str
    name: str
    category: str
    network_generation: str
    five_g_enabled: bool
    monthly_price_eur: float
    description: str


class Incident(BaseModel):
    incident_id: str
    title: str
    status: IncidentStatus
    severity: Severity
    location: str
    affected_services: list[str] = Field(default_factory=list)
    description: str
    created_at: datetime
    updated_at: datetime
    customer_ids: list[str] = Field(default_factory=list)


class NetworkStatus(BaseModel):
    location: str
    status: Literal["NORMAL", "DEGRADED"]
    sites: int
    technologies: list[str]
    active_incidents: list[str]


class Notification(BaseModel):
    notification_id: str
    channel: str
    message: str
    incident_id: str | None
    status: Literal["SENT"]
    sent_at: datetime
