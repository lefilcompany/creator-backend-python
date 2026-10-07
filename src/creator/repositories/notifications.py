from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserDeviceRecord:
    id: UUID
    user_id: UUID
    platform: str
    fcm_token: str
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class UserDeviceRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[UserDeviceRecord]: ...
    def get_for_user(self, *, user_id: UUID, device_id: UUID) -> UserDeviceRecord | None: ...
    def add(self, *, user_id: UUID, platform: str, fcm_token: str) -> UserDeviceRecord: ...
    def update(
        self, *, user_id: UUID, device_id: UUID, fields: dict[str, object]
    ) -> UserDeviceRecord: ...
    def soft_delete(self, *, user_id: UUID, device_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class NotificationPreferenceRecord:
    id: UUID
    user_id: UUID
    type: str
    channel: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class NotificationPreferenceRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[NotificationPreferenceRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, preference_id: UUID
    ) -> NotificationPreferenceRecord | None: ...
    def add(
        self, *, user_id: UUID, type: str, channel: str, is_enabled: bool
    ) -> NotificationPreferenceRecord: ...
    def update(
        self, *, user_id: UUID, preference_id: UUID, fields: dict[str, object]
    ) -> NotificationPreferenceRecord: ...
    def soft_delete(self, *, user_id: UUID, preference_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    id: UUID
    workspace_id: UUID
    type: str
    title: str
    body: str
    payload: dict[str, object]
    resource_type: str | None
    resource_id: UUID | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class NotificationRepository(Protocol):
    def list_for_user(
        self, *, user_id: UUID, workspace_id: UUID | None = None
    ) -> list[NotificationRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, notification_id: UUID
    ) -> NotificationRecord | None: ...
    def add(
        self,
        *,
        workspace_id: UUID,
        created_by: UUID,
        type: str,
        title: str,
        body: str,
        payload: dict[str, object],
        resource_type: str | None,
        resource_id: UUID | None,
    ) -> NotificationRecord: ...
    def update(self, *, notification_id: UUID, fields: dict[str, object]) -> NotificationRecord: ...
    def soft_delete(self, *, notification_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class NotificationRecipientRecord:
    id: UUID
    notification_id: UUID
    user_id: UUID
    workspace_member_id: UUID | None
    channel: str
    status: str
    attempts: int
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class NotificationRecipientRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[NotificationRecipientRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, recipient_id: UUID
    ) -> NotificationRecipientRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> NotificationRecipientRecord: ...
    def update(
        self, *, recipient_id: UUID, fields: dict[str, object]
    ) -> NotificationRecipientRecord: ...
    def soft_delete(self, *, recipient_id: UUID) -> None: ...
