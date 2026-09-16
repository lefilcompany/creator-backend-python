from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from creator.api.dependencies import (
    get_current_user,
    get_metrics_registry,
    get_optional_principal,
    get_rate_limiter,
)
from creator.config import Settings, get_settings
from creator.domain.auth import Principal
from creator.infrastructure.metrics import MetricsRegistry
from creator.infrastructure.rate_limit import (
    REDIS_SLIDING_WINDOW_SCRIPT,
    InMemoryRateLimitBackend,
    RateLimitBackend,
    RateLimitBackendError,
    RateLimiter,
    RedisRateLimitBackend,
    create_rate_limiter,
)
from creator.main import create_app
from creator.repositories import UserRecord


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class FailingBackend(RateLimitBackend):
    def consume(self, *, key: str, limit: int, window_seconds: float):
        raise RateLimitBackendError("redis unavailable")


class FakeRedis:
    def __init__(self, result: list[int] | Exception) -> None:
        self.result = result
        self.calls: list[tuple[object, ...]] = []

    def eval(self, *args: object) -> list[int]:
        self.calls.append(args)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def user_record() -> UserRecord:
    now = datetime.now(UTC)
    return UserRecord(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        external_id="principal-123",
        email="principal@example.com",
        display_name="Principal",
        global_role="membro",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


def make_limiter(
    backend: RateLimitBackend,
    *,
    metrics: MetricsRegistry | None = None,
) -> RateLimiter:
    return RateLimiter(
        backend,
        limit=5,
        window_seconds=1.0,
        key_prefix="creator:rate-limit:v1",
        metrics=metrics or MetricsRegistry(),
    )


def test_in_memory_sliding_window_and_reset() -> None:
    clock = FakeClock()
    backend = InMemoryRateLimitBackend(clock=clock)

    decisions = [
        backend.consume(key="key", limit=5, window_seconds=1.0)
        for _ in range(6)
    ]

    assert [decision.allowed for decision in decisions] == [True] * 5 + [False]
    assert decisions[5].retry_after_seconds == 1

    clock.now += 1.0
    assert backend.consume(key="key", limit=5, window_seconds=1.0).allowed


def test_rate_limiter_isolates_identity_class_and_endpoint() -> None:
    limiter = make_limiter(InMemoryRateLimitBackend())

    for _ in range(5):
        assert limiter.check(
            rate_class="cheap",
            endpoint="GET /api/v1/users/me",
            identity="principal:user-1",
        ).allowed

    assert not limiter.check(
        rate_class="cheap",
        endpoint="GET /api/v1/users/me",
        identity="principal:user-1",
    ).allowed
    assert limiter.check(
        rate_class="cheap",
        endpoint="GET /api/v1/users/me",
        identity="principal:user-2",
    ).allowed
    assert limiter.check(
        rate_class="generation",
        endpoint="POST /api/v1/content/generate",
        identity="principal:user-1",
    ).allowed


def test_in_memory_backend_is_atomic_under_concurrency() -> None:
    backend = InMemoryRateLimitBackend()

    with ThreadPoolExecutor(max_workers=16) as executor:
        decisions = list(
            executor.map(
                lambda _: backend.consume(key="key", limit=5, window_seconds=1.0),
                range(100),
            )
        )

    assert sum(decision.allowed for decision in decisions) == 5


def test_redis_backend_uses_atomic_sliding_window_script() -> None:
    connection = FakeRedis([1, 1000, 4])
    backend = RedisRateLimitBackend(connection)  # type: ignore[arg-type]

    decision = backend.consume(key="creator:rate-limit:key", limit=5, window_seconds=1.0)

    assert decision.allowed
    assert decision.remaining == 4
    assert "redis.call('TIME')" in REDIS_SLIDING_WINDOW_SCRIPT
    assert "ZREMRANGEBYSCORE" in REDIS_SLIDING_WINDOW_SCRIPT
    assert "ZADD" in REDIS_SLIDING_WINDOW_SCRIPT
    assert connection.calls[0][1] == 1


def test_redis_backend_wraps_backend_errors() -> None:
    backend = RedisRateLimitBackend(
        FakeRedis(RedisConnectionError("down"))  # type: ignore[arg-type]
    )

    with pytest.raises(RateLimitBackendError):
        backend.consume(key="key", limit=5, window_seconds=1.0)


def test_memory_backend_is_rejected_in_production() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        create_rate_limiter(
            Settings(_env_file=None, app_env="production", rate_limit_backend="memory"),
            MetricsRegistry(),
        )


@pytest.mark.anyio
async def test_api_returns_rate_limit_envelope_and_retry_headers() -> None:
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        auth_required=True,
        rate_limit_backend="memory",
    )
    application.dependency_overrides[get_current_user] = user_record
    application.dependency_overrides[get_optional_principal] = lambda: Principal(
        subject="principal-123",
        email="principal@example.com",
        role="authenticated",
    )
    application.dependency_overrides[get_rate_limiter] = lambda: make_limiter(
        InMemoryRateLimitBackend()
    )

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        responses = [await client.get("/api/v1/users/me") for _ in range(6)]

    response = responses[-1]
    assert response.status_code == 429
    assert response.json()["error"] == {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Rate limit exceeded for this endpoint",
    }
    assert response.headers["Retry-After"] == "1"
    assert response.headers["RateLimit-Limit"] == "5"
    assert response.headers["RateLimit-Remaining"] == "0"
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_rate_limiter_failure_is_fail_open_for_cheap_and_closed_for_generation() -> None:
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        auth_required=True,
        rate_limit_backend="memory",
    )
    application.dependency_overrides[get_current_user] = user_record
    application.dependency_overrides[get_optional_principal] = lambda: Principal(
        subject="principal-123",
        email="principal@example.com",
        role="authenticated",
    )
    application.dependency_overrides[get_rate_limiter] = lambda: make_limiter(FailingBackend())

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        cheap_response = await client.get("/api/v1/users/me")
        generation_response = await client.post(
            "/api/v1/content/generate",
            json={
                "workspace_id": "00000000-0000-0000-0000-000000000001",
                "topic": "launch",
                "audience": "customers",
                "content_type": "social_post",
            },
        )

    assert cheap_response.status_code == 200
    assert generation_response.status_code == 503
    assert generation_response.json()["error"]["code"] == "RATE_LIMITER_UNAVAILABLE"
    assert generation_response.headers["Retry-After"] == "1"


@pytest.mark.anyio
async def test_metrics_are_exposed_without_user_cardinality() -> None:
    metrics = MetricsRegistry()
    limiter = make_limiter(InMemoryRateLimitBackend(), metrics=metrics)
    limiter.check(
        rate_class="cheap",
        endpoint="GET /api/v1/users/me",
        identity="principal:secret-user",
    )
    application = create_app()
    application.dependency_overrides[get_metrics_registry] = lambda: metrics

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "creator_rate_limit_requests_total" in response.text
    assert "secret-user" not in response.text
    assert "principal" not in response.text


def test_runtime_openapi_documents_rate_limit_responses() -> None:
    schema = create_app().openapi()

    for path, path_item in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for operation in path_item.values():
            if isinstance(operation, dict) and "responses" in operation:
                assert "429" in operation["responses"]

    for path in {
        "/api/v1/content/generate",
        "/api/v1/content/improve",
        "/api/v1/images/generate",
        "/api/v1/images/{id}/regenerate",
    }:
        assert "503" in schema["paths"][path]["post"]["responses"]
