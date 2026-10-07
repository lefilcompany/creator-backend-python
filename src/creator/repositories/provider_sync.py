from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ProviderCustomerRecord:
    id: UUID
    billing_account_id: UUID
    provider: str
    provider_customer_id: str
    provider_code: str | None
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ProviderCustomerRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[ProviderCustomerRecord]: ...
    def get_for_user(self, *, user_id: UUID, record_id: UUID) -> ProviderCustomerRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> ProviderCustomerRecord: ...
    def update(self, *, record_id: UUID, fields: dict[str, object]) -> ProviderCustomerRecord: ...
    def soft_delete(self, *, record_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class ProviderSubscriptionRecord:
    id: UUID
    subscription_id: UUID
    provider: str
    provider_subscription_id: str
    provider_status: str | None
    payload: dict[str, object]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ProviderSubscriptionRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[ProviderSubscriptionRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, record_id: UUID
    ) -> ProviderSubscriptionRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> ProviderSubscriptionRecord: ...
    def update(
        self, *, record_id: UUID, fields: dict[str, object]
    ) -> ProviderSubscriptionRecord: ...
    def soft_delete(self, *, record_id: UUID) -> None: ...
