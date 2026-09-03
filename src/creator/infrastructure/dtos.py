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
    ContentFilters,
    ContentRecord,
    GeneratedTextContentRecord,
    GenerationHistoryFilters,
    GenerationJobRecord,
    ImageGenerationStatusRecord,
    ImageGenerationWorkItem,
    ImageMetadata,
    ImageRecord,
    JsonObject,
    Page,
    PageRequest,
    SettingsRecord,
    UserRecord,
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
        preferences=_json(row.preferences),
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
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

    def create_for_user(
        self,
        user_id: UUID,
        *,
        preferences: JsonObject | None = None,
    ) -> SettingsRecord:
        row = models.Settings(user_id=user_id, preferences=_json(preferences))
        self._session.add(row)
        flush_or_raise(self._session)
        return _settings_record(row)

    def upsert_preferences(self, user_id: UUID, preferences: JsonObject) -> SettingsRecord:
        existing = self._session.scalars(
            select(models.Settings).where(models.Settings.user_id == user_id)
        ).one_or_none()
        if existing is None:
            return self.create_for_user(user_id, preferences=preferences)
        existing.preferences = _json(preferences)
        existing.updated_at = _now()
        flush_or_raise(self._session)
        return _settings_record(existing)

    def update_preferences(self, user_id: UUID, preferences: JsonObject) -> SettingsRecord:
        row = self._session.scalars(
            select(models.Settings).where(models.Settings.user_id == user_id)
        ).one_or_none()
        if row is None:
            raise EntityNotFoundError("Settings not found")
        row.preferences = _json(preferences)
        row.updated_at = _now()
        flush_or_raise(self._session)
        return _settings_record(row)


class SqlAlchemyContentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        workspace_id: UUID,
        created_by_user_id: UUID | None,
        content_type: str = "IMAGE",
        title: str | None = None,
        payload: JsonObject | None = None,
    ) -> ContentRecord:
        row = models.Content(
            workspace_id=workspace_id,
            created_by_user_id=created_by_user_id,
            content_type=content_type,
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
        title: str | None = None,
        payload: JsonObject | None = None,
    ) -> ContentRecord:
        row = self._session.get(models.Content, content_id)
        if row is None or row.deleted_at is not None:
            raise EntityNotFoundError("Content not found")
        if title is not None:
            row.title = title
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
