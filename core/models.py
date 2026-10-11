from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    ADMIN = "ADMIN"
    AI_ENGINEER = "AI_ENGINEER"
    SUPPORT_AGENT = "SUPPORT_AGENT"
    READ_ONLY_USER = "READ_ONLY_USER"


class Principal(BaseModel):
    """The authenticated caller on whose behalf agents and tools act."""

    subject: str
    role: Role
