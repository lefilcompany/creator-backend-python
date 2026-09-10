from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class WorkspaceMembershipRecord:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class CreatedWorkspaceRecord:
    workspace: WorkspaceRecord
    membership: WorkspaceMembershipRecord


class WorkspaceRepository(Protocol):
    def create_for_user(
        self,
        *,
        user_id: UUID,
        name: str,
        role: str = "owner",
    ) -> CreatedWorkspaceRecord: ...

    def soft_delete_for_user(self, *, user_id: UUID, workspace_id: UUID) -> WorkspaceRecord: ...
