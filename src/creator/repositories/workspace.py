from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

<<<<<<< HEAD
=======
from creator.repositories.common import Page, PageRequest

>>>>>>> 3f6417bb10585844ad5772267618c4bc9bd474a1

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


<<<<<<< HEAD
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
=======
class WorkspaceRepository(Protocol):
    def add(self, *, name: str, owner_user_id: UUID) -> WorkspaceRecord: ...

    def get_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        include_deleted: bool = False,
    ) -> WorkspaceRecord | None: ...

    def list_for_user(
        self,
        *,
        user_id: UUID,
        page: PageRequest | None = None,
    ) -> Page[WorkspaceRecord]: ...

    def update(self, *, user_id: UUID, workspace_id: UUID, name: str) -> WorkspaceRecord: ...

    def soft_delete(self, *, user_id: UUID, workspace_id: UUID) -> None: ...

    def user_has_workspace_role(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        minimum_role: str = "viewer",
    ) -> bool: ...
>>>>>>> 3f6417bb10585844ad5772267618c4bc9bd474a1
