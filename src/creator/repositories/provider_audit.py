from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ProviderWebhookEventRecord:
    id: UUID
    provider: str
    provider_event_id: str
    dedupe_key: str
    event_type: str
    account_id: str | None
    resource_type: str | None
    resource_id: str | None
    payload: dict[str, object]
    signature_verified: bool
    status: str
    attempts: int
    last_error: str | None
    received_at: datetime
    processed_at: datetime | None


class ProviderWebhookEventRepository(Protocol):
    def list(self) -> list[ProviderWebhookEventRecord]: ...
    def get(self, *, event_id: UUID) -> ProviderWebhookEventRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> ProviderWebhookEventRecord: ...
    def update(
        self, *, event_id: UUID, fields: dict[str, object]
    ) -> ProviderWebhookEventRecord: ...


@dataclass(frozen=True, slots=True)
class ProviderIdempotencyKeyRecord:
    id: UUID
    provider: str
    idempotency_key: str
    request_hash: str | None
    resource_type: str | None
    resource_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ProviderIdempotencyKeyRepository(Protocol):
    def list(self) -> list[ProviderIdempotencyKeyRecord]: ...
    def get(self, *, key_id: UUID) -> ProviderIdempotencyKeyRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> ProviderIdempotencyKeyRecord: ...
    def update(
        self, *, key_id: UUID, fields: dict[str, object]
    ) -> ProviderIdempotencyKeyRecord: ...
