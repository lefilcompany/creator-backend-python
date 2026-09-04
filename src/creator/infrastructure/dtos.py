from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, and_, asc, desc, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from creator.domain.exceptions import (
    ConcurrencyError,
    ConflictError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    PersistenceError,
)
from creator.domain.generation import GenerationJobStatus, can_transition
from creator.infrastructure import models
from creator.repositories import (
    AssetRecord,
    BrandRecord,
    BrandSettingsRecord,
    ContentFilters,
    ContentRecord,
    GeneratedTextContentRecord,
    GenerationHistoryFilters,
    GenerationJobRecord,
    GenerationRecord,
    ImageGenerationStatusRecord,
    ImageGenerationWorkItem,
    ImageMetadata,
    ImageRecord,
    JsonObject,
    Page,
    PageRequest,
    ProjectRecord,
    SettingsRecord,
    UserRecord,
    WorkspaceRecord,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _enum_value(value: object) -> str:
    return cast(str, getattr(value, "value", value))


def _datetime(value: object) -> datetime:
    return cast(datetime, value)


def _optional_datetime(value: object | None) -> datetime | None:
    return cast(datetime | None, value)


def _json(value: dict[str, object] | None) -> JsonObject:
    return dict(value or {})


def map_sqlalchemy_error(error: SQLAlchemyError) -> PersistenceError:
    if isinstance(error, IntegrityError):
        message = str(error.orig).lower()
        if "unique" in message or "duplicate" in message:
            return ConflictError(str(error.orig))
        return ConcurrencyError(str(error.orig))
    return PersistenceError(str(error))


def flush_or_raise(session: Session) -> None:
    try:
        session.flush()
    except SQLAlchemyError as error:
        raise map_sqlalchemy_error(error) from error


def _user_record(row: models.User) -> UserRecord:
    return UserRecord(
        id=row.id,
        external_id=row.external_id,
        email=row.email,
        display_name=row.display_name,
        global_role=_enum_value(row.global_role),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _settings_record(row: models.Settings) -> SettingsRecord:
    return SettingsRecord(
        id=row.id,
        user_id=row.user_id,
        brand_name=row.brand_name,
        segment=row.segment,
        tone=row.tone,
        voice=row.voice,
        visual_style=row.visual_style,
        default_preferences=_json(row.default_preferences),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
    )


def _workspace_record(row: models.Workspace) -> WorkspaceRecord:
    return WorkspaceRecord(
        id=row.id,
        name=row.name,
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _brand_record(row: models.Brand) -> BrandRecord:
    return BrandRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        created_by_user_id=row.created_by_user_id,
        name=row.name,
        description=row.description,
        brand_voice=row.brand_voice,
        metadata=_json(row.metadata_json),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _project_record(row: models.Project) -> ProjectRecord:
    return ProjectRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        brand_id=row.brand_id,
        created_by_user_id=row.created_by_user_id,
        name=row.name,
        description=row.description,
        status=row.status,
        metadata=_json(row.metadata_json),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _content_record(row: models.Content) -> ContentRecord:
    return ContentRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        created_by_user_id=row.created_by_user_id,
        content_type=_enum_value(row.content_type),
        title=row.title,
        payload=_json(row.payload),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
        brand_id=row.brand_id,
        project_id=row.project_id,
    )


def _generation_record(row: models.Generation) -> GenerationRecord:
    return GenerationRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        content_id=row.content_id,
        brand_id=row.brand_id,
        project_id=row.project_id,
        requested_by_user_id=row.requested_by_user_id,
        generation_type=_enum_value(row.generation_type),
        model=row.model,
        prompt=row.prompt,
        parameters=_json(row.parameters),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _asset_record(row: models.Asset) -> AssetRecord:
    return AssetRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        brand_id=row.brand_id,
        project_id=row.project_id,
        content_id=row.content_id,
        uploaded_by_user_id=row.uploaded_by_user_id,
        asset_type=row.asset_type,
        storage_path=row.storage_path,
        public_url=row.public_url,
        mime_type=row.mime_type,
        byte_size=row.byte_size,
        checksum=row.checksum,
        metadata=_json(row.metadata_json),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _brand_settings_record(row: models.BrandSettings) -> BrandSettingsRecord:
    return BrandSettingsRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        brand_id=row.brand_id,
        voice_settings=_json(row.voice_settings),
        visual_settings=_json(row.visual_settings),
        generation_defaults=_json(row.generation_defaults),
        metadata=_json(row.metadata_json),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _job_record(row: models.GenerationJob, content_id: UUID) -> GenerationJobRecord:
    return GenerationJobRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        generation_id=row.generation_id,
        content_id=content_id,
        status=row.status,
        external_id=row.external_id,
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        failure_code=row.failure_code,
        failure_message=row.failure_message,
        queued_at=_datetime(row.queued_at),
        started_at=_optional_datetime(row.started_at),
        completed_at=_optional_datetime(row.completed_at),
        failed_at=_optional_datetime(row.failed_at),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _image_record(row: models.Image) -> ImageRecord:
    return ImageRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        content_id=row.content_id,
        generation_id=row.generation_id,
        version_number=row.version_number,
        storage_path=row.storage_path,
        public_url=row.public_url,
        mime_type=row.mime_type,
        width=row.width,
        height=row.height,
        model=row.model,
        prompt=row.prompt,
        metadata=_json(row.metadata_json),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
        deleted_at=_optional_datetime(row.deleted_at),
    )


def _image_generation_status_record(
    job: models.GenerationJob,
    content_id: UUID,
    parameters: dict[str, object] | None,
    image: models.Image | None,
) -> ImageGenerationStatusRecord:
    return ImageGenerationStatusRecord(
        job=_job_record(job, content_id),
        parameters=_json(parameters),
        image=_image_record(image) if image else None,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        external_id: str,
        email: str | None = None,
        display_name: str | None = None,
        global_role: str = "membro",
    ) -> UserRecord:
        row = models.User(
            external_id=external_id,
            email=email,
            display_name=display_name,
            global_role=global_role,
        )
        self._session.add(row)
        flush_or_raise(self._session)
        return _user_record(row)

    def get_by_id(self, user_id: UUID, *, include_deleted: bool = False) -> UserRecord | None:
        statement = select(models.User).where(models.User.id == user_id)
        if not include_deleted:
            statement = statement.where(models.User.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _user_record(row) if row else None

    def get_by_external_id(
        self, external_id: str, *, include_deleted: bool = False
    ) -> UserRecord | None:
        statement = select(models.User).where(models.User.external_id == external_id)
        if not include_deleted:
            statement = statement.where(models.User.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _user_record(row) if row else None

    def list(
        self,
        *,
        include_deleted: bool = False,
        page: PageRequest | None = None,
    ) -> Page[UserRecord]:
        page = page or PageRequest()
        statement = select(models.User)
        count_statement = select(func.count()).select_from(models.User)
        if not include_deleted:
            statement = statement.where(models.User.deleted_at.is_(None))
            count_statement = count_statement.where(models.User.deleted_at.is_(None))
        rows, total = _page(self._session, statement, count_statement, models.User.created_at, page)
        return Page(
            items=[_user_record(row) for row in rows],
            total=total,
            page=page.page,
            limit=page.limit,
        )

    def update_profile(
        self,
        user_id: UUID,
        *,
        email: str | None = None,
        display_name: str | None = None,
    ) -> UserRecord:
        row = self._session.get(models.User, user_id)
        if row is None or row.deleted_at is not None:
            raise EntityNotFoundError("User not found")
        if email is not None:
            row.email = email
        if display_name is not None:
            row.display_name = display_name
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _user_record(row)

    def update(
        self,
        user_id: UUID,
        *,
        email: str | None = None,
        display_name: str | None = None,
        global_role: str | None = None,
    ) -> UserRecord:
        row = self._session.get(models.User, user_id)
        if row is None or row.deleted_at is not None:
            raise EntityNotFoundError("User not found")
        if email is not None:
            row.email = email
        if display_name is not None:
            row.display_name = display_name
        if global_role is not None:
            row.global_role = models.GlobalRole(global_role)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _user_record(row)

    def soft_delete(self, user_id: UUID) -> None:
        row = self._session.get(models.User, user_id)
        if row is None or row.deleted_at is not None:
            raise EntityNotFoundError("User not found")
        timestamp = _now()
        row.deleted_at = timestamp
        row.updated_at = timestamp
        flush_or_raise(self._session)


class SqlAlchemySettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_id(self, user_id: UUID) -> SettingsRecord | None:
        row = self._session.scalars(
            select(models.Settings).where(models.Settings.user_id == user_id)
        ).one_or_none()
        return _settings_record(row) if row else None

    def get_or_create_for_user(self, user_id: UUID) -> SettingsRecord:
        row = self._session.scalars(
            select(models.Settings).where(models.Settings.user_id == user_id).with_for_update()
        ).one_or_none()
        if row is not None:
            return _settings_record(row)
        try:
            return self.create_for_user(user_id)
        except ConflictError:
            row = self._session.scalars(
                select(models.Settings).where(models.Settings.user_id == user_id).with_for_update()
            ).one_or_none()
            if row is None:
                raise
            return _settings_record(row)

    def create_for_user(
        self,
        user_id: UUID,
        *,
        brand_name: str | None = None,
        segment: str | None = None,
        tone: str = "professional",
        voice: str = "Clear and useful",
        visual_style: str = "photographic",
        default_preferences: JsonObject | None = None,
    ) -> SettingsRecord:
        row = models.Settings(
            user_id=user_id,
            brand_name=brand_name,
            segment=segment,
            tone=tone,
            voice=voice,
            visual_style=visual_style,
            default_preferences=_json(default_preferences),
        )
        self._session.add(row)
        flush_or_raise(self._session)
        return _settings_record(row)

    def update_partial(self, user_id: UUID, changes: JsonObject) -> SettingsRecord:
        row = self._session.scalars(
            select(models.Settings).where(models.Settings.user_id == user_id).with_for_update()
        ).one_or_none()
        if row is None:
            raise EntityNotFoundError("Settings not found")
        for field_name in (
            "brand_name",
            "segment",
            "tone",
            "voice",
            "visual_style",
            "default_preferences",
        ):
            if field_name not in changes:
                continue
            value = changes[field_name]
            if field_name == "default_preferences":
                row.default_preferences = _json(value if isinstance(value, dict) else None)
            else:
                setattr(row, field_name, value)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _settings_record(row)


ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}


class SqlAlchemyWorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, name: str, owner_user_id: UUID) -> WorkspaceRecord:
        workspace = models.Workspace(name=name)
        self._session.add(workspace)
        flush_or_raise(self._session)
        membership = models.WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=owner_user_id,
            role=models.WorkspaceRole.OWNER,
        )
        self._session.add(membership)
        flush_or_raise(self._session)
        return _workspace_record(workspace)

    def get_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        include_deleted: bool = False,
    ) -> WorkspaceRecord | None:
        statement = self._scoped_select(user_id).where(models.Workspace.id == workspace_id)
        if not include_deleted:
            statement = statement.where(models.Workspace.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _workspace_record(row) if row else None

    def list_for_user(
        self,
        *,
        user_id: UUID,
        page: PageRequest | None = None,
    ) -> Page[WorkspaceRecord]:
        page = page or PageRequest()
        statement = self._scoped_select(user_id).where(models.Workspace.deleted_at.is_(None))
        count_statement = (
            select(func.count())
            .select_from(models.Workspace)
            .join(
                models.WorkspaceMembership,
                and_(
                    models.WorkspaceMembership.workspace_id == models.Workspace.id,
                    models.WorkspaceMembership.user_id == user_id,
                    models.WorkspaceMembership.deleted_at.is_(None),
                ),
            )
            .where(models.Workspace.deleted_at.is_(None))
        )
        order_column = (
            asc(models.Workspace.created_at)
            if page.sort == "asc"
            else desc(models.Workspace.created_at)
        )
        rows = self._session.scalars(
            statement.order_by(order_column).offset(page.offset).limit(page.limit)
        ).all()
        total = self._session.execute(count_statement).scalar_one()
        return Page(
            items=[_workspace_record(row) for row in rows],
            total=total,
            page=page.page,
            limit=page.limit,
        )

    def update(self, *, user_id: UUID, workspace_id: UUID, name: str) -> WorkspaceRecord:
        row = self._writable_workspace(user_id=user_id, workspace_id=workspace_id)
        row.name = name
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _workspace_record(row)

    def soft_delete(self, *, user_id: UUID, workspace_id: UUID) -> None:
        row = self._writable_workspace(user_id=user_id, workspace_id=workspace_id)
        timestamp = _now()
        row.deleted_at = timestamp
        row.updated_at = timestamp
        flush_or_raise(self._session)

    def user_has_workspace_role(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        minimum_role: str = "viewer",
    ) -> bool:
        minimum_rank = ROLE_RANK[minimum_role]
        row = self._session.scalars(
            select(models.WorkspaceMembership).where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.workspace_id == workspace_id,
                models.WorkspaceMembership.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            return False
        return ROLE_RANK[_enum_value(row.role)] >= minimum_rank

    def _writable_workspace(self, *, user_id: UUID, workspace_id: UUID) -> models.Workspace:
        if not self.user_has_workspace_role(
            user_id=user_id,
            workspace_id=workspace_id,
            minimum_role="admin",
        ):
            raise EntityNotFoundError("Workspace not found")
        row = self._session.get(models.Workspace, workspace_id)
        if row is None or row.deleted_at is not None:
            raise EntityNotFoundError("Workspace not found")
        return row

    def _scoped_select(self, user_id: UUID) -> Select[tuple[models.Workspace]]:
        return (
            select(models.Workspace)
            .join(
                models.WorkspaceMembership,
                and_(
                    models.WorkspaceMembership.workspace_id == models.Workspace.id,
                    models.WorkspaceMembership.user_id == user_id,
                    models.WorkspaceMembership.deleted_at.is_(None),
                ),
            )
            .where(models.WorkspaceMembership.deleted_at.is_(None))
        )


def _user_has_workspace_role(
    session: Session,
    *,
    user_id: UUID,
    workspace_id: UUID,
    minimum_role: str = "viewer",
) -> bool:
    return SqlAlchemyWorkspaceRepository(session).user_has_workspace_role(
        user_id=user_id,
        workspace_id=workspace_id,
        minimum_role=minimum_role,
    )


class SqlAlchemyBrandRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        workspace_id: UUID,
        created_by_user_id: UUID | None,
        name: str,
        description: str | None = None,
        brand_voice: str | None = None,
        metadata: JsonObject | None = None,
    ) -> BrandRecord:
        if created_by_user_id is not None and not _user_has_workspace_role(
            self._session,
            user_id=created_by_user_id,
            workspace_id=workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Workspace not found")
        row = models.Brand(
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            name=name,
            description=description,
            brand_voice=brand_voice,
            metadata_json=_json(metadata),
        )
        self._session.add(row)
        flush_or_raise(self._session)
        return _brand_record(row)

    def get_for_user(
        self,
        *,
        user_id: UUID,
        brand_id: UUID,
        include_deleted: bool = False,
    ) -> BrandRecord | None:
        statement = self._scoped_select(user_id).where(models.Brand.id == brand_id)
        if not include_deleted:
            statement = statement.where(models.Brand.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _brand_record(row) if row else None

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[BrandRecord]:
        page = page or PageRequest()
        statement = self._scoped_select(user_id).where(models.Brand.deleted_at.is_(None))
        count_statement = self._scoped_count(user_id).where(models.Brand.deleted_at.is_(None))
        if workspace_id is not None:
            statement = statement.where(models.Brand.workspace_id == workspace_id)
            count_statement = count_statement.where(models.Brand.workspace_id == workspace_id)
        rows, total = _page(
            self._session, statement, count_statement, models.Brand.created_at, page
        )
        return Page(
            items=[_brand_record(row) for row in rows],
            total=total,
            page=page.page,
            limit=page.limit,
        )

    def update(
        self,
        *,
        user_id: UUID,
        brand_id: UUID,
        name: str | None = None,
        description: str | None = None,
        brand_voice: str | None = None,
        metadata: JsonObject | None = None,
    ) -> BrandRecord:
        row = self._writable_brand(user_id=user_id, brand_id=brand_id)
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if brand_voice is not None:
            row.brand_voice = brand_voice
        if metadata is not None:
            row.metadata_json = _json(metadata)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _brand_record(row)

    def soft_delete(self, *, user_id: UUID, brand_id: UUID) -> None:
        row = self._writable_brand(user_id=user_id, brand_id=brand_id)
        timestamp = _now()
        row.deleted_at = timestamp
        row.updated_at = timestamp
        flush_or_raise(self._session)

    def _writable_brand(self, *, user_id: UUID, brand_id: UUID) -> models.Brand:
        row = self._session.scalars(
            self._scoped_select(user_id).where(
                models.Brand.id == brand_id,
                models.Brand.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None or not _user_has_workspace_role(
            self._session,
            user_id=user_id,
            workspace_id=row.workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Brand not found")
        return row

    def _scoped_select(self, user_id: UUID) -> Select[tuple[models.Brand]]:
        return _scoped_resource_select(user_id, models.Brand)

    def _scoped_count(self, user_id: UUID) -> Select[tuple[int]]:
        return _scoped_resource_count(user_id, models.Brand)


class SqlAlchemyProjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        workspace_id: UUID,
        brand_id: UUID | None,
        created_by_user_id: UUID | None,
        name: str,
        description: str | None = None,
        status: str = "ACTIVE",
        metadata: JsonObject | None = None,
    ) -> ProjectRecord:
        if created_by_user_id is not None and not _user_has_workspace_role(
            self._session,
            user_id=created_by_user_id,
            workspace_id=workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Workspace not found")
        row = models.Project(
            workspace_id=workspace_id,
            brand_id=brand_id,
            created_by_user_id=created_by_user_id,
            name=name,
            description=description,
            status=status,
            metadata_json=_json(metadata),
        )
        self._session.add(row)
        flush_or_raise(self._session)
        return _project_record(row)

    def get_for_user(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        include_deleted: bool = False,
    ) -> ProjectRecord | None:
        statement = self._scoped_select(user_id).where(models.Project.id == project_id)
        if not include_deleted:
            statement = statement.where(models.Project.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _project_record(row) if row else None

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        brand_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[ProjectRecord]:
        page = page or PageRequest()
        statement = self._scoped_select(user_id).where(models.Project.deleted_at.is_(None))
        count_statement = self._scoped_count(user_id).where(models.Project.deleted_at.is_(None))
        if workspace_id is not None:
            statement = statement.where(models.Project.workspace_id == workspace_id)
            count_statement = count_statement.where(models.Project.workspace_id == workspace_id)
        if brand_id is not None:
            statement = statement.where(models.Project.brand_id == brand_id)
            count_statement = count_statement.where(models.Project.brand_id == brand_id)
        rows, total = _page(
            self._session, statement, count_statement, models.Project.created_at, page
        )
        return Page(
            items=[_project_record(row) for row in rows],
            total=total,
            page=page.page,
            limit=page.limit,
        )

    def update(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        metadata: JsonObject | None = None,
    ) -> ProjectRecord:
        row = self._writable_project(user_id=user_id, project_id=project_id)
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if status is not None:
            row.status = status
        if metadata is not None:
            row.metadata_json = _json(metadata)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _project_record(row)

    def soft_delete(self, *, user_id: UUID, project_id: UUID) -> None:
        row = self._writable_project(user_id=user_id, project_id=project_id)
        timestamp = _now()
        row.deleted_at = timestamp
        row.updated_at = timestamp
        flush_or_raise(self._session)

    def _writable_project(self, *, user_id: UUID, project_id: UUID) -> models.Project:
        row = self._session.scalars(
            self._scoped_select(user_id).where(
                models.Project.id == project_id,
                models.Project.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None or not _user_has_workspace_role(
            self._session,
            user_id=user_id,
            workspace_id=row.workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Project not found")
        return row

    def _scoped_select(self, user_id: UUID) -> Select[tuple[models.Project]]:
        return _scoped_resource_select(user_id, models.Project)

    def _scoped_count(self, user_id: UUID) -> Select[tuple[int]]:
        return _scoped_resource_count(user_id, models.Project)


def _scoped_resource_select(user_id: UUID, model: type[Any]) -> Select[Any]:
    return (
        select(model)
        .join(
            models.WorkspaceMembership,
            and_(
                models.WorkspaceMembership.workspace_id == model.workspace_id,
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
            ),
        )
        .join(
            models.Workspace,
            and_(
                models.Workspace.id == model.workspace_id,
                models.Workspace.deleted_at.is_(None),
            ),
        )
    )


def _scoped_resource_count(user_id: UUID, model: type[Any]) -> Select[tuple[int]]:
    return (
        select(func.count())
        .select_from(model)
        .join(
            models.WorkspaceMembership,
            and_(
                models.WorkspaceMembership.workspace_id == model.workspace_id,
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
            ),
        )
        .join(
            models.Workspace,
            and_(
                models.Workspace.id == model.workspace_id,
                models.Workspace.deleted_at.is_(None),
            ),
        )
    )


def _page(
    session: Session,
    statement: Select[Any],
    count_statement: Select[Any],
    order_by: Any,
    page: PageRequest,
) -> tuple[list[Any], int]:
    order_column = asc(order_by) if page.sort == "asc" else desc(order_by)
    rows = session.scalars(
        statement.order_by(order_column).offset(page.offset).limit(page.limit)
    ).all()
    total = session.execute(count_statement).scalar_one()
    return list(rows), total


class SqlAlchemyContentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        workspace_id: UUID,
        created_by_user_id: UUID | None,
        content_type: str = "IMAGE",
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        title: str | None = None,
        payload: JsonObject | None = None,
    ) -> ContentRecord:
        row = models.Content(
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            content_type=content_type,
            brand_id=brand_id,
            project_id=project_id,
            title=title,
            payload=_json(payload),
        )
        self._session.add(row)
        flush_or_raise(self._session)
        return _content_record(row)

    def create_text_generation(
        self,
        *,
        workspace_id: UUID,
        requested_by_user_id: UUID,
        title: str,
        payload: JsonObject,
        model: str,
        prompt: str,
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        parameters: JsonObject | None = None,
    ) -> GeneratedTextContentRecord:
        if not self.user_has_workspace_access(
            user_id=requested_by_user_id,
            workspace_id=workspace_id,
        ):
            raise EntityNotFoundError("Workspace not found")

        content = models.Content(
            workspace_id=workspace_id,
            created_by_user_id=requested_by_user_id,
            content_type=models.ContentType.TEXT,
            brand_id=brand_id,
            project_id=project_id,
            title=title,
            payload=_json(payload),
        )
        self._session.add(content)
        flush_or_raise(self._session)

        generation = models.Generation(
            workspace_id=workspace_id,
            content_id=content.id,
            requested_by_user_id=requested_by_user_id,
            generation_type=models.GenerationType.TEXT,
            brand_id=brand_id,
            project_id=project_id,
            model=model,
            prompt=prompt,
            parameters=_json(parameters),
        )
        self._session.add(generation)
        flush_or_raise(self._session)

        return GeneratedTextContentRecord(
            content=_content_record(content),
            generation_id=generation.id,
            generation_model=model,
            generation_parameters=_json(generation.parameters),
        )

    def user_has_workspace_access(self, *, user_id: UUID, workspace_id: UUID) -> bool:
        statement = (
            select(func.count())
            .select_from(models.WorkspaceMembership)
            .join(
                models.Workspace,
                and_(
                    models.Workspace.id == models.WorkspaceMembership.workspace_id,
                    models.Workspace.deleted_at.is_(None),
                ),
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.workspace_id == workspace_id,
                models.WorkspaceMembership.deleted_at.is_(None),
            )
        )
        return self._session.execute(statement).scalar_one() > 0

    def get_by_id_for_user(
        self,
        *,
        user_id: UUID,
        content_id: UUID,
        include_deleted: bool = False,
    ) -> ContentRecord | None:
        statement = self._scoped_select(user_id).where(models.Content.id == content_id)
        if not include_deleted:
            statement = statement.where(models.Content.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _content_record(row) if row else None

    def list_for_user(
        self,
        *,
        user_id: UUID,
        filters: ContentFilters | None = None,
        page: PageRequest | None = None,
    ) -> Page[ContentRecord]:
        filters = filters or ContentFilters()
        page = page or PageRequest()
        statement = self._apply_content_filters(self._scoped_select(user_id), filters)
        count_statement = self._apply_content_filters(self._scoped_count(user_id), filters)
        order_column = (
            asc(models.Content.created_at)
            if page.sort == "asc"
            else desc(models.Content.created_at)
        )
        rows = self._session.scalars(
            statement.order_by(order_column).offset(page.offset).limit(page.limit)
        ).all()
        total = self._session.execute(count_statement).scalar_one()
        return Page(
            items=[_content_record(row) for row in rows],
            total=total,
            page=page.page,
            limit=page.limit,
        )

    def update(
        self,
        content_id: UUID,
        *,
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        title: str | None = None,
        payload: JsonObject | None = None,
    ) -> ContentRecord:
        row = self._session.get(models.Content, content_id)
        if row is None or row.deleted_at is not None:
            raise EntityNotFoundError("Content not found")
        if title is not None:
            row.title = title
        if brand_id is not None:
            row.brand_id = brand_id
        if project_id is not None:
            row.project_id = project_id
        if payload is not None:
            row.payload = _json(payload)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _content_record(row)

    def soft_delete(self, content_id: UUID) -> None:
        row = self._session.get(models.Content, content_id)
        if row is None or row.deleted_at is not None:
            raise EntityNotFoundError("Content not found")
        timestamp = _now()
        row.deleted_at = timestamp
        row.updated_at = timestamp
        flush_or_raise(self._session)

    def _scoped_select(self, user_id: UUID) -> Select[tuple[models.Content]]:
        return (
            select(models.Content)
            .join(
                models.WorkspaceMembership,
                and_(
                    models.WorkspaceMembership.workspace_id == models.Content.workspace_id,
                    models.WorkspaceMembership.user_id == user_id,
                    models.WorkspaceMembership.deleted_at.is_(None),
                ),
            )
            .where(models.WorkspaceMembership.deleted_at.is_(None))
        )

    def _scoped_count(self, user_id: UUID) -> Select[tuple[int]]:
        return (
            select(func.count())
            .select_from(models.Content)
            .join(
                models.WorkspaceMembership,
                and_(
                    models.WorkspaceMembership.workspace_id == models.Content.workspace_id,
                    models.WorkspaceMembership.user_id == user_id,
                    models.WorkspaceMembership.deleted_at.is_(None),
                ),
            )
        )

    def _apply_content_filters(
        self,
        statement: Select[Any],
        filters: ContentFilters,
    ) -> Select[Any]:
        if not filters.include_deleted:
            statement = statement.where(models.Content.deleted_at.is_(None))
        if filters.workspace_id is not None:
            statement = statement.where(models.Content.workspace_id == filters.workspace_id)
        if filters.content_type is not None:
            statement = statement.where(models.Content.content_type == filters.content_type)
        if filters.created_from is not None:
            statement = statement.where(models.Content.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(models.Content.created_at <= filters.created_to)
        return statement


class SqlAlchemyGenerationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        workspace_id: UUID,
        content_id: UUID,
        requested_by_user_id: UUID | None,
        model: str,
        prompt: str,
        generation_type: str = "TEXT",
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        parameters: JsonObject | None = None,
    ) -> GenerationRecord:
        if requested_by_user_id is not None and not _user_has_workspace_role(
            self._session,
            user_id=requested_by_user_id,
            workspace_id=workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Workspace not found")
        row = models.Generation(
            workspace_id=workspace_id,
            content_id=content_id,
            requested_by_user_id=requested_by_user_id,
            generation_type=generation_type,
            brand_id=brand_id,
            project_id=project_id,
            model=model,
            prompt=prompt,
            parameters=_json(parameters),
        )
        self._session.add(row)
        flush_or_raise(self._session)
        return _generation_record(row)

    def get_for_user(
        self,
        *,
        user_id: UUID,
        generation_id: UUID,
        include_deleted: bool = False,
    ) -> GenerationRecord | None:
        statement = self._scoped_select(user_id).where(models.Generation.id == generation_id)
        if not include_deleted:
            statement = statement.where(models.Generation.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _generation_record(row) if row else None

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        content_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[GenerationRecord]:
        page = page or PageRequest()
        statement = self._scoped_select(user_id).where(models.Generation.deleted_at.is_(None))
        count_statement = self._scoped_count(user_id).where(models.Generation.deleted_at.is_(None))
        if workspace_id is not None:
            statement = statement.where(models.Generation.workspace_id == workspace_id)
            count_statement = count_statement.where(models.Generation.workspace_id == workspace_id)
        if content_id is not None:
            statement = statement.where(models.Generation.content_id == content_id)
            count_statement = count_statement.where(models.Generation.content_id == content_id)
        rows, total = _page(
            self._session, statement, count_statement, models.Generation.created_at, page
        )
        return Page(
            items=[_generation_record(row) for row in rows],
            total=total,
            page=page.page,
            limit=page.limit,
        )

    def update(
        self,
        *,
        user_id: UUID,
        generation_id: UUID,
        model: str | None = None,
        prompt: str | None = None,
        parameters: JsonObject | None = None,
    ) -> GenerationRecord:
        row = self._writable_generation(user_id=user_id, generation_id=generation_id)
        if model is not None:
            row.model = model
        if prompt is not None:
            row.prompt = prompt
        if parameters is not None:
            row.parameters = _json(parameters)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _generation_record(row)

    def soft_delete(self, *, user_id: UUID, generation_id: UUID) -> None:
        row = self._writable_generation(user_id=user_id, generation_id=generation_id)
        timestamp = _now()
        row.deleted_at = timestamp
        row.updated_at = timestamp
        flush_or_raise(self._session)

    def _writable_generation(self, *, user_id: UUID, generation_id: UUID) -> models.Generation:
        row = self._session.scalars(
            self._scoped_select(user_id).where(
                models.Generation.id == generation_id,
                models.Generation.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None or not _user_has_workspace_role(
            self._session,
            user_id=user_id,
            workspace_id=row.workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Generation not found")
        return row

    def _scoped_select(self, user_id: UUID) -> Select[tuple[models.Generation]]:
        return _scoped_resource_select(user_id, models.Generation)

    def _scoped_count(self, user_id: UUID) -> Select[tuple[int]]:
        return _scoped_resource_count(user_id, models.Generation)


class SqlAlchemyAssetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        workspace_id: UUID,
        uploaded_by_user_id: UUID | None,
        asset_type: str,
        storage_path: str,
        mime_type: str,
        byte_size: int,
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        content_id: UUID | None = None,
        public_url: str | None = None,
        checksum: str | None = None,
        metadata: JsonObject | None = None,
    ) -> AssetRecord:
        if uploaded_by_user_id is not None and not _user_has_workspace_role(
            self._session,
            user_id=uploaded_by_user_id,
            workspace_id=workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Workspace not found")
        row = models.Asset(
            workspace_id=workspace_id,
            brand_id=brand_id,
            project_id=project_id,
            content_id=content_id,
            uploaded_by_user_id=uploaded_by_user_id,
            asset_type=asset_type,
            storage_path=storage_path,
            public_url=public_url,
            mime_type=mime_type,
            byte_size=byte_size,
            checksum=checksum,
            metadata_json=_json(metadata),
        )
        self._session.add(row)
        flush_or_raise(self._session)
        return _asset_record(row)

    def get_for_user(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        include_deleted: bool = False,
    ) -> AssetRecord | None:
        statement = self._scoped_select(user_id).where(models.Asset.id == asset_id)
        if not include_deleted:
            statement = statement.where(models.Asset.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _asset_record(row) if row else None

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        content_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[AssetRecord]:
        page = page or PageRequest()
        statement = self._scoped_select(user_id).where(models.Asset.deleted_at.is_(None))
        count_statement = self._scoped_count(user_id).where(models.Asset.deleted_at.is_(None))
        for column, value in [
            (models.Asset.workspace_id, workspace_id),
            (models.Asset.brand_id, brand_id),
            (models.Asset.project_id, project_id),
            (models.Asset.content_id, content_id),
        ]:
            if value is not None:
                statement = statement.where(column == value)
                count_statement = count_statement.where(column == value)
        rows, total = _page(
            self._session, statement, count_statement, models.Asset.created_at, page
        )
        return Page(
            items=[_asset_record(row) for row in rows],
            total=total,
            page=page.page,
            limit=page.limit,
        )

    def update(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        asset_type: str | None = None,
        public_url: str | None = None,
        metadata: JsonObject | None = None,
    ) -> AssetRecord:
        row = self._writable_asset(user_id=user_id, asset_id=asset_id)
        if asset_type is not None:
            row.asset_type = asset_type
        if public_url is not None:
            row.public_url = public_url
        if metadata is not None:
            row.metadata_json = _json(metadata)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _asset_record(row)

    def soft_delete(self, *, user_id: UUID, asset_id: UUID) -> None:
        row = self._writable_asset(user_id=user_id, asset_id=asset_id)
        timestamp = _now()
        row.deleted_at = timestamp
        row.updated_at = timestamp
        flush_or_raise(self._session)

    def _writable_asset(self, *, user_id: UUID, asset_id: UUID) -> models.Asset:
        row = self._session.scalars(
            self._scoped_select(user_id).where(
                models.Asset.id == asset_id,
                models.Asset.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None or not _user_has_workspace_role(
            self._session,
            user_id=user_id,
            workspace_id=row.workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Asset not found")
        return row

    def _scoped_select(self, user_id: UUID) -> Select[tuple[models.Asset]]:
        return _scoped_resource_select(user_id, models.Asset)

    def _scoped_count(self, user_id: UUID) -> Select[tuple[int]]:
        return _scoped_resource_count(user_id, models.Asset)


class SqlAlchemyBrandSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_user(
        self,
        *,
        user_id: UUID,
        brand_id: UUID,
        include_deleted: bool = False,
    ) -> BrandSettingsRecord | None:
        statement = self._scoped_select(user_id).where(models.BrandSettings.brand_id == brand_id)
        if not include_deleted:
            statement = statement.where(models.BrandSettings.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _brand_settings_record(row) if row else None

    def upsert(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        brand_id: UUID,
        voice_settings: JsonObject | None = None,
        visual_settings: JsonObject | None = None,
        generation_defaults: JsonObject | None = None,
        metadata: JsonObject | None = None,
    ) -> BrandSettingsRecord:
        if not _user_has_workspace_role(
            self._session,
            user_id=user_id,
            workspace_id=workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Brand not found")
        row = self._session.scalars(
            select(models.BrandSettings).where(models.BrandSettings.brand_id == brand_id)
        ).one_or_none()
        if row is None:
            row = models.BrandSettings(
                workspace_id=workspace_id,
                brand_id=brand_id,
                voice_settings=_json(voice_settings),
                visual_settings=_json(visual_settings),
                generation_defaults=_json(generation_defaults),
                metadata_json=_json(metadata),
            )
            self._session.add(row)
        else:
            row.deleted_at = None
            if voice_settings is not None:
                row.voice_settings = _json(voice_settings)
            if visual_settings is not None:
                row.visual_settings = _json(visual_settings)
            if generation_defaults is not None:
                row.generation_defaults = _json(generation_defaults)
            if metadata is not None:
                row.metadata_json = _json(metadata)
            row.updated_at = _now()
        flush_or_raise(self._session)
        return _brand_settings_record(row)

    def update(
        self,
        *,
        user_id: UUID,
        brand_id: UUID,
        voice_settings: JsonObject | None = None,
        visual_settings: JsonObject | None = None,
        generation_defaults: JsonObject | None = None,
        metadata: JsonObject | None = None,
    ) -> BrandSettingsRecord:
        row = self._writable_settings(user_id=user_id, brand_id=brand_id)
        if voice_settings is not None:
            row.voice_settings = _json(voice_settings)
        if visual_settings is not None:
            row.visual_settings = _json(visual_settings)
        if generation_defaults is not None:
            row.generation_defaults = _json(generation_defaults)
        if metadata is not None:
            row.metadata_json = _json(metadata)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _brand_settings_record(row)

    def soft_delete(self, *, user_id: UUID, brand_id: UUID) -> None:
        row = self._writable_settings(user_id=user_id, brand_id=brand_id)
        timestamp = _now()
        row.deleted_at = timestamp
        row.updated_at = timestamp
        flush_or_raise(self._session)

    def _writable_settings(self, *, user_id: UUID, brand_id: UUID) -> models.BrandSettings:
        row = self._session.scalars(
            self._scoped_select(user_id).where(
                models.BrandSettings.brand_id == brand_id,
                models.BrandSettings.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None or not _user_has_workspace_role(
            self._session,
            user_id=user_id,
            workspace_id=row.workspace_id,
            minimum_role="editor",
        ):
            raise EntityNotFoundError("Brand settings not found")
        return row

    def _scoped_select(self, user_id: UUID) -> Select[tuple[models.BrandSettings]]:
        return _scoped_resource_select(user_id, models.BrandSettings)


class SqlAlchemyImageGenerationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_image_generation(
        self,
        *,
        workspace_id: UUID,
        content_id: UUID,
        requested_by_user_id: UUID | None,
        model: str,
        prompt: str,
        parameters: JsonObject | None = None,
        external_id: str | None = None,
    ) -> GenerationJobRecord:
        content = self._session.scalars(
            select(models.Content).where(
                models.Content.id == content_id,
                models.Content.workspace_id == workspace_id,
                models.Content.deleted_at.is_(None),
            )
        ).one_or_none()
        if content is None:
            raise EntityNotFoundError("Content not found")

        generation = models.Generation(
            workspace_id=workspace_id,
            content_id=content_id,
            requested_by_user_id=requested_by_user_id,
            model=model,
            prompt=prompt,
            parameters=_json(parameters),
        )
        self._session.add(generation)
        flush_or_raise(self._session)

        job = models.GenerationJob(
            workspace_id=workspace_id,
            generation_id=generation.id,
            external_id=external_id,
        )
        self._session.add(job)
        flush_or_raise(self._session)
        self._add_status_event(job.id, None, GenerationJobStatus.PENDING)
        flush_or_raise(self._session)
        return _job_record(job, content_id)

    def get_job_for_user(
        self,
        *,
        user_id: UUID,
        job_id: UUID,
        include_deleted: bool = False,
    ) -> GenerationJobRecord | None:
        statement = self._scoped_job_select(user_id).where(models.GenerationJob.id == job_id)
        if not include_deleted:
            statement = statement.where(models.GenerationJob.deleted_at.is_(None))
        row = self._session.execute(statement).one_or_none()
        if row is None:
            return None
        job, content_id = row
        return _job_record(job, content_id)

    def list_history_for_user(
        self,
        *,
        user_id: UUID,
        filters: GenerationHistoryFilters | None = None,
        page: PageRequest | None = None,
    ) -> Page[GenerationJobRecord]:
        filters = filters or GenerationHistoryFilters()
        page = page or PageRequest()
        statement = self._apply_history_filters(self._scoped_job_select(user_id), filters)
        count_statement = self._apply_history_filters(self._scoped_job_count(user_id), filters)
        order_column = (
            asc(models.GenerationJob.created_at)
            if page.sort == "asc"
            else desc(models.GenerationJob.created_at)
        )
        rows = self._session.execute(
            statement.order_by(order_column).offset(page.offset).limit(page.limit)
        ).all()
        total = self._session.execute(count_statement).scalar_one()
        return Page(
            items=[_job_record(job, content_id) for job, content_id in rows],
            total=total,
            page=page.page,
            limit=page.limit,
        )

    def claim_next_pending(self, *, workspace_id: UUID | None = None) -> GenerationJobRecord | None:
        statement = (
            select(models.GenerationJob)
            .where(
                models.GenerationJob.status == GenerationJobStatus.PENDING,
                models.GenerationJob.deleted_at.is_(None),
            )
            .order_by(models.GenerationJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if workspace_id is not None:
            statement = statement.where(models.GenerationJob.workspace_id == workspace_id)

        job = self._session.scalars(statement).first()
        if job is None:
            return None
        self._transition_job(job, GenerationJobStatus.PROCESSING)
        timestamp = _now()
        job.started_at = timestamp
        job.attempt_count += 1
        job.updated_at = timestamp
        flush_or_raise(self._session)
        content_id = self._content_id_for_generation(job.generation_id)
        return _job_record(job, content_id)

    def next_image_version(self, content_id: UUID) -> int:
        return self._next_image_version(content_id)

    def get_status_for_user(
        self,
        *,
        user_id: UUID,
        job_id: UUID,
        include_deleted: bool = False,
    ) -> ImageGenerationStatusRecord | None:
        statement = self._scoped_status_select(user_id).where(models.GenerationJob.id == job_id)
        if not include_deleted:
            statement = statement.where(models.GenerationJob.deleted_at.is_(None))
        row = self._session.execute(statement).one_or_none()
        if row is None:
            return None
        job, content_id, parameters, image = row
        return _image_generation_status_record(job, content_id, parameters, image)

    def get_status_by_external_id_for_user(
        self,
        *,
        user_id: UUID,
        external_id: str,
        include_deleted: bool = False,
    ) -> ImageGenerationStatusRecord | None:
        statement = self._scoped_status_select(user_id).where(
            models.GenerationJob.external_id == external_id
        )
        if not include_deleted:
            statement = statement.where(models.GenerationJob.deleted_at.is_(None))
        row = self._session.execute(statement).one_or_none()
        if row is None:
            return None
        job, content_id, parameters, image = row
        return _image_generation_status_record(job, content_id, parameters, image)

    def claim_pending_by_id(self, job_id: UUID) -> ImageGenerationWorkItem | None:
        statement = (
            select(models.GenerationJob, models.Generation, models.User)
            .join(
                models.Generation,
                and_(
                    models.Generation.id == models.GenerationJob.generation_id,
                    models.Generation.workspace_id == models.GenerationJob.workspace_id,
                    models.Generation.deleted_at.is_(None),
                ),
            )
            .join(
                models.User,
                and_(
                    models.User.id == models.Generation.requested_by_user_id,
                    models.User.deleted_at.is_(None),
                ),
            )
            .where(
                models.GenerationJob.id == job_id,
                models.GenerationJob.status == GenerationJobStatus.PENDING,
                models.GenerationJob.deleted_at.is_(None),
            )
            .with_for_update(of=models.GenerationJob)
        )
        row = self._session.execute(statement).one_or_none()
        if row is None:
            return None
        job, generation, user = row
        self._transition_job(job, GenerationJobStatus.PROCESSING)
        timestamp = _now()
        job.started_at = timestamp
        job.attempt_count += 1
        job.updated_at = timestamp
        flush_or_raise(self._session)
        return ImageGenerationWorkItem(
            job=_job_record(job, generation.content_id),
            model=generation.model,
            prompt=generation.prompt,
            parameters=_json(generation.parameters),
            requested_by_user=_user_record(user),
        )

    def get_image_for_user(
        self,
        *,
        user_id: UUID,
        image_id: UUID,
        include_deleted: bool = False,
    ) -> ImageRecord | None:
        statement = (
            select(models.Image)
            .join(
                models.Content,
                and_(
                    models.Content.id == models.Image.content_id,
                    models.Content.workspace_id == models.Image.workspace_id,
                    models.Content.deleted_at.is_(None),
                ),
            )
            .join(
                models.WorkspaceMembership,
                and_(
                    models.WorkspaceMembership.workspace_id == models.Image.workspace_id,
                    models.WorkspaceMembership.user_id == user_id,
                    models.WorkspaceMembership.deleted_at.is_(None),
                ),
            )
            .where(models.Image.id == image_id)
        )
        if not include_deleted:
            statement = statement.where(models.Image.deleted_at.is_(None))
        row = self._session.scalars(statement).one_or_none()
        return _image_record(row) if row else None

    def complete_job(self, job_id: UUID, image: ImageMetadata) -> ImageRecord:
        job = self._locked_job(job_id)
        generation = self._generation_for_job(job)
        self._lock_content(generation.content_id)
        self._transition_job(job, GenerationJobStatus.COMPLETED)
        version_number = (
            image.version_number
            if image.version_number is not None
            else self._next_image_version(generation.content_id)
        )
        timestamp = _now()
        job.completed_at = timestamp
        job.updated_at = timestamp
        image_row = models.Image(
            workspace_id=job.workspace_id,
            content_id=generation.content_id,
            generation_id=job.generation_id,
            version_number=version_number,
            storage_path=image.storage_path,
            public_url=image.public_url,
            mime_type=image.mime_type,
            width=image.width,
            height=image.height,
            model=image.model,
            prompt=image.prompt,
            metadata_json=_json(image.metadata),
        )
        self._session.add(image_row)
        flush_or_raise(self._session)
        return _image_record(image_row)

    def fail_job(
        self,
        job_id: UUID,
        *,
        failure_code: str,
        failure_message: str,
    ) -> GenerationJobRecord:
        job = self._locked_job(job_id)
        self._transition_job(job, GenerationJobStatus.FAILED)
        timestamp = _now()
        job.failure_code = failure_code
        job.failure_message = failure_message
        job.failed_at = timestamp
        job.updated_at = timestamp
        flush_or_raise(self._session)
        content_id = self._content_id_for_generation(job.generation_id)
        return _job_record(job, content_id)

    def _scoped_job_select(self, user_id: UUID) -> Select[tuple[models.GenerationJob, UUID]]:
        return (
            select(models.GenerationJob, models.Generation.content_id)
            .join(
                models.Generation,
                and_(
                    models.Generation.id == models.GenerationJob.generation_id,
                    models.Generation.workspace_id == models.GenerationJob.workspace_id,
                ),
            )
            .join(
                models.WorkspaceMembership,
                and_(
                    models.WorkspaceMembership.workspace_id == models.GenerationJob.workspace_id,
                    models.WorkspaceMembership.user_id == user_id,
                    models.WorkspaceMembership.deleted_at.is_(None),
                ),
            )
        )

    def _scoped_job_count(self, user_id: UUID) -> Select[tuple[int]]:
        return (
            select(func.count())
            .select_from(models.GenerationJob)
            .join(
                models.Generation,
                and_(
                    models.Generation.id == models.GenerationJob.generation_id,
                    models.Generation.workspace_id == models.GenerationJob.workspace_id,
                ),
            )
            .join(
                models.WorkspaceMembership,
                and_(
                    models.WorkspaceMembership.workspace_id == models.GenerationJob.workspace_id,
                    models.WorkspaceMembership.user_id == user_id,
                    models.WorkspaceMembership.deleted_at.is_(None),
                ),
            )
        )

    def _scoped_status_select(self, user_id: UUID) -> Select[Any]:
        return (
            select(
                models.GenerationJob,
                models.Generation.content_id,
                models.Generation.parameters,
                models.Image,
            )
            .join(
                models.Generation,
                and_(
                    models.Generation.id == models.GenerationJob.generation_id,
                    models.Generation.workspace_id == models.GenerationJob.workspace_id,
                    models.Generation.deleted_at.is_(None),
                ),
            )
            .join(
                models.WorkspaceMembership,
                and_(
                    models.WorkspaceMembership.workspace_id == models.GenerationJob.workspace_id,
                    models.WorkspaceMembership.user_id == user_id,
                    models.WorkspaceMembership.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                models.Image,
                and_(
                    models.Image.generation_id == models.GenerationJob.generation_id,
                    models.Image.workspace_id == models.GenerationJob.workspace_id,
                    models.Image.content_id == models.Generation.content_id,
                    models.Image.deleted_at.is_(None),
                ),
            )
        )

    def _apply_history_filters(
        self,
        statement: Select[Any],
        filters: GenerationHistoryFilters,
    ) -> Select[Any]:
        if not filters.include_deleted:
            statement = statement.where(models.GenerationJob.deleted_at.is_(None))
        if filters.workspace_id is not None:
            statement = statement.where(models.GenerationJob.workspace_id == filters.workspace_id)
        if filters.content_id is not None:
            statement = statement.where(models.Generation.content_id == filters.content_id)
        if filters.status is not None:
            statement = statement.where(models.GenerationJob.status == filters.status)
        if filters.created_from is not None:
            statement = statement.where(models.GenerationJob.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(models.GenerationJob.created_at <= filters.created_to)
        return statement

    def _locked_job(self, job_id: UUID) -> models.GenerationJob:
        job = self._session.scalars(
            select(models.GenerationJob)
            .where(
                models.GenerationJob.id == job_id,
                models.GenerationJob.deleted_at.is_(None),
            )
            .with_for_update()
        ).one_or_none()
        if job is None:
            raise EntityNotFoundError("Generation Job not found")
        return job

    def _generation_for_job(self, job: models.GenerationJob) -> models.Generation:
        generation = self._session.scalars(
            select(models.Generation).where(
                models.Generation.id == job.generation_id,
                models.Generation.workspace_id == job.workspace_id,
                models.Generation.deleted_at.is_(None),
            )
        ).one_or_none()
        if generation is None:
            raise EntityNotFoundError("Generation not found")
        return generation

    def _lock_content(self, content_id: UUID) -> None:
        content = self._session.scalars(
            select(models.Content)
            .where(models.Content.id == content_id, models.Content.deleted_at.is_(None))
            .with_for_update()
        ).one_or_none()
        if content is None:
            raise EntityNotFoundError("Content not found")

    def _transition_job(self, job: models.GenerationJob, target: GenerationJobStatus) -> None:
        current = job.status
        if not can_transition(current, target):
            raise InvalidStateTransitionError(f"Cannot transition {current} to {target}")
        job.status = target
        self._add_status_event(job.id, current, target)

    def _add_status_event(
        self,
        job_id: UUID,
        previous_status: GenerationJobStatus | None,
        status: GenerationJobStatus,
    ) -> None:
        self._session.add(
            models.GenerationJobStatusEvent(
                generation_job_id=job_id,
                previous_status=previous_status,
                status=status,
            )
        )

    def _content_id_for_generation(self, generation_id: UUID) -> UUID:
        content_id = self._session.execute(
            select(models.Generation.content_id).where(models.Generation.id == generation_id)
        ).scalar_one_or_none()
        if content_id is None:
            raise EntityNotFoundError("Generation not found")
        return content_id

    def _next_image_version(self, content_id: UUID) -> int:
        version = self._session.execute(
            select(func.coalesce(func.max(models.Image.version_number), 0) + 1).where(
                models.Image.content_id == content_id
            )
        ).scalar_one()
        return version
