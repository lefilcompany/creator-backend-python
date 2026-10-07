from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import models, schema_models
from creator.repositories.workspace import WorkspaceInviteRecord, WorkspaceInviteRepository


def _record(row: schema_models.WorkspaceInvite) -> WorkspaceInviteRecord:
    return WorkspaceInviteRecord(
        row.id,
        row.workspace_id,
        row.type,
        row.role,
        row.email,
        row.max_uses,
        row.uses_count,
        row.status,
        row.is_active,
        row.created_by,
        row.expires_at,
        row.last_used_at,
        row.revoked_at,
        row.created_at,
        row.updated_at,
        row.deleted_at,
    )


class SqlAlchemyWorkspaceInviteRepository(WorkspaceInviteRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _owned(self, user_id: UUID, invite_id: UUID) -> schema_models.WorkspaceInvite | None:
        return self._session.scalar(
            select(schema_models.WorkspaceInvite)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id
                == schema_models.WorkspaceInvite.workspace_id,
            )
            .where(
                schema_models.WorkspaceInvite.id == invite_id,
                models.WorkspaceMembership.user_id == user_id,
                schema_models.WorkspaceInvite.deleted_at.is_(None),
                models.WorkspaceMembership.deleted_at.is_(None),
            )
        )

    def list_for_user(
        self, *, user_id: UUID, workspace_id: UUID | None = None
    ) -> list[WorkspaceInviteRecord]:
        query = (
            select(schema_models.WorkspaceInvite)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id
                == schema_models.WorkspaceInvite.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.WorkspaceInvite.deleted_at.is_(None),
            )
        )
        if workspace_id is not None:
            query = query.where(schema_models.WorkspaceInvite.workspace_id == workspace_id)
        return [_record(x) for x in self._session.scalars(query).all()]

    def get_for_user(self, *, user_id: UUID, invite_id: UUID) -> WorkspaceInviteRecord | None:
        row = self._owned(user_id, invite_id)
        return _record(row) if row else None

    def add(
        self,
        *,
        workspace_id: UUID,
        created_by: UUID,
        type: str,
        role: str,
        email: str | None,
        max_uses: int | None,
        expires_at: datetime | None,
        token: str,
    ) -> WorkspaceInviteRecord:
        row = schema_models.WorkspaceInvite(
            workspace_id=workspace_id,
            created_by=created_by,
            type=type,
            role=role,
            email=email,
            max_uses=max_uses,
            expires_at=expires_at,
            token=token,
            status="pending",
        )
        self._session.add(row)
        self._session.flush()
        return _record(row)

    def update(self, *, invite_id: UUID, fields: dict[str, object]) -> WorkspaceInviteRecord:
        row = self._session.get(schema_models.WorkspaceInvite, invite_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Workspace invite not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _record(row)

    def soft_delete(self, *, invite_id: UUID) -> None:
        row = self._session.get(schema_models.WorkspaceInvite, invite_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Workspace invite not found")
        row.deleted_at = datetime.now(UTC)
        row.updated_at = row.deleted_at
        self._session.flush()
