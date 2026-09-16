import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from creator.application.unit_of_work import UnitOfWork
from creator.config import Settings, get_settings
from creator.domain.auth import Principal
from creator.infrastructure.auth import (
    AccessTokenExpiredError,
    AccessTokenInvalidError,
    AuthClient,
    AuthConfigurationError,
    create_auth_client,
    create_auth_token_verifier,
)
from creator.infrastructure.metrics import MetricsRegistry
from creator.infrastructure.queue import RqGenerationQueue
from creator.infrastructure.queue import get_generation_queue as get_rq_generation_queue
from creator.infrastructure.rate_limit import (
    RateLimitBackendError,
    RateLimiter,
    create_rate_limiter,
)
from creator.infrastructure.storage import create_storage_provider
from creator.infrastructure.unit_of_work import get_unit_of_work
from creator.repositories import UserRecord
from creator.services.ai.factory import create_llm_provider
from creator.services.ai.provider import LLMProvider
from creator.services.storage.provider import StorageConfigurationError, StorageProvider

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="SupabaseBearerAuth")
logger = logging.getLogger(__name__)


def _auth_exception(
    code: str,
    message: str,
    *,
    status_code: int = status.HTTP_401_UNAUTHORIZED,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def get_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | str | None,
        Security(bearer_scheme),
    ] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> Principal | None:
    token = _bearer_token(credentials)
    if token is None:
        if settings.auth_required:
            raise _invalid_auth_exception()
        return None

    verifier = create_auth_token_verifier(settings)
    try:
        return verifier.verify(token)
    except AuthConfigurationError as error:
        if not settings.auth_required:
            return None
        raise _auth_exception(
            "AUTHENTICATION_MISCONFIGURED",
            "Authentication is not configured",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from error
    except (AccessTokenExpiredError, AccessTokenInvalidError) as error:
        raise _invalid_auth_exception() from error


def get_optional_principal(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> Principal | None:
    """Validate a supplied token without making authentication mandatory.

    The global rate-limit dependency must be able to rate-limit public Auth routes
    by IP before the endpoint's own authentication requirements are evaluated.
    """
    token = request.headers.get("Authorization")
    if not token:
        return None

    bearer_token = _bearer_token(token)
    if bearer_token is None:
        return None
    verifier = create_auth_token_verifier(settings)
    try:
        return verifier.verify(bearer_token)
    except AuthConfigurationError as error:
        if not settings.auth_required:
            return None
        raise _auth_exception(
            "AUTHENTICATION_MISCONFIGURED",
            "Authentication is not configured",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from error
    except (AccessTokenExpiredError, AccessTokenInvalidError) as error:
        raise _invalid_auth_exception() from error


def get_uow(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> UnitOfWork:
    return unit_of_work


def get_current_user(
    principal: Annotated[Principal | None, Depends(get_principal)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_uow)],
) -> UserRecord:
    if principal is None:
        raise _invalid_auth_exception()

    existing = unit_of_work.users.get_by_external_id(principal.subject, include_deleted=True)
    if existing is not None and existing.deleted_at is not None:
        raise _invalid_auth_exception()
    if existing is None:
        user = unit_of_work.users.add(
            external_id=principal.subject,
            email=principal.email,
            display_name=_display_name_from_claims(principal),
        )
        unit_of_work.commit()
        return user

    display_name = _display_name_from_claims(principal)
    if (principal.email and principal.email != existing.email) or (
        display_name and display_name != existing.display_name
    ):
        user = unit_of_work.users.update_profile(
            existing.id,
            email=principal.email,
            display_name=display_name,
        )
        unit_of_work.commit()
        return user
    return existing


def get_auth_client(
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> AuthClient:
    return create_auth_client(settings)


def get_llm_provider(
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> LLMProvider:
    return create_llm_provider(settings)


def get_storage_provider(
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> StorageProvider:
    try:
        return create_storage_provider(settings)
    except StorageConfigurationError as error:
        raise _auth_exception(
            "STORAGE_MISCONFIGURED",
            "Storage is not configured",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from error


def get_generation_queue() -> RqGenerationQueue:
    return get_rq_generation_queue()


def get_metrics_registry(request: Request) -> MetricsRegistry:
    registry = getattr(request.app.state, "metrics_registry", None)
    if not isinstance(registry, MetricsRegistry):
        registry = MetricsRegistry()
        request.app.state.metrics_registry = registry
    return registry


def get_rate_limiter(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
    metrics: Annotated[MetricsRegistry, Depends(get_metrics_registry)] = None,  # type: ignore[assignment]
) -> RateLimiter:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if not isinstance(limiter, RateLimiter):
        limiter = create_rate_limiter(settings, metrics)
        request.app.state.rate_limiter = limiter
    return limiter


GENERATION_RATE_LIMIT_ENDPOINTS = frozenset(
    {
        "POST /api/v1/content/generate",
        "POST /api/v1/content/improve",
        "POST /api/v1/images/generate",
        "POST /api/v1/images/{id}/regenerate",
    }
)
AUTH_RATE_LIMIT_ENDPOINTS = frozenset(
    {
        "POST /api/v1/auth/login",
        "POST /api/v1/auth/signup",
    }
)
ROUTE_ALIASES = {
    "GET /api/v1/content": "GET /api/v1/contents",
    "GET /api/v1/content/{id}": "GET /api/v1/contents/{id}",
    "DELETE /api/v1/content/{id}": "DELETE /api/v1/contents/{id}",
}


def enforce_rate_limit(
    request: Request,
    principal: Annotated[Principal | None, Depends(get_optional_principal)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    path = request.url.path
    if not path.startswith("/api/v1/"):
        return

    route = request.scope.get("route")
    route_path = getattr(route, "path", path)
    route_key = f"{request.method.upper()} {route_path}"
    endpoint = ROUTE_ALIASES.get(route_key, route_key)
    rate_class = "generation" if endpoint in GENERATION_RATE_LIMIT_ENDPOINTS else "cheap"

    if endpoint in AUTH_RATE_LIMIT_ENDPOINTS:
        client_host = request.client.host if request.client else "unknown"
        identity = f"ip:{client_host}"
    elif principal is not None:
        identity = f"principal:{principal.subject}"
    else:
        # The endpoint's authentication dependency remains authoritative.
        return

    try:
        decision = limiter.check(
            rate_class=rate_class,
            endpoint=endpoint,
            identity=identity,
        )
    except RateLimitBackendError as error:
        if rate_class == "cheap":
            logger.warning(
                "Rate limiter unavailable; allowing cheap request",
                extra={"rate_limit_class": rate_class, "rate_limit_endpoint": endpoint},
            )
            return
        logger.error(
            "Rate limiter unavailable; rejecting generation request",
            extra={"rate_limit_class": rate_class, "rate_limit_endpoint": endpoint},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "RATE_LIMITER_UNAVAILABLE",
                "message": "Rate limiter is temporarily unavailable",
            },
            headers={"Retry-After": "1"},
        ) from error

    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Rate limit exceeded for this endpoint",
            },
            headers={
                "Retry-After": str(decision.retry_after_seconds),
                "RateLimit-Limit": str(limiter.limit),
                "RateLimit-Remaining": str(decision.remaining),
                "RateLimit-Reset": str(decision.reset_seconds),
            },
        )


def _invalid_auth_exception() -> HTTPException:
    return _auth_exception("AUTHENTICATION_INVALID", "Authentication failed")


def _bearer_token(credentials: HTTPAuthorizationCredentials | str | None) -> str | None:
    if credentials is None:
        return None
    if isinstance(credentials, str):
        scheme, _, token = credentials.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise _invalid_auth_exception()
        return token
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _invalid_auth_exception()
    return credentials.credentials


def _display_name_from_claims(principal: Principal) -> str | None:
    user_metadata = principal.claims.get("user_metadata")
    if not isinstance(user_metadata, dict):
        return None
    for key in ("display_name", "full_name", "name"):
        value = user_metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None
