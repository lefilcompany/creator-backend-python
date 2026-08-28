from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    auth_subject: str
    email: str | None
    display_name: str | None
    global_role: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class UserRepository(Protocol):
    def add(
        self,
        *,
        auth_subject: str,
        email: str | None = None,
        display_name: str | None = None,
        global_role: str = "membro",
    ) -> UserRecord: ...

    def get_by_id(self, user_id: UUID, *, include_deleted: bool = False) -> UserRecord | None: ...

    def get_by_auth_subject(
        self, auth_subject: str, *, include_deleted: bool = False
    ) -> UserRecord | None: ...

    def update_profile(
        self,
        user_id: UUID,
        *,
        email: str | None = None,
        display_name: str | None = None,
    ) -> UserRecord: ...

    def soft_delete(self, user_id: UUID) -> None: ...
