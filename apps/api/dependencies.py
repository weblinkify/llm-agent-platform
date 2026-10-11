from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.service import ChatService
from core.models import Principal
from core.settings import Settings
from observability.metrics import SECURITY_EVENTS
from security.auth import AuthError, verify_token
from security.ratelimit import SlidingWindowRateLimiter

bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_service(request: Request) -> ChatService:
    service: ChatService = request.app.state.service
    return service


class Caller:
    def __init__(self, principal: Principal, token: str) -> None:
        self.principal = principal
        self.token = token


def get_caller(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Caller:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        principal = verify_token(credentials.credentials, request.app.state.settings)
    except AuthError as exc:
        SECURITY_EVENTS.labels("auth_failed").inc()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return Caller(principal, credentials.credentials)


def rate_limited(request: Request, caller: Annotated[Caller, Depends(get_caller)]) -> Caller:
    limiter: SlidingWindowRateLimiter = request.app.state.rate_limiter
    if not limiter.allow(caller.principal.subject):
        SECURITY_EVENTS.labels("rate_limited").inc()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded",
            headers={"Retry-After": "60"},
        )
    return caller
