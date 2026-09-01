from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from creator.api.dependencies import (
    get_auth_client,
    get_current_user,
    get_storage_provider,
    get_uow,
)
from creator.config import Settings, get_settings
from creator.domain.auth import AuthSession, AuthSignupResult, Principal
from creator.infrastructure.auth import AuthLoginRejectedError, AuthSignupRejectedError
from creator.main import app, create_app
from creator.repositories import ImageRecord, UserRecord
from creator.services.storage.provider import StorageUrlError

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


class FakeImageRepository:
    def __init__(self, image: ImageRecord | None) -> None:
        self.image = image
        self.requests: list[dict[str, UUID]] = []

    def get_image_for_user(self, *, user_id: UUID, image_id: UUID) -> ImageRecord | None:
        self.requests.append({"user_id": user_id, "image_id": image_id})
        return self.image


class FakeUnitOfWork:
    def __init__(self, image: ImageRecord | None) -> None:
        self.image_generations = FakeImageRepository(image)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class FakeStorageProvider:
    def __init__(self, *, url_error: bool = False) -> None:
        self.url_error = url_error
        self.paths: list[str] = []

    def get_url(self, path: str) -> str:
        self.paths.append(path)
        if self.url_error:
            raise StorageUrlError("unavailable")
        return f"https://signed.example/{path}"


def stored_image(image_id: UUID) -> ImageRecord:
    return ImageRecord(
        id=image_id,
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        content_id=UUID("20000000-0000-0000-0000-000000000001"),
        generation_id=UUID("30000000-0000-0000-0000-000000000001"),
        version_number=1,
        storage_path="users/principal-123/contents/content/versions/1/image.png",
        public_url="https://expired.example/image.png",
        mime_type="image/png",
        width=512,
        height=512,
        model="gemini-image",
        prompt="Generate",
        metadata={"storage_provider": "local"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
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
async def test_get_image_returns_authorized_image_with_fresh_storage_url() -> None:
    image_id = UUID("40000000-0000-0000-0000-000000000001")
    image = stored_image(image_id)
    unit_of_work = FakeUnitOfWork(image)
    storage = FakeStorageProvider()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_storage_provider] = lambda: storage

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/images/{image_id}")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["public_url"] == (
        "https://signed.example/users/principal-123/contents/content/versions/1/image.png"
    )
    assert response.json()["data"]["metadata"] == {"storage_provider": "local"}
    assert storage.paths == [image.storage_path]
    assert unit_of_work.image_generations.requests == [
        {
            "user_id": UUID("00000000-0000-0000-0000-000000000001"),
            "image_id": image_id,
        }
    ]


@pytest.mark.anyio
async def test_get_image_returns_not_found_without_calling_storage_when_not_visible() -> None:
    image_id = UUID("40000000-0000-0000-0000-000000000001")
    unit_of_work = FakeUnitOfWork(None)
    storage = FakeStorageProvider()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_storage_provider] = lambda: storage

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/images/{image_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "IMAGE_NOT_FOUND"
    assert storage.paths == []


@pytest.mark.anyio
async def test_get_image_returns_storage_error_when_signed_url_is_unavailable() -> None:
    image_id = UUID("40000000-0000-0000-0000-000000000001")
    image = stored_image(image_id)
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: FakeUnitOfWork(image)
    application.dependency_overrides[get_storage_provider] = lambda: FakeStorageProvider(
        url_error=True
    )

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/images/{image_id}")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "STORAGE_URL_UNAVAILABLE"


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
