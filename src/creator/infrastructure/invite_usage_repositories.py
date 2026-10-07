from __future__ import annotations

from datetime import UTC, datetime

# mypy: disable-error-code=no-untyped-def
# mypy: disallow_untyped_calls=False
from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import models, schema_models
from creator.repositories.invite_usage import (
    WorkspaceInviteUsageRecord,
    WorkspaceInviteUsageRepository,
)


class SqlAlchemyWorkspaceInviteUsageRepository(WorkspaceInviteUsageRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return WorkspaceInviteUsageRecord(
            x.id,
            x.invite_id,
            x.user_id,
            x.workspace_id,
            x.member_id,
            x.used_at,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def _owned(self, uid, usage_id):
        return self.s.scalar(
            select(schema_models.WorkspaceInviteUsage)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id
                == schema_models.WorkspaceInviteUsage.workspace_id,
            )
            .where(
                schema_models.WorkspaceInviteUsage.id == usage_id,
                models.WorkspaceMembership.user_id == uid,
                schema_models.WorkspaceInviteUsage.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id, workspace_id=None):
        q = (
            select(schema_models.WorkspaceInviteUsage)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id
                == schema_models.WorkspaceInviteUsage.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                schema_models.WorkspaceInviteUsage.deleted_at.is_(None),
            )
        )
        if workspace_id is not None:
            q = q.where(schema_models.WorkspaceInviteUsage.workspace_id == workspace_id)
        return [self._r(x) for x in self.s.scalars(q).all()]

    def get_for_user(self, *, user_id, usage_id):
        x = self._owned(user_id, usage_id)
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.WorkspaceInviteUsage(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, usage_id, fields):
        x = self.s.get(schema_models.WorkspaceInviteUsage, usage_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Workspace invite usage not found")
        for key, value in fields.items():
            setattr(x, key, value)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, usage_id):
        x = self.s.get(schema_models.WorkspaceInviteUsage, usage_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Workspace invite usage not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()
