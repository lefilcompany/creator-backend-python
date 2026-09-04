from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from creator.domain.exceptions import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from creator.domain.generation import GenerationJobStatus
from creator.infrastructure import models
from creator.infrastructure.dtos import (
    SqlAlchemyAssetRepository,
    SqlAlchemyBrandRepository,
    SqlAlchemyBrandSettingsRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGenerationRepository,
    SqlAlchemyImageGenerationRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySettingsRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
    flush_or_raise,
)
from creator.repositories import (
    ContentFilters,
    GenerationHistoryFilters,
    ImageMetadata,
    PageRequest,
)

NOW = datetime(2026, 8, 28, tzinfo=UTC)


class ScalarResult:
    def __init__(self, value: object = None, values: list[object] | None = None) -> None:
        self.value = value
        self.values = values or ([] if value is None else [value])

    def one_or_none(self) -> object | None:
        return self.value

    def first(self) -> object | None:
        return self.value

    def all(self) -> list[object]:
        return self.values


class ExecuteResult:
    def __init__(self, value: object = None, rows: list[object] | None = None) -> None:
        self.value = value
        self.rows = rows or ([] if value is None else [value])

    def scalar_one(self) -> object:
        return self.value

    def scalar_one_or_none(self) -> object | None:
        return self.value

    def one_or_none(self) -> object | None:
        return self.value

    def all(self) -> list[object]:
        return self.rows


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.scalars_results: list[ScalarResult] = []
        self.execute_results: list[ExecuteResult] = []
        self.get_results: list[object | None] = []
        self.flush_error: IntegrityError | None = None

    def add(self, row: object) -> None:
        self.added.append(row)

    def flush(self) -> None:
        if self.flush_error is not None:
            raise self.flush_error
        for row in self.added:
            self._assign_defaults(row)

    def get(self, model: type[object], identity: UUID) -> object | None:
        return self.get_results.pop(0)

    def scalars(self, statement: object) -> ScalarResult:
        return self.scalars_results.pop(0)

    def execute(self, statement: object) -> ExecuteResult:
        return self.execute_results.pop(0)

    def _assign_defaults(self, row: object) -> None:
        if getattr(row, "id", None) is None:
            row.id = uuid4()
        for field_name in ["created_at", "updated_at", "queued_at", "occurred_at"]:
            if hasattr(row, field_name) and getattr(row, field_name, None) is None:
                setattr(row, field_name, NOW)
        if isinstance(row, models.GenerationJob):
            if row.status is None:
                row.status = GenerationJobStatus.PENDING
            if row.attempt_count is None:
                row.attempt_count = 0
            if row.max_attempts is None:
                row.max_attempts = 1
        if isinstance(row, models.Content) and row.content_type is None:
            row.content_type = models.ContentType.IMAGE
        if isinstance(row, models.Generation) and row.generation_type is None:
            row.generation_type = models.GenerationType.IMAGE
        if isinstance(row, models.User) and row.global_role is None:
            row.global_role = models.GlobalRole.MEMBRO
        if isinstance(row, models.Project) and row.status is None:
            row.status = "ACTIVE"
        for field_name in [
            "metadata_json",
            "voice_settings",
            "visual_settings",
            "generation_defaults",
            "default_preferences",
            "payload",
            "parameters",
        ]:
            if hasattr(row, field_name) and getattr(row, field_name, None) is None:
                setattr(row, field_name, {})


def fake_session(session: FakeSession) -> Session:
    return cast(Session, session)


def user_row() -> models.User:
    return models.User(
        id=uuid4(),
        external_id=f"supabase:{uuid4()}",
        email="user@example.com",
        display_name="User",
        global_role=models.GlobalRole.MEMBRO,
        created_at=NOW,
        updated_at=NOW,
    )


def workspace_row() -> models.Workspace:
    return models.Workspace(id=uuid4(), name="Workspace", created_at=NOW, updated_at=NOW)


def membership_row(user: models.User, workspace: models.Workspace) -> models.WorkspaceMembership:
    return models.WorkspaceMembership(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=models.WorkspaceRole.OWNER,
        created_at=NOW,
        updated_at=NOW,
    )


def brand_row(
    *,
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
) -> models.Brand:
    return models.Brand(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),
        created_by_user_id=user_id or uuid4(),
        name="Brand",
        description="Description",
        brand_voice="Voice",
        metadata_json={"segment": "creator"},
        created_at=NOW,
        updated_at=NOW,
    )


def project_row(brand: models.Brand) -> models.Project:
    return models.Project(
        id=uuid4(),
        workspace_id=brand.workspace_id,
        brand_id=brand.id,
        created_by_user_id=brand.created_by_user_id,
        name="Project",
        description="Description",
        status="ACTIVE",
        metadata_json={"channel": "email"},
        created_at=NOW,
        updated_at=NOW,
    )


def content_row(
    *,
    content_id: UUID | None = None,
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    brand_id: UUID | None = None,
    project_id: UUID | None = None,
) -> models.Content:
    return models.Content(
        id=content_id or uuid4(),
        workspace_id=workspace_id or uuid4(),
        created_by_user_id=user_id or uuid4(),
        brand_id=brand_id,
        project_id=project_id,
        content_type=models.ContentType.IMAGE,
        title="Content",
        payload={"kind": "image"},
        created_at=NOW,
        updated_at=NOW,
    )


def generation_row(content: models.Content) -> models.Generation:
    return models.Generation(
        id=uuid4(),
        workspace_id=content.workspace_id,
        content_id=content.id,
        brand_id=content.brand_id,
        project_id=content.project_id,
        requested_by_user_id=content.created_by_user_id,
        generation_type=models.GenerationType.IMAGE,
        model="gemini-image",
        prompt="Generate",
        parameters={},
        created_at=NOW,
        updated_at=NOW,
    )


def asset_row(content: models.Content) -> models.Asset:
    return models.Asset(
        id=uuid4(),
        workspace_id=content.workspace_id,
        brand_id=content.brand_id,
        project_id=content.project_id,
        content_id=content.id,
        uploaded_by_user_id=content.created_by_user_id,
        asset_type="image",
        storage_path=f"{content.workspace_id}/{uuid4()}.png",
        public_url="https://example.com/asset.png",
        mime_type="image/png",
        byte_size=123,
        checksum="sha256:abc",
        metadata_json={"source": "test"},
        created_at=NOW,
        updated_at=NOW,
    )


def brand_settings_row(brand: models.Brand) -> models.BrandSettings:
    return models.BrandSettings(
        id=uuid4(),
        workspace_id=brand.workspace_id,
        brand_id=brand.id,
        voice_settings={"tone": "clear"},
        visual_settings={"colors": ["#111111"]},
        generation_defaults={"temperature": 0.7},
        metadata_json={"source": "test"},
        created_at=NOW,
        updated_at=NOW,
    )


def job_row(generation: models.Generation, status: GenerationJobStatus) -> models.GenerationJob:
    return models.GenerationJob(
        id=uuid4(),
        workspace_id=generation.workspace_id,
        generation_id=generation.id,
        status=status,
        external_id=None,
        attempt_count=0,
        max_attempts=1,
        queued_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def image_row(generation: models.Generation) -> models.Image:
    return models.Image(
        id=uuid4(),
        workspace_id=generation.workspace_id,
        content_id=generation.content_id,
        generation_id=generation.id,
        version_number=1,
        storage_path="users/principal/contents/content/versions/1/image.png",
        public_url="https://example.com/image.png",
        mime_type="image/png",
        width=100,
        height=100,
        model="gemini-image",
        prompt="Generate",
        metadata_json={"source": "test"},
        created_at=NOW,
        updated_at=NOW,
    )


def test_user_repository_crud_and_soft_delete_paths() -> None:
    session = FakeSession()
    repository = SqlAlchemyUserRepository(fake_session(session))

    created = repository.add(external_id="supabase:new", email="new@example.com")
    assert created.external_id == "supabase:new"

    stored = user_row()
    session.scalars_results.append(ScalarResult(stored))
    assert repository.get_by_external_id(stored.external_id) is not None

    session.get_results.append(stored)
    updated = repository.update_profile(stored.id, display_name="Updated")
    assert updated.display_name == "Updated"

    session.get_results.append(stored)
    repository.soft_delete(stored.id)
    assert stored.deleted_at is not None


def test_user_repository_raises_when_updating_missing_user() -> None:
    session = FakeSession()
    session.get_results.append(None)

    with pytest.raises(EntityNotFoundError):
        SqlAlchemyUserRepository(fake_session(session)).update_profile(
            uuid4(), email="x@example.com"
        )


def test_settings_repository_get_create_upsert_and_update() -> None:
    session = FakeSession()
    repository = SqlAlchemySettingsRepository(fake_session(session))
    user_id = uuid4()

    session.scalars_results.append(ScalarResult(None))
    assert repository.get_by_user_id(user_id) is None

    created = repository.create_for_user(
        user_id,
        brand_name="Lefil",
        segment="marketing",
        default_preferences={"locale": "pt-BR"},
    )
    assert created.brand_name == "Lefil"
    assert created.default_preferences == {"locale": "pt-BR"}

    existing = models.Settings(
        id=uuid4(),
        user_id=user_id,
        brand_name="Lefil",
        segment="marketing",
        tone="professional",
        voice="Clear and useful",
        visual_style="photographic",
        default_preferences={"locale": "pt-BR"},
        created_at=NOW,
        updated_at=NOW,
    )
    session.scalars_results.append(ScalarResult(existing))
    stored = repository.get_or_create_for_user(user_id)
    assert stored.brand_name == "Lefil"

    session.scalars_results.append(ScalarResult(existing))
    updated = repository.update_partial(user_id, {"segment": "SaaS"})
    assert updated.brand_name == "Lefil"
    assert updated.segment == "SaaS"


def test_settings_repository_raises_for_missing_update() -> None:
    session = FakeSession()
    session.scalars_results.append(ScalarResult(None))

    with pytest.raises(EntityNotFoundError):
        SqlAlchemySettingsRepository(fake_session(session)).update_partial(uuid4(), {})


def test_workspace_repository_crud_and_role_checks() -> None:
    session = FakeSession()
    repository = SqlAlchemyWorkspaceRepository(fake_session(session))
    user = user_row()
    workspace = workspace_row()
    membership = membership_row(user, workspace)

    created = repository.add(name="Created Workspace", owner_user_id=user.id)
    assert created.name == "Created Workspace"

    session.scalars_results.append(ScalarResult(workspace))
    assert repository.get_for_user(user_id=user.id, workspace_id=workspace.id) is not None

    session.scalars_results.append(ScalarResult(values=[workspace]))
    session.execute_results.append(ExecuteResult(1))
    page = repository.list_for_user(user_id=user.id, page=PageRequest(page=1, limit=10))
    assert page.total == 1

    session.scalars_results.append(ScalarResult(membership))
    session.get_results.append(workspace)
    assert repository.update(user_id=user.id, workspace_id=workspace.id, name="Updated").name == (
        "Updated"
    )

    session.scalars_results.append(ScalarResult(membership))
    assert repository.user_has_workspace_role(
        user_id=user.id,
        workspace_id=workspace.id,
        minimum_role="editor",
    )


def test_brand_project_asset_generation_and_settings_repositories_crud_paths() -> None:
    session = FakeSession()
    user = user_row()
    workspace = workspace_row()
    membership = membership_row(user, workspace)
    brand = brand_row(workspace_id=workspace.id, user_id=user.id)
    project = project_row(brand)
    content = content_row(
        workspace_id=workspace.id,
        user_id=user.id,
        brand_id=brand.id,
        project_id=project.id,
    )
    generation = generation_row(content)
    asset = asset_row(content)
    settings = brand_settings_row(brand)

    brand_repository = SqlAlchemyBrandRepository(fake_session(session))
    session.scalars_results.append(ScalarResult(membership))
    created_brand = brand_repository.add(
        workspace_id=workspace.id,
        created_by_user_id=user.id,
        name="Created Brand",
        metadata={"source": "test"},
    )
    assert created_brand.name == "Created Brand"

    session.scalars_results.append(ScalarResult(values=[brand]))
    session.execute_results.append(ExecuteResult(1))
    assert brand_repository.list_for_user(user_id=user.id).total == 1

    session.scalars_results.extend([ScalarResult(brand), ScalarResult(membership)])
    assert brand_repository.update(user_id=user.id, brand_id=brand.id, name="Updated").name == (
        "Updated"
    )

    project_repository = SqlAlchemyProjectRepository(fake_session(session))
    session.scalars_results.append(ScalarResult(membership))
    assert (
        project_repository.add(
            workspace_id=workspace.id,
            brand_id=brand.id,
            created_by_user_id=user.id,
            name="Created Project",
        ).workspace_id
        == workspace.id
    )

    session.scalars_results.append(ScalarResult(values=[project]))
    session.execute_results.append(ExecuteResult(1))
    assert project_repository.list_for_user(user_id=user.id, brand_id=brand.id).total == 1

    session.scalars_results.extend([ScalarResult(project), ScalarResult(membership)])
    assert (
        project_repository.update(
            user_id=user.id,
            project_id=project.id,
            status="ARCHIVED",
        ).status
        == "ARCHIVED"
    )

    generation_repository = SqlAlchemyGenerationRepository(fake_session(session))
    session.scalars_results.append(ScalarResult(membership))
    assert (
        generation_repository.add(
            workspace_id=workspace.id,
            content_id=content.id,
            requested_by_user_id=user.id,
            model="gemini",
            prompt="Generate",
            brand_id=brand.id,
            project_id=project.id,
        ).content_id
        == content.id
    )

    session.scalars_results.extend([ScalarResult(generation), ScalarResult(membership)])
    assert generation_repository.update(
        user_id=user.id,
        generation_id=generation.id,
        parameters={"temperature": 1},
    ).parameters == {"temperature": 1}

    asset_repository = SqlAlchemyAssetRepository(fake_session(session))
    session.scalars_results.append(ScalarResult(membership))
    assert (
        asset_repository.add(
            workspace_id=workspace.id,
            uploaded_by_user_id=user.id,
            asset_type="image",
            storage_path="workspace/asset.png",
            mime_type="image/png",
            byte_size=123,
            brand_id=brand.id,
            project_id=project.id,
            content_id=content.id,
        ).asset_type
        == "image"
    )

    session.scalars_results.append(ScalarResult(values=[asset]))
    session.execute_results.append(ExecuteResult(1))
    assert asset_repository.list_for_user(user_id=user.id, content_id=content.id).total == 1

    session.scalars_results.extend([ScalarResult(asset), ScalarResult(membership)])
    assert asset_repository.update(
        user_id=user.id,
        asset_id=asset.id,
        metadata={"alt": "updated"},
    ).metadata == {"alt": "updated"}

    settings_repository = SqlAlchemyBrandSettingsRepository(fake_session(session))
    session.scalars_results.append(ScalarResult(settings))
    assert settings_repository.get_for_user(user_id=user.id, brand_id=brand.id) is not None

    session.scalars_results.extend([ScalarResult(membership), ScalarResult(None)])
    assert settings_repository.upsert(
        user_id=user.id,
        workspace_id=workspace.id,
        brand_id=brand.id,
        voice_settings={"tone": "new"},
    ).voice_settings == {"tone": "new"}

    session.scalars_results.extend([ScalarResult(settings), ScalarResult(membership)])
    assert settings_repository.update(
        user_id=user.id,
        brand_id=brand.id,
        visual_settings={"logo": "mark"},
    ).visual_settings == {"logo": "mark"}


def test_content_repository_crud_pagination_and_soft_delete() -> None:
    session = FakeSession()
    repository = SqlAlchemyContentRepository(fake_session(session))
    content = content_row()

    created = repository.add(
        workspace_id=content.workspace_id,
        created_by_user_id=content.created_by_user_id,
        title="Created",
    )
    assert created.title == "Created"

    session.scalars_results.append(ScalarResult(content))
    assert repository.get_by_id_for_user(user_id=content.created_by_user_id, content_id=content.id)

    session.scalars_results.append(ScalarResult(values=[content]))
    session.execute_results.append(ExecuteResult(1))
    page = repository.list_for_user(
        user_id=content.created_by_user_id,
        filters=ContentFilters(workspace_id=content.workspace_id),
        page=PageRequest(page=1, limit=10, sort="asc"),
    )
    assert page.total == 1

    session.get_results.append(content)
    assert repository.update(content.id, title="Updated").title == "Updated"

    session.get_results.append(content)
    repository.soft_delete(content.id)
    assert content.deleted_at is not None


def test_content_repository_creates_text_content_with_generation() -> None:
    session = FakeSession()
    repository = SqlAlchemyContentRepository(fake_session(session))
    workspace_id = uuid4()
    user_id = uuid4()
    session.execute_results.append(ExecuteResult(1))

    generated = repository.create_text_generation(
        workspace_id=workspace_id,
        requested_by_user_id=user_id,
        title="Launch campaign",
        payload={"text": "Generated launch copy"},
        model="gemini-2.5-flash",
        prompt="CREATOR_PROMPT",
        parameters={"prompt_template": {"id": "content.generation.v1"}},
    )

    assert generated.content.content_type == "TEXT"
    assert generated.content.workspace_id == workspace_id
    assert generated.content.payload == {"text": "Generated launch copy"}
    assert generated.generation_model == "gemini-2.5-flash"
    assert generated.generation_parameters == {"prompt_template": {"id": "content.generation.v1"}}
    assert any(
        isinstance(row, models.Generation) and row.generation_type == models.GenerationType.TEXT
        for row in session.added
    )


def test_content_repository_rejects_text_generation_without_workspace_access() -> None:
    session = FakeSession()
    repository = SqlAlchemyContentRepository(fake_session(session))
    session.execute_results.append(ExecuteResult(0))

    with pytest.raises(EntityNotFoundError):
        repository.create_text_generation(
            workspace_id=uuid4(),
            requested_by_user_id=uuid4(),
            title="Launch campaign",
            payload={"text": "Generated launch copy"},
            model="gemini-2.5-flash",
            prompt="CREATOR_PROMPT",
        )

    assert session.added == []


def test_image_generation_repository_lifecycle_paths() -> None:
    session = FakeSession()
    repository = SqlAlchemyImageGenerationRepository(fake_session(session))
    content = content_row()
    generation = generation_row(content)
    pending_job = job_row(generation, GenerationJobStatus.PENDING)
    processing_job = job_row(generation, GenerationJobStatus.PROCESSING)

    session.scalars_results.append(ScalarResult(content))
    created = repository.create_image_generation(
        workspace_id=content.workspace_id,
        content_id=content.id,
        requested_by_user_id=content.created_by_user_id,
        model="gemini-image",
        prompt="Generate",
    )
    assert created.status == GenerationJobStatus.PENDING

    session.scalars_results.append(ScalarResult(pending_job))
    session.execute_results.append(ExecuteResult(content.id))
    claimed = repository.claim_next_pending(workspace_id=content.workspace_id)
    assert claimed is not None
    assert claimed.status == GenerationJobStatus.PROCESSING

    session.scalars_results.extend(
        [ScalarResult(processing_job), ScalarResult(generation), ScalarResult(content)]
    )
    session.execute_results.append(ExecuteResult(1))
    image = repository.complete_job(
        processing_job.id,
        ImageMetadata(
            storage_path="workspace/image.png",
            public_url="https://example.com/image.png",
            mime_type="image/png",
            width=100,
            height=100,
            model="gemini-image",
            prompt="Generate",
        ),
    )
    assert image.version_number == 1

    failing_job = job_row(generation, GenerationJobStatus.PROCESSING)
    session.scalars_results.append(ScalarResult(failing_job))
    session.execute_results.append(ExecuteResult(content.id))
    failed = repository.fail_job(
        failing_job.id,
        failure_code="PROVIDER_ERROR",
        failure_message="Provider failed",
    )
    assert failed.status == GenerationJobStatus.FAILED


def test_image_generation_repository_scoped_history_queries() -> None:
    session = FakeSession()
    repository = SqlAlchemyImageGenerationRepository(fake_session(session))
    content = content_row()
    generation = generation_row(content)
    completed_job = job_row(generation, GenerationJobStatus.COMPLETED)
    row = (completed_job, content.id)

    session.execute_results.extend([ExecuteResult(rows=[row]), ExecuteResult(1)])
    history = repository.list_history_for_user(
        user_id=content.created_by_user_id,
        filters=GenerationHistoryFilters(
            workspace_id=content.workspace_id,
            content_id=content.id,
            status=GenerationJobStatus.COMPLETED,
        ),
    )

    session.execute_results.append(ExecuteResult(row))
    stored = repository.get_job_for_user(
        user_id=content.created_by_user_id,
        job_id=completed_job.id,
    )

    assert history.total == 1
    assert stored is not None


def test_image_generation_repository_get_image_for_user_scopes_by_membership() -> None:
    session = FakeSession()
    repository = SqlAlchemyImageGenerationRepository(fake_session(session))
    content = content_row()
    generation = generation_row(content)
    image = image_row(generation)

    session.scalars_results.append(ScalarResult(image))
    stored = repository.get_image_for_user(
        user_id=content.created_by_user_id,
        image_id=image.id,
    )

    assert stored is not None
    assert stored.id == image.id
    assert stored.metadata == {"source": "test"}


def test_invalid_generation_job_transition_is_rejected() -> None:
    session = FakeSession()
    repository = SqlAlchemyImageGenerationRepository(fake_session(session))
    content = content_row()
    generation = generation_row(content)
    completed_job = job_row(generation, GenerationJobStatus.COMPLETED)
    session.scalars_results.append(ScalarResult(completed_job))

    with pytest.raises(InvalidStateTransitionError):
        repository.fail_job(completed_job.id, failure_code="FAILED", failure_message="nope")


def test_integrity_errors_are_mapped_at_flush_boundary() -> None:
    session = FakeSession()
    session.flush_error = IntegrityError("insert", {}, Exception("duplicate key unique"))

    with pytest.raises(ConflictError):
        flush_or_raise(fake_session(session))
