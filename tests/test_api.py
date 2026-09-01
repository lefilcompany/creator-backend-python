from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from creator.api.dependencies import get_auth_client, get_current_user
from creator.config import Settings, get_settings
from creator.domain.auth import AuthSession, AuthSignupResult, Principal
from creator.infrastructure.auth import AuthLoginRejectedError, AuthSignupRejectedError
from creator.main import app, create_app
from creator.repositories import UserRecord

JWT_SECRET = "test-supabase-jwt-secret-with-32-bytes"
SUPABASE_URL = "https://creator-test.supabase.co"


def authenticated_app() -> object:
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: Settings(
        auth_required=True,
        supabase_url=SUPABASE_URL,
        supabase_jwt_secret=JWT_SECRET,
    )
    return application


def unauthenticated_app() -> object:
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: Settings(auth_required=False)
    return application


def authorized_app() -> object:
    application = authenticated_app()
    application.dependency_overrides[get_current_user] = lambda: UserRecord(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        external_id="principal-123",
        email="principal@example.com",
        display_name="Principal Example",
        global_role="membro",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )
    return application


class FakeAuthClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[dict[str, str]] = []

    def sign_in_with_password(self, *, email: str, password: str) -> AuthSession:
        self.requests.append({"email": email, "password": password})
        if self.error:
            raise self.error
        return AuthSession(
            access_token="access-token",
            refresh_token="refresh-token",
            token_type="bearer",
            expires_in=3600,
            principal=Principal(
                subject="principal-123",
                email=email,
                role="authenticated",
            ),
            provider="supabase",
            metadata={"aud": "authenticated"},
        )

    def sign_up_with_password(self, *, email: str, password: str) -> AuthSignupResult:
        self.requests.append({"email": email, "password": password})
        if self.error:
            raise self.error
        return AuthSignupResult(
            principal=Principal(
                subject="principal-123",
                email=email,
                role="authenticated",
            ),
            session=None,
            confirmation_required=True,
            provider="supabase",
            metadata={"aud": "authenticated"},
        )


def supabase_access_token() -> str:
    return jwt.encode(
        {
            "sub": "principal-123",
            "aud": "authenticated",
            "iss": f"{SUPABASE_URL}/auth/v1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
            "role": "authenticated",
            "session_id": "session-123",
        },
        JWT_SECRET,
        algorithm="HS256",
    )


@pytest.mark.anyio
async def test_health_returns_contract_envelope() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"] == {"status": "ok"}
    assert response.json()["meta"]["request_id"]
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_live_health_returns_contract_envelope() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"] == {"status": "ok"}
    assert response.json()["meta"]["request_id"]
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_reserved_route_returns_structured_error() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=authorized_app()), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/images/generate")

    assert response.status_code == 501
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"
    assert response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_login_returns_supabase_session_envelope() -> None:
    auth_client = FakeAuthClient()
    application = create_app()
    application.dependency_overrides[get_auth_client] = lambda: auth_client

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "principal@example.com", "password": "correct-password"},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["access_token"] == "access-token"
    assert response.json()["data"]["refresh_token"] == "refresh-token"
    assert response.json()["data"]["principal"] == {
        "subject": "principal-123",
        "email": "principal@example.com",
        "role": "authenticated",
    }
    assert auth_client.requests == [
        {"email": "principal@example.com", "password": "correct-password"}
    ]


@pytest.mark.anyio
async def test_login_rejects_invalid_credentials_with_structured_error() -> None:
    application = create_app()
    application.dependency_overrides[get_auth_client] = lambda: FakeAuthClient(
        AuthLoginRejectedError("rejected")
    )

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "principal@example.com", "password": "wrong-password"},
        )

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "LOGIN_REJECTED"
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_signup_returns_created_principal_without_session_when_confirmation_is_required() -> (
    None
):
    auth_client = FakeAuthClient()
    application = create_app()
    application.dependency_overrides[get_auth_client] = lambda: auth_client

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={"email": "new-principal@example.com", "password": "correct-password"},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["principal"] == {
        "subject": "principal-123",
        "email": "new-principal@example.com",
        "role": "authenticated",
    }
    assert response.json()["data"]["session"] is None
    assert response.json()["data"]["confirmation_required"] is True
    assert auth_client.requests == [
        {"email": "new-principal@example.com", "password": "correct-password"}
    ]


@pytest.mark.anyio
async def test_signup_rejects_invalid_request_with_structured_error() -> None:
    application = create_app()
    application.dependency_overrides[get_auth_client] = lambda: FakeAuthClient(
        AuthSignupRejectedError("rejected")
    )

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={"email": "new-principal@example.com", "password": "password"},
        )

    assert response.status_code == 400
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "SIGNUP_REJECTED"


@pytest.mark.anyio
async def test_api_v1_route_requires_auth_when_enabled() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=authenticated_app()), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/images/generate")

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "AUTHENTICATION_INVALID"
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_api_v1_route_accepts_valid_supabase_token_when_enabled() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=authorized_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Authorization": f"Bearer {supabase_access_token()}"},
        )

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"


@pytest.mark.anyio
async def test_swagger_and_openapi_are_available() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        docs_response = await client.get("/docs")
        openapi_response = await client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
    assert "/health" in openapi_response.json()["paths"]
    assert "/api/v1/auth/login" in openapi_response.json()["paths"]
    assert "/api/v1/auth/signup" in openapi_response.json()["paths"]


def test_application_factory_and_compatibility_entrypoint() -> None:
    assert create_app().title == "Creator API"
    assert app.title == "Creator API"
