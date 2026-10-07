from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WorkspaceInviteUsageRecord:
    id: UUID
    invite_id: UUID
    user_id: UUID
    workspace_id: UUID
    member_id: UUID | None
    used_at: datetime
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class WorkspaceInviteUsageRepository(Protocol):
    def list_for_user(
        self, *, user_id: UUID, workspace_id: UUID | None = None
    ) -> list[WorkspaceInviteUsageRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, usage_id: UUID
    ) -> WorkspaceInviteUsageRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> WorkspaceInviteUsageRecord: ...
    def update(
        self, *, usage_id: UUID, fields: dict[str, object]
    ) -> WorkspaceInviteUsageRecord: ...
    def soft_delete(self, *, usage_id: UUID) -> None: ...
