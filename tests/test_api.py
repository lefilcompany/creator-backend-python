from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from creator.api.dependencies import (
    get_auth_client,
    get_current_user,
    get_generation_queue,
    get_llm_provider,
    get_storage_provider,
    get_uow,
)
from creator.application.image_generation import image_generation_request_fingerprint
from creator.config import Settings, get_settings
from creator.domain.auth import AuthSession, AuthSignupResult, Principal
from creator.domain.exceptions import PersistenceError
from creator.domain.generation import GenerationJobStatus
from creator.infrastructure.auth import AuthLoginRejectedError, AuthSignupRejectedError
from creator.integrations.gemini.exceptions import GeminiTimeoutError
from creator.main import app, create_app
from creator.repositories import (
    AssetRecord,
    BrandRecord,
    BrandSettingsRecord,
    ContentRecord,
    GeneratedTextContentRecord,
    GenerationJobRecord,
    GenerationRecord,
    ImageGenerationStatusRecord,
    ImageRecord,
    Page,
    ProjectRecord,
    SettingsRecord,
    UserRecord,
    WorkspaceRecord,
)
from creator.repositories.common import PageRequest
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


def admin_app() -> object:
    application = authenticated_app()
    application.dependency_overrides[get_current_user] = lambda: user_record(
        UUID("00000000-0000-0000-0000-000000000001"),
        global_role="admin",
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


class FakeContentRepository:
    def __init__(
        self,
        content: ContentRecord | None,
        *,
        page: Page[ContentRecord] | None = None,
        workspace_access: bool = True,
        create_error: Exception | None = None,
    ) -> None:
        self.content = content
        self.page = page
        self.workspace_access = workspace_access
        self.create_error = create_error
        self.requests: list[dict[str, UUID]] = []
        self.workspace_requests: list[dict[str, UUID]] = []
        self.created_text_generations: list[dict[str, object]] = []
        self.created: list[dict[str, object]] = []
        self.updated: list[dict[str, object]] = []
        self.deleted: list[UUID] = []

    def add(self, **kwargs: object) -> ContentRecord:
        self.created.append(kwargs)
        return content_record(UUID("21000000-0000-0000-0000-000000000001"))

    def get_by_id_for_user(self, *, user_id: UUID, content_id: UUID) -> ContentRecord | None:
        self.requests.append({"user_id": user_id, "content_id": content_id})
        return self.content

    def user_has_workspace_access(self, *, user_id: UUID, workspace_id: UUID) -> bool:
        self.workspace_requests.append({"user_id": user_id, "workspace_id": workspace_id})
        return self.workspace_access

    def create_text_generation(self, **kwargs: object) -> GeneratedTextContentRecord:
        self.created_text_generations.append(kwargs)
        if self.create_error is not None:
            raise self.create_error
        return GeneratedTextContentRecord(
            content=ContentRecord(
                id=UUID("21000000-0000-0000-0000-000000000001"),
                workspace_id=kwargs["workspace_id"],
                created_by_user_id=kwargs["requested_by_user_id"],
                content_type="TEXT",
                title=str(kwargs["title"]),
                payload=kwargs["payload"],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                deleted_at=None,
            ),
            generation_id=UUID("61000000-0000-0000-0000-000000000001"),
            generation_model=str(kwargs["model"]),
            generation_parameters=kwargs["parameters"],
        )

    def list_for_user(
        self,
        *,
        user_id: UUID,
        page: PageRequest,
        filters: object | None = None,
    ) -> Page[ContentRecord]:
        if self.page is not None:
            return self.page
        return Page(items=[], total=0, page=page.page, limit=page.limit)

    def update(self, content_id: UUID, **kwargs: object) -> ContentRecord:
        self.updated.append({"content_id": content_id, **kwargs})
        return content_record(content_id)

    def soft_delete(self, content_id: UUID) -> None:
        self.deleted.append(content_id)


class FakeSettingsRepository:
    def __init__(self, settings: SettingsRecord | None = None) -> None:
        self.settings = settings
        self.requests: list[UUID] = []
        self.created: list[UUID] = []
        self.updated: list[dict[str, object]] = []

    def get_by_user_id(self, user_id: UUID) -> SettingsRecord | None:
        self.requests.append(user_id)
        return self.settings

    def get_or_create_for_user(self, user_id: UUID) -> SettingsRecord:
        self.requests.append(user_id)
        if self.settings is None:
            self.settings = settings_record()
            self.created.append(user_id)
        return self.settings

    def update_partial(self, user_id: UUID, changes: dict[str, object]) -> SettingsRecord:
        self.updated.append({"user_id": user_id, "changes": changes})
        current = self.settings or settings_record()
        self.settings = SettingsRecord(
            id=current.id,
            user_id=current.user_id,
            brand_name=changes.get("brand_name", current.brand_name),  # type: ignore[arg-type]
            segment=changes.get("segment", current.segment),  # type: ignore[arg-type]
            tone=str(changes.get("tone", current.tone)),
            voice=str(changes.get("voice", current.voice)),
            visual_style=str(changes.get("visual_style", current.visual_style)),
            default_preferences=changes.get(  # type: ignore[arg-type]
                "default_preferences", current.default_preferences
            ),
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
        )
        return self.settings


class FakeImageGenerationRepository:
    def __init__(
        self,
        *,
        status: ImageGenerationStatusRecord | None = None,
        existing: ImageGenerationStatusRecord | None = None,
    ) -> None:
        self.status = status
        self.existing = existing
        self.created: list[dict[str, object]] = []
        self.status_requests: list[dict[str, UUID]] = []
        self.external_requests: list[dict[str, object]] = []

    def get_status_by_external_id_for_user(
        self,
        *,
        user_id: UUID,
        external_id: str,
    ) -> ImageGenerationStatusRecord | None:
        self.external_requests.append({"user_id": user_id, "external_id": external_id})
        return self.existing

    def create_image_generation(self, **kwargs: object) -> GenerationJobRecord:
        self.created.append(kwargs)
        return job_record(
            job_id=UUID("50000000-0000-0000-0000-000000000001"),
            content_id=kwargs["content_id"],
            generation_id=UUID("60000000-0000-0000-0000-000000000001"),
            status=GenerationJobStatus.PENDING,
            external_id=kwargs.get("external_id"),
        )

    def get_status_for_user(
        self,
        *,
        user_id: UUID,
        job_id: UUID,
    ) -> ImageGenerationStatusRecord | None:
        self.status_requests.append({"user_id": user_id, "job_id": job_id})
        return self.status


class FakeUserRepository:
    def __init__(self) -> None:
        self.user = user_record(UUID("00000000-0000-0000-0000-000000000002"))
        self.deleted: list[UUID] = []

    def add(self, **kwargs: object) -> UserRecord:
        return UserRecord(
            id=UUID("00000000-0000-0000-0000-000000000003"),
            external_id=str(kwargs["external_id"]),
            email=kwargs.get("email") if isinstance(kwargs.get("email"), str) else None,
            display_name=kwargs.get("display_name")
            if isinstance(kwargs.get("display_name"), str)
            else None,
            global_role=str(kwargs.get("global_role", "membro")),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deleted_at=None,
        )

    def list(self, *, page: PageRequest, include_deleted: bool = False) -> Page[UserRecord]:
        return Page(items=[self.user], total=1, page=page.page, limit=page.limit)

    def get_by_id(self, user_id: UUID, *, include_deleted: bool = False) -> UserRecord | None:
        return self.user if user_id == self.user.id else None

    def update(self, user_id: UUID, **kwargs: object) -> UserRecord:
        return user_record(user_id, global_role=str(kwargs.get("global_role") or "membro"))

    def soft_delete(self, user_id: UUID) -> None:
        self.deleted.append(user_id)


class FakeWorkspaceRepository:
    def __init__(self, *, writable: bool = True) -> None:
        self.writable = writable
        self.workspace = workspace_record(UUID("10000000-0000-0000-0000-000000000001"))

    def user_has_workspace_role(
        self, *, user_id: UUID, workspace_id: UUID, minimum_role: str = "viewer"
    ) -> bool:
        return self.writable

    def add(self, *, name: str, owner_user_id: UUID) -> WorkspaceRecord:
        return workspace_record(UUID("10000000-0000-0000-0000-000000000002"), name=name)

    def list_for_user(self, *, user_id: UUID, page: PageRequest) -> Page[WorkspaceRecord]:
        return Page(items=[self.workspace], total=1, page=page.page, limit=page.limit)

    def get_for_user(
        self, *, user_id: UUID, workspace_id: UUID, include_deleted: bool = False
    ) -> WorkspaceRecord | None:
        return self.workspace if workspace_id == self.workspace.id else None

    def update(self, *, user_id: UUID, workspace_id: UUID, name: str) -> WorkspaceRecord:
        return workspace_record(workspace_id, name=name)

    def soft_delete(self, *, user_id: UUID, workspace_id: UUID) -> None:
        return None


class FakeCrudRepository:
    def __init__(self, record: object) -> None:
        self.record = record
        self.created: list[dict[str, object]] = []

    def add(self, **kwargs: object) -> object:
        self.created.append(kwargs)
        return self.record

    def get_for_user(self, **kwargs: object) -> object:
        return self.record

    def list_for_user(self, *, page: PageRequest, **kwargs: object) -> Page[object]:
        return Page(items=[self.record], total=1, page=page.page, limit=page.limit)

    def update(self, **kwargs: object) -> object:
        return self.record

    def soft_delete(self, **kwargs: object) -> None:
        return None

    def upsert(self, **kwargs: object) -> object:
        return self.record


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        content: ContentRecord | None = None,
        content_page: Page[ContentRecord] | None = None,
        workspace_access: bool = True,
        content_create_error: Exception | None = None,
        settings_record: SettingsRecord | None = None,
        status: ImageGenerationStatusRecord | None = None,
        existing: ImageGenerationStatusRecord | None = None,
    ) -> None:
        self.users = FakeUserRepository()
        self.workspaces = FakeWorkspaceRepository(writable=workspace_access)
        self.brands = FakeCrudRepository(brand_record())
        self.projects = FakeCrudRepository(project_record())
        self.contents = FakeContentRepository(
            content,
            page=content_page,
            workspace_access=workspace_access,
            create_error=content_create_error,
        )
        self.generations = FakeCrudRepository(generation_record())
        self.assets = FakeCrudRepository(asset_record())
        self.brand_settings = FakeCrudRepository(brand_settings_record())
        self.settings = FakeSettingsRepository(settings_record)
        self.image_generations = FakeImageGenerationRepository(status=status, existing=existing)
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeLLMProvider:
    def __init__(
        self,
        *,
        output: str = "Generated launch copy",
        error: Exception | None = None,
    ) -> None:
        self.output = output
        self.error = error
        self.prompts: list[str] = []

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.output


class FakeGenerationQueue:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    def enqueue(self, f: str, *args: object, job_id: str) -> object:
        self.calls.append({"f": f, "args": args, "job_id": job_id})
        if self.error:
            raise self.error
        return object()


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


def content_record(content_id: UUID) -> ContentRecord:
    return ContentRecord(
        id=content_id,
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        created_by_user_id=UUID("00000000-0000-0000-0000-000000000001"),
        content_type="IMAGE",
        title="Launch campaign",
        payload={"produto": "Creator Pro", "oferta": "30 dias gratis"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def user_record(user_id: UUID, *, global_role: str = "membro") -> UserRecord:
    return UserRecord(
        id=user_id,
        external_id=f"principal-{user_id}",
        email="user@example.com",
        display_name="User Example",
        global_role=global_role,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def workspace_record(workspace_id: UUID, *, name: str = "Workspace") -> WorkspaceRecord:
    return WorkspaceRecord(
        id=workspace_id,
        name=name,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def brand_record() -> BrandRecord:
    return BrandRecord(
        id=UUID("31000000-0000-0000-0000-000000000001"),
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        created_by_user_id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Lefil",
        description="Brand description",
        brand_voice="Clear",
        metadata={"segment": "creator"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def project_record() -> ProjectRecord:
    return ProjectRecord(
        id=UUID("32000000-0000-0000-0000-000000000001"),
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        brand_id=UUID("31000000-0000-0000-0000-000000000001"),
        created_by_user_id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Launch",
        description="Launch project",
        status="ACTIVE",
        metadata={"channel": "email"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def generation_record() -> GenerationRecord:
    return GenerationRecord(
        id=UUID("33000000-0000-0000-0000-000000000001"),
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        content_id=UUID("21000000-0000-0000-0000-000000000001"),
        brand_id=UUID("31000000-0000-0000-0000-000000000001"),
        project_id=UUID("32000000-0000-0000-0000-000000000001"),
        requested_by_user_id=UUID("00000000-0000-0000-0000-000000000001"),
        generation_type="TEXT",
        model="gemini-2.5-flash",
        prompt="Write launch copy",
        parameters={"temperature": 0.7},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def asset_record() -> AssetRecord:
    return AssetRecord(
        id=UUID("34000000-0000-0000-0000-000000000001"),
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        brand_id=UUID("31000000-0000-0000-0000-000000000001"),
        project_id=UUID("32000000-0000-0000-0000-000000000001"),
        content_id=UUID("21000000-0000-0000-0000-000000000001"),
        uploaded_by_user_id=UUID("00000000-0000-0000-0000-000000000001"),
        asset_type="image",
        storage_path="workspaces/ws/assets/a.png",
        public_url="https://example.com/a.png",
        mime_type="image/png",
        byte_size=123,
        checksum="sha256:abc",
        metadata={"alt": "asset"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def brand_settings_record() -> BrandSettingsRecord:
    return BrandSettingsRecord(
        id=UUID("35000000-0000-0000-0000-000000000001"),
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        brand_id=UUID("31000000-0000-0000-0000-000000000001"),
        voice_settings={"tone": "clear"},
        visual_settings={"colors": ["#111111"]},
        generation_defaults={"temperature": 0.7},
        metadata={"source": "test"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def text_content_record(content_id: UUID) -> ContentRecord:
    return ContentRecord(
        id=content_id,
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        created_by_user_id=UUID("00000000-0000-0000-0000-000000000001"),
        content_type="TEXT",
        title="Launch campaign",
        payload={
            "text": "Generated launch copy",
            "request": {
                "topic": "Launch campaign",
                "audience": "marketing managers",
                "tone": "professional",
                "content_type": "email",
                "brand_voice": "Clear and useful",
            },
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def settings_record(
    *,
    brand_name: str | None = "Lefil",
    segment: str | None = "marketing",
    tone: str = "professional",
    voice: str = "Clear and useful",
    visual_style: str = "photographic",
    default_preferences: dict[str, object] | None = None,
) -> SettingsRecord:
    return SettingsRecord(
        id=UUID("90000000-0000-0000-0000-000000000001"),
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        brand_name=brand_name,
        segment=segment,
        tone=tone,
        voice=voice,
        visual_style=visual_style,
        default_preferences=default_preferences or {},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def generate_content_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "workspace_id": "10000000-0000-0000-0000-000000000001",
        "topic": "Launch campaign",
        "audience": "marketing managers",
        "tone": "professional",
        "content_type": "email",
        "brand_voice": "Clear and useful",
    }
    payload.update(overrides)
    return payload


def job_record(
    *,
    job_id: UUID,
    content_id: object,
    generation_id: UUID,
    status: GenerationJobStatus,
    external_id: object | None = None,
    failure_code: str | None = None,
) -> GenerationJobRecord:
    return GenerationJobRecord(
        id=job_id,
        workspace_id=UUID("10000000-0000-0000-0000-000000000001"),
        generation_id=generation_id,
        content_id=content_id if isinstance(content_id, UUID) else UUID(str(content_id)),
        status=status,
        external_id=external_id if isinstance(external_id, str) else None,
        attempt_count=0,
        max_attempts=1,
        failure_code=failure_code,
        failure_message=None,
        queued_at=datetime.now(UTC),
        started_at=None,
        completed_at=None,
        failed_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def status_record(
    *,
    job_id: UUID,
    content_id: UUID,
    status: GenerationJobStatus = GenerationJobStatus.PENDING,
    image: ImageRecord | None = None,
    request_fingerprint: str | None = None,
    failure_code: str | None = None,
) -> ImageGenerationStatusRecord:
    return ImageGenerationStatusRecord(
        job=job_record(
            job_id=job_id,
            content_id=content_id,
            generation_id=UUID("60000000-0000-0000-0000-000000000001"),
            status=status,
            failure_code=failure_code,
        ),
        parameters={
            "style": "photographic",
            "idempotency": {
                "request_fingerprint": request_fingerprint
                or image_generation_request_fingerprint(content_id=content_id, style="photographic")
            },
        },
        image=image,
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
async def test_user_admin_crud_routes_return_envelopes() -> None:
    unit_of_work = FakeUnitOfWork()
    application = admin_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    user_id = "00000000-0000-0000-0000-000000000002"

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        list_response = await client.get("/api/v1/users")
        create_response = await client.post(
            "/api/v1/users",
            json={
                "external_id": "supabase:new",
                "email": "new@example.com",
                "display_name": "New User",
                "global_role": "gestor",
            },
        )
        get_response = await client.get(f"/api/v1/users/{user_id}")
        update_response = await client.put(
            f"/api/v1/users/{user_id}",
            json={"display_name": "Updated", "global_role": "admin"},
        )
        delete_response = await client.delete(f"/api/v1/users/{user_id}")

    assert list_response.status_code == 200
    assert create_response.status_code == 201
    assert get_response.status_code == 200
    assert update_response.json()["data"]["global_role"] == "admin"
    assert delete_response.json()["data"] == {"deleted": True}
    assert unit_of_work.commits == 3


@pytest.mark.anyio
async def test_get_settings_creates_default_for_authenticated_user() -> None:
    unit_of_work = FakeUnitOfWork()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/settings")

    assert response.status_code == 200
    assert response.json()["data"]["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert response.json()["data"]["tone"] == "professional"
    assert response.json()["data"]["voice"] == "Clear and useful"
    assert response.json()["data"]["visual_style"] == "photographic"
    assert unit_of_work.settings.created == [UUID("00000000-0000-0000-0000-000000000001")]
    assert unit_of_work.commits == 1


@pytest.mark.anyio
async def test_patch_settings_updates_only_sent_fields() -> None:
    unit_of_work = FakeUnitOfWork(
        settings_record=settings_record(
            brand_name="Lefil",
            segment="agency",
            default_preferences={"locale": "pt-BR"},
        )
    )
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.patch(
            "/api/v1/settings",
            json={"segment": "SaaS", "tone": "friendly"},
        )

    assert response.status_code == 200
    assert response.json()["data"]["brand_name"] == "Lefil"
    assert response.json()["data"]["segment"] == "SaaS"
    assert response.json()["data"]["tone"] == "friendly"
    assert response.json()["data"]["default_preferences"] == {"locale": "pt-BR"}
    assert unit_of_work.settings.updated == [
        {
            "user_id": UUID("00000000-0000-0000-0000-000000000001"),
            "changes": {"segment": "SaaS", "tone": "friendly"},
        }
    ]
    assert unit_of_work.commits == 1


@pytest.mark.anyio
async def test_patch_settings_returns_standard_validation_error() -> None:
    application = authorized_app()

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.patch("/api/v1/settings", json={"tone": "urgent"})

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.anyio
async def test_workspace_crud_routes_are_scoped_to_current_user() -> None:
    unit_of_work = FakeUnitOfWork()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    workspace_id = "10000000-0000-0000-0000-000000000001"

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        list_response = await client.get("/api/v1/workspaces")
        create_response = await client.post("/api/v1/workspaces", json={"name": "Growth"})
        get_response = await client.get(f"/api/v1/workspaces/{workspace_id}")
        update_response = await client.put(
            f"/api/v1/workspaces/{workspace_id}",
            json={"name": "Updated Growth"},
        )
        delete_response = await client.delete(f"/api/v1/workspaces/{workspace_id}")

    assert list_response.json()["data"]["pagination"]["total"] == 1
    assert create_response.status_code == 201
    assert get_response.json()["data"]["id"] == workspace_id
    assert update_response.json()["data"]["name"] == "Updated Growth"
    assert delete_response.json()["data"] == {"deleted": True}
    assert unit_of_work.commits == 3


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("base_path", "payload", "expected_field"),
    [
        (
            "/api/v1/brands",
            {
                "workspace_id": "10000000-0000-0000-0000-000000000001",
                "name": "Lefil",
                "description": "Brand",
                "brand_voice": "Clear",
                "metadata": {"segment": "creator"},
            },
            "name",
        ),
        (
            "/api/v1/projects",
            {
                "workspace_id": "10000000-0000-0000-0000-000000000001",
                "brand_id": "31000000-0000-0000-0000-000000000001",
                "name": "Launch",
                "description": "Project",
                "status": "ACTIVE",
                "metadata": {"channel": "email"},
            },
            "status",
        ),
        (
            "/api/v1/contents",
            {
                "workspace_id": "10000000-0000-0000-0000-000000000001",
                "brand_id": "31000000-0000-0000-0000-000000000001",
                "project_id": "32000000-0000-0000-0000-000000000001",
                "type": "TEXT",
                "title": "Launch copy",
                "payload": {"text": "hello"},
            },
            "title",
        ),
        (
            "/api/v1/generations",
            {
                "workspace_id": "10000000-0000-0000-0000-000000000001",
                "content_id": "21000000-0000-0000-0000-000000000001",
                "brand_id": "31000000-0000-0000-0000-000000000001",
                "project_id": "32000000-0000-0000-0000-000000000001",
                "type": "TEXT",
                "model": "gemini-2.5-flash",
                "prompt": "Write",
                "parameters": {"temperature": 0.7},
            },
            "model",
        ),
        (
            "/api/v1/assets",
            {
                "workspace_id": "10000000-0000-0000-0000-000000000001",
                "brand_id": "31000000-0000-0000-0000-000000000001",
                "project_id": "32000000-0000-0000-0000-000000000001",
                "content_id": "21000000-0000-0000-0000-000000000001",
                "asset_type": "image",
                "storage_path": "workspaces/ws/assets/a.png",
                "public_url": "https://example.com/a.png",
                "mime_type": "image/png",
                "byte_size": 123,
                "checksum": "sha256:abc",
                "metadata": {"alt": "asset"},
            },
            "asset_type",
        ),
    ],
)
async def test_core_resource_crud_routes_return_envelopes(
    base_path: str,
    payload: dict[str, object],
    expected_field: str,
) -> None:
    unit_of_work = FakeUnitOfWork(
        content=content_record(UUID("21000000-0000-0000-0000-000000000001"))
    )
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        list_response = await client.get(base_path)
        create_response = await client.post(base_path, json=payload)
        resource_id = create_response.json()["data"]["id"]
        get_response = await client.get(f"{base_path}/{resource_id}")
        update_response = await client.put(f"{base_path}/{resource_id}", json={})
        delete_response = await client.delete(f"{base_path}/{resource_id}")

    assert list_response.status_code == 200
    assert create_response.status_code == 201
    assert get_response.status_code == 200
    assert expected_field in update_response.json()["data"]
    assert delete_response.json()["data"] == {"deleted": True}
    assert unit_of_work.commits == 3


@pytest.mark.anyio
async def test_brand_settings_crud_routes_use_brand_subresource() -> None:
    unit_of_work = FakeUnitOfWork()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    brand_id = "31000000-0000-0000-0000-000000000001"
    payload = {
        "workspace_id": "10000000-0000-0000-0000-000000000001",
        "voice_settings": {"tone": "clear"},
        "visual_settings": {"colors": ["#111111"]},
        "generation_defaults": {"temperature": 0.7},
        "metadata": {"source": "test"},
    }

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        get_response = await client.get(f"/api/v1/brands/{brand_id}/settings")
        upsert_response = await client.put(f"/api/v1/brands/{brand_id}/settings", json=payload)
        update_response = await client.patch(
            f"/api/v1/brands/{brand_id}/settings",
            json={"voice_settings": {"tone": "warm"}},
        )
        delete_response = await client.delete(f"/api/v1/brands/{brand_id}/settings")

    assert get_response.json()["data"]["brand_id"] == brand_id
    assert upsert_response.status_code == 200
    assert update_response.json()["data"]["voice_settings"] == {"tone": "clear"}
    assert delete_response.json()["data"] == {"deleted": True}
    assert unit_of_work.commits == 3


@pytest.mark.anyio
async def test_core_resource_create_rejects_non_writable_workspace() -> None:
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: FakeUnitOfWork(workspace_access=False)

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/brands",
            json={
                "workspace_id": "10000000-0000-0000-0000-000000000001",
                "name": "Blocked",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.anyio
async def test_generate_content_persists_text_content() -> None:
    unit_of_work = FakeUnitOfWork(
        settings_record=settings_record(default_preferences={"locale": "pt-BR", "brand": "Lefil"})
    )
    llm_provider = FakeLLMProvider(output="Generated launch copy")
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_llm_provider] = lambda: llm_provider

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/content/generate",
            json=generate_content_payload(),
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["id"] == "21000000-0000-0000-0000-000000000001"
    assert response.json()["data"]["type"] == "TEXT"
    assert response.json()["data"]["payload"]["text"] == "Generated launch copy"
    assert response.json()["data"]["generation"]["id"] == "61000000-0000-0000-0000-000000000001"
    assert response.json()["data"]["generation"]["model"] == "gemini-2.5-flash"
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]
    assert "CREATOR_PROMPT" in llm_provider.prompts[0]
    assert '"settings"' in llm_provider.prompts[0]
    created = unit_of_work.contents.created_text_generations[0]
    assert created["workspace_id"] == UUID("10000000-0000-0000-0000-000000000001")
    assert created["model"] == "gemini-2.5-flash"
    assert created["parameters"]["prompt_template"]["id"] == "content.generation.v1"
    assert unit_of_work.commits == 1


@pytest.mark.anyio
async def test_generate_content_uses_settings_defaults_when_request_omits_fields() -> None:
    unit_of_work = FakeUnitOfWork(
        settings_record=settings_record(tone="friendly", voice="Warm and practical")
    )
    llm_provider = FakeLLMProvider(output="Generated launch copy")
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_llm_provider] = lambda: llm_provider
    payload = generate_content_payload()
    del payload["tone"]
    del payload["brand_voice"]

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/content/generate", json=payload)

    assert response.status_code == 200
    created = unit_of_work.contents.created_text_generations[0]
    assert created["payload"]["request"]["tone"] == "friendly"
    assert created["payload"]["request"]["brand_voice"] == "Warm and practical"


@pytest.mark.anyio
async def test_generate_content_returns_validation_error_envelope() -> None:
    application = authorized_app()

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/content/generate",
            json=generate_content_payload(tone="urgent", topic=""),
        )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_generate_content_rejects_workspace_without_membership() -> None:
    unit_of_work = FakeUnitOfWork(workspace_access=False)
    llm_provider = FakeLLMProvider()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_llm_provider] = lambda: llm_provider

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/content/generate",
            json=generate_content_payload(),
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "WORKSPACE_ACCESS_DENIED"
    assert llm_provider.prompts == []
    assert unit_of_work.contents.created_text_generations == []


@pytest.mark.anyio
async def test_generate_content_maps_provider_timeout_without_persisting() -> None:
    unit_of_work = FakeUnitOfWork()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(
        error=GeminiTimeoutError("slow")
    )

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/content/generate",
            json=generate_content_payload(),
        )

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "LLM_PROVIDER_TIMEOUT"
    assert unit_of_work.contents.created_text_generations == []
    assert unit_of_work.commits == 0


@pytest.mark.anyio
async def test_generate_content_rolls_back_when_persistence_fails() -> None:
    unit_of_work = FakeUnitOfWork(content_create_error=PersistenceError("db failed"))
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider()

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/content/generate",
            json=generate_content_payload(),
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "CONTENT_GENERATION_PERSISTENCE_FAILED"
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


@pytest.mark.anyio
async def test_list_content_returns_history_for_current_user() -> None:
    content = text_content_record(UUID("21000000-0000-0000-0000-000000000001"))
    unit_of_work = FakeUnitOfWork(
        content_page=Page(items=[content], total=1, page=1, limit=20),
    )
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/content")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["items"][0]["id"] == "21000000-0000-0000-0000-000000000001"
    assert response.json()["data"]["items"][0]["type"] == "TEXT"
    assert response.json()["data"]["pagination"] == {"page": 1, "limit": 20, "total": 1}


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
async def test_signup_rejection_includes_normalized_provider_message() -> None:
    application = create_app()
    application.dependency_overrides[get_auth_client] = lambda: FakeAuthClient(
        AuthSignupRejectedError(
            "rejected",
            provider_code="user_already_exists",
            provider_message="User already registered",
        )
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
    assert response.json()["error"] == {
        "code": "SIGNUP_REJECTED",
        "message": "User already registered",
    }


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
async def test_api_v1_route_rejects_bearer_token_without_optional_auth_config() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=unauthenticated_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Authorization": f"Bearer {supabase_access_token()}"},
        )

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "AUTHENTICATION_INVALID"


@pytest.mark.anyio
async def test_api_v1_route_accepts_valid_supabase_token_when_enabled() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=authorized_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/content/generate",
            headers={"Authorization": f"Bearer {supabase_access_token()}"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.anyio
async def test_generate_image_returns_accepted_job_and_enqueues_work() -> None:
    content_id = UUID("20000000-0000-0000-0000-000000000001")
    unit_of_work = FakeUnitOfWork(content=content_record(content_id))
    queue = FakeGenerationQueue()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_generation_queue] = lambda: queue

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Idempotency-Key": "idem-1"},
            json={"content_id": str(content_id), "style": "photographic"},
        )

    assert response.status_code == 202
    assert response.json()["success"] is True
    assert response.json()["data"]["id"] == "50000000-0000-0000-0000-000000000001"
    assert response.json()["data"]["status"] == "PENDING"
    assert response.json()["data"]["image"] is None
    assert queue.calls == [
        {
            "f": "creator.workers.image_generation.run_image_generation",
            "args": ("50000000-0000-0000-0000-000000000001",),
            "job_id": "image-generation:50000000-0000-0000-0000-000000000001",
        }
    ]
    created = unit_of_work.image_generations.created[0]
    assert created["model"] == "gemini-2.5-flash-image"
    assert "CREATOR_PROMPT" in str(created["prompt"])
    assert created["parameters"]["style"] == "photographic"
    assert created["parameters"]["prompt_template"]["id"] == "image.advertising.v1"
    assert "request_fingerprint" in created["parameters"]["idempotency"]
    assert unit_of_work.commits == 1


@pytest.mark.anyio
async def test_generate_image_uses_settings_default_style_when_request_omits_style() -> None:
    content_id = UUID("20000000-0000-0000-0000-000000000001")
    unit_of_work = FakeUnitOfWork(
        content=content_record(content_id),
        settings_record=settings_record(visual_style="illustration"),
    )
    queue = FakeGenerationQueue()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_generation_queue] = lambda: queue

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Idempotency-Key": "idem-1"},
            json={"content_id": str(content_id)},
        )

    assert response.status_code == 202
    created = unit_of_work.image_generations.created[0]
    assert created["parameters"]["style"] == "illustration"
    assert created["parameters"]["idempotency"]["request_fingerprint"] == (
        image_generation_request_fingerprint(content_id=content_id, style="illustration")
    )
    assert "illustration" in str(created["prompt"])


@pytest.mark.anyio
async def test_generate_image_returns_existing_job_for_same_idempotency_key() -> None:
    content_id = UUID("20000000-0000-0000-0000-000000000001")
    existing = status_record(
        job_id=UUID("50000000-0000-0000-0000-000000000001"),
        content_id=content_id,
    )
    unit_of_work = FakeUnitOfWork(existing=existing)
    queue = FakeGenerationQueue()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_generation_queue] = lambda: queue

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Idempotency-Key": "idem-1"},
            json={"content_id": str(content_id), "style": "photographic"},
        )

    assert response.status_code == 202
    assert response.json()["data"]["id"] == "50000000-0000-0000-0000-000000000001"
    assert queue.calls == []
    assert unit_of_work.contents.requests == []
    assert unit_of_work.image_generations.created == []


@pytest.mark.anyio
async def test_generate_image_rejects_reused_idempotency_key_with_different_payload() -> None:
    content_id = UUID("20000000-0000-0000-0000-000000000001")
    existing = status_record(
        job_id=UUID("50000000-0000-0000-0000-000000000001"),
        content_id=content_id,
        request_fingerprint="different",
    )
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: FakeUnitOfWork(existing=existing)
    application.dependency_overrides[get_generation_queue] = lambda: FakeGenerationQueue()

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Idempotency-Key": "idem-1"},
            json={"content_id": str(content_id), "style": "photographic"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.anyio
async def test_generate_image_returns_not_found_for_missing_content() -> None:
    content_id = UUID("20000000-0000-0000-0000-000000000001")
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: FakeUnitOfWork(content=None)
    application.dependency_overrides[get_generation_queue] = lambda: FakeGenerationQueue()

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Idempotency-Key": "idem-1"},
            json={"content_id": str(content_id), "style": "photographic"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONTENT_NOT_FOUND"


@pytest.mark.anyio
async def test_generate_image_returns_validation_error_envelope() -> None:
    application = authorized_app()

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Idempotency-Key": "idem-1"},
            json={"content_id": "not-a-uuid", "style": "photographic"},
        )

    assert response.status_code == 422
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert response.headers["X-Request-ID"] == response.json()["meta"]["request_id"]


@pytest.mark.anyio
async def test_generate_image_rolls_back_when_queue_enqueue_fails() -> None:
    content_id = UUID("20000000-0000-0000-0000-000000000001")
    unit_of_work = FakeUnitOfWork(content=content_record(content_id))
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_generation_queue] = lambda: FakeGenerationQueue(
        error=RuntimeError("redis down")
    )

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/images/generate",
            headers={"Idempotency-Key": "idem-1"},
            json={"content_id": str(content_id), "style": "photographic"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "QUEUE_ENQUEUE_FAILED"
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


@pytest.mark.anyio
async def test_get_image_returns_pending_status_without_calling_storage() -> None:
    job_id = UUID("50000000-0000-0000-0000-000000000001")
    content_id = UUID("20000000-0000-0000-0000-000000000001")
    unit_of_work = FakeUnitOfWork(status=status_record(job_id=job_id, content_id=content_id))
    storage = FakeStorageProvider()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_storage_provider] = lambda: storage

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/images/{job_id}")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "PENDING"
    assert response.json()["data"]["image"] is None
    assert storage.paths == []


@pytest.mark.anyio
async def test_get_image_returns_completed_job_with_fresh_storage_url() -> None:
    job_id = UUID("50000000-0000-0000-0000-000000000001")
    image_id = UUID("40000000-0000-0000-0000-000000000001")
    image = stored_image(image_id)
    unit_of_work = FakeUnitOfWork(
        status=status_record(
            job_id=job_id,
            content_id=image.content_id,
            status=GenerationJobStatus.COMPLETED,
            image=image,
        )
    )
    storage = FakeStorageProvider()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_storage_provider] = lambda: storage

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/images/{job_id}")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["status"] == "COMPLETED"
    assert response.json()["data"]["image"]["public_url"] == (
        "https://signed.example/users/principal-123/contents/content/versions/1/image.png"
    )
    assert response.json()["data"]["image"]["metadata"] == {"storage_provider": "local"}
    assert storage.paths == [image.storage_path]
    assert unit_of_work.image_generations.status_requests == [
        {
            "user_id": UUID("00000000-0000-0000-0000-000000000001"),
            "job_id": job_id,
        }
    ]


@pytest.mark.anyio
async def test_get_image_returns_not_found_without_calling_storage_when_not_visible() -> None:
    job_id = UUID("50000000-0000-0000-0000-000000000001")
    unit_of_work = FakeUnitOfWork(status=None)
    storage = FakeStorageProvider()
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: unit_of_work
    application.dependency_overrides[get_storage_provider] = lambda: storage

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/images/{job_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "IMAGE_GENERATION_NOT_FOUND"
    assert storage.paths == []


@pytest.mark.anyio
async def test_get_image_returns_storage_error_when_signed_url_is_unavailable() -> None:
    job_id = UUID("50000000-0000-0000-0000-000000000001")
    image_id = UUID("40000000-0000-0000-0000-000000000001")
    image = stored_image(image_id)
    application = authorized_app()
    application.dependency_overrides[get_uow] = lambda: FakeUnitOfWork(
        status=status_record(
            job_id=job_id,
            content_id=image.content_id,
            status=GenerationJobStatus.COMPLETED,
            image=image,
        )
    )
    application.dependency_overrides[get_storage_provider] = lambda: FakeStorageProvider(
        url_error=True
    )

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/images/{job_id}")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "STORAGE_URL_UNAVAILABLE"


@pytest.mark.anyio
async def test_swagger_and_openapi_are_available() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        docs_response = await client.get("/docs")
        openapi_response = await client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
    openapi_schema = openapi_response.json()
    assert "/health" in openapi_schema["paths"]
    assert "/api/v1/auth/login" in openapi_schema["paths"]
    assert "/api/v1/auth/signup" in openapi_schema["paths"]


@pytest.mark.anyio
async def test_swagger_uses_bearer_security_for_protected_routes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/openapi.json")

    openapi_schema = response.json()
    assert openapi_schema["components"]["securitySchemes"]["SupabaseBearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
    }
    generate_operation = openapi_schema["paths"]["/api/v1/content/generate"]["post"]
    assert generate_operation["security"] == [{"SupabaseBearerAuth": []}]
    assert all(
        parameter["name"] != "authorization"
        for parameter in generate_operation.get("parameters", [])
    )


def test_application_factory_and_compatibility_entrypoint() -> None:
    assert create_app().title == "Creator API"
    assert app.title == "Creator API"
