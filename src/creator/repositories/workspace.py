from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from creator.repositories.common import Page, PageRequest


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


@dataclass(frozen=True, slots=True)
class WorkspaceInviteRecord:
    id: UUID
    workspace_id: UUID
    type: str
    role: str
    email: str | None
    max_uses: int | None
    uses_count: int
    status: str
    is_active: bool
    created_by: UUID
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class WorkspaceInviteRepository(Protocol):
    def list_for_user(
        self, *, user_id: UUID, workspace_id: UUID | None = None
    ) -> list[WorkspaceInviteRecord]: ...
    def get_for_user(self, *, user_id: UUID, invite_id: UUID) -> WorkspaceInviteRecord | None: ...
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
    ) -> WorkspaceInviteRecord: ...
    def update(self, *, invite_id: UUID, fields: dict[str, object]) -> WorkspaceInviteRecord: ...
    def soft_delete(self, *, invite_id: UUID) -> None: ...


class WorkspaceRepository(Protocol):
    def add(self, *, name: str, owner_user_id: UUID) -> WorkspaceRecord: ...

    def create_for_user(
        self,
        *,
        user_id: UUID,
        name: str,
        role: str = "owner",
    ) -> CreatedWorkspaceRecord: ...

    def soft_delete_for_user(self, *, user_id: UUID, workspace_id: UUID) -> WorkspaceRecord: ...

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
