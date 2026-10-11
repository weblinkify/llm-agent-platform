from datetime import UTC, datetime, timedelta

import jwt

from core.models import Principal, Role
from core.settings import Settings

ALGORITHM = "HS256"


class AuthError(Exception):
    pass


def issue_token(principal: Principal, settings: Settings, ttl_minutes: int | None = None) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": principal.subject,
        "role": principal.role.value,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes or settings.jwt_ttl_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str, settings: Settings) -> Principal:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "role", "exp", "iss"]},
        )
        return Principal(subject=claims["sub"], role=Role(claims["role"]))
    except (jwt.PyJWTError, ValueError) as exc:
        raise AuthError(f"Invalid token: {exc}") from exc


def issue_approval_grant(
    approval_id: str, tools: list[str], approver: Principal, settings: Settings
) -> str:
    """Short-lived token proving a human approved these tool calls. The MCP
    server requires it for every sensitive tool, so a hijacked agent cannot
    execute writes on its own."""
    now = datetime.now(UTC)
    claims = {
        "sub": approver.subject,
        "role": approver.role.value,
        "iss": settings.jwt_issuer,
        "aud": "approval-grant",
        "approval_id": approval_id,
        "tools": tools,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def verify_approval_grant(token: str, tool: str, settings: Settings) -> str:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
            audience="approval-grant",
        )
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid approval grant: {exc}") from exc
    if tool not in claims.get("tools", []):
        raise AuthError(f"Approval grant does not cover {tool}")
    return str(claims["approval_id"])
