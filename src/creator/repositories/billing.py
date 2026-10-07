from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PlanRecord:
    id: UUID
    code: str
    type: str
    name: str
    description: str | None
    metadata: dict[str, object]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class PlanRepository(Protocol):
    def list(self) -> list[PlanRecord]: ...
    def get(self, *, plan_id: UUID) -> PlanRecord | None: ...
    def add(
        self,
        *,
        code: str,
        type: str,
        name: str,
        description: str | None,
        metadata: dict[str, object],
        is_active: bool,
    ) -> PlanRecord: ...
    def update(self, *, plan_id: UUID, fields: dict[str, object]) -> PlanRecord: ...
    def soft_delete(self, *, plan_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class BillingAccountRecord:
    id: UUID
    user_id: UUID
    payer_type: str
    name: str
    email: str
    phone: str | None
    document: str | None
    document_type: str | None
    company_name: str | None
    provider: str | None
    provider_customer_id: str | None
    provider_customer_code: str | None
    delinquent: bool
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class BillingAccountRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[BillingAccountRecord]: ...
    def get_for_user(self, *, user_id: UUID, account_id: UUID) -> BillingAccountRecord | None: ...
    def add(
        self,
        *,
        user_id: UUID,
        payer_type: str,
        name: str,
        email: str,
        phone: str | None,
        document: str | None,
        document_type: str | None,
    ) -> BillingAccountRecord: ...
    def update(
        self, *, user_id: UUID, account_id: UUID, fields: dict[str, object]
    ) -> BillingAccountRecord: ...
    def soft_delete(self, *, user_id: UUID, account_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class PlanItemRecord:
    id: UUID
    plan_id: UUID
    name: str
    description: str | None
    quantity: int
    cycles: int | None
    pricing_scheme_type: str | None
    price_cents: int
    price_brackets: dict[str, object] | None
    status: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class PlanItemRepository(Protocol):
    def list(self, *, plan_id: UUID | None = None) -> list[PlanItemRecord]: ...
    def get(self, *, item_id: UUID) -> PlanItemRecord | None: ...
    def add(
        self,
        *,
        plan_id: UUID,
        name: str,
        description: str | None,
        quantity: int,
        cycles: int | None,
        pricing_scheme_type: str | None,
        price_cents: int,
        price_brackets: dict[str, object] | None,
        status: str | None,
    ) -> PlanItemRecord: ...
    def update(self, *, item_id: UUID, fields: dict[str, object]) -> PlanItemRecord: ...
    def soft_delete(self, *, item_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class SubscriptionRecord:
    id: UUID
    billing_account_id: UUID
    workspace_id: UUID
    plan_id: UUID
    status: str
    payment_method: str | None
    billing_day: int | None
    start_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class SubscriptionRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[SubscriptionRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, subscription_id: UUID
    ) -> SubscriptionRecord | None: ...
    def add(
        self,
        *,
        billing_account_id: UUID,
        workspace_id: UUID,
        plan_id: UUID,
        payment_method: str | None,
        billing_day: int | None,
        start_at: datetime | None,
    ) -> SubscriptionRecord: ...
    def update(self, *, subscription_id: UUID, fields: dict[str, object]) -> SubscriptionRecord: ...
    def soft_delete(self, *, subscription_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class InvoiceRecord:
    id: UUID
    billing_account_id: UUID
    subscription_id: UUID | None
    amount_cents: int
    currency: str
    status: str
    billing_at: datetime | None
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class InvoiceRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[InvoiceRecord]: ...
    def get_for_user(self, *, user_id: UUID, invoice_id: UUID) -> InvoiceRecord | None: ...
    def add(
        self,
        *,
        billing_account_id: UUID,
        subscription_id: UUID | None,
        amount_cents: int,
        currency: str,
        billing_at: datetime | None,
        due_at: datetime | None,
    ) -> InvoiceRecord: ...
    def update(self, *, invoice_id: UUID, fields: dict[str, object]) -> InvoiceRecord: ...
    def soft_delete(self, *, invoice_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class ChargeRecord:
    id: UUID
    billing_account_id: UUID
    invoice_id: UUID | None
    amount_cents: int
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ChargeRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[ChargeRecord]: ...
    def get_for_user(self, *, user_id: UUID, charge_id: UUID) -> ChargeRecord | None: ...
    def add(
        self, *, billing_account_id: UUID, invoice_id: UUID | None, amount_cents: int, currency: str
    ) -> ChargeRecord: ...
    def update(self, *, charge_id: UUID, fields: dict[str, object]) -> ChargeRecord: ...
    def soft_delete(self, *, charge_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class BillingAddressRecord:
    id: UUID
    billing_account_id: UUID
    street: str | None
    number: str | None
    complement: str | None
    neighborhood: str | None
    zip_code: str | None
    city: str | None
    state: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class BillingAddressRepository(Protocol):
    def list_for_user(
        self, *, user_id: UUID, account_id: UUID | None = None
    ) -> list[BillingAddressRecord]: ...
    def get_for_user(self, *, user_id: UUID, address_id: UUID) -> BillingAddressRecord | None: ...
    def add(
        self, *, billing_account_id: UUID, fields: dict[str, object]
    ) -> BillingAddressRecord: ...
    def update(self, *, address_id: UUID, fields: dict[str, object]) -> BillingAddressRecord: ...
    def soft_delete(self, *, address_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class BillingPaymentMethodRecord:
    id: UUID
    billing_account_id: UUID
    holder_name: str | None
    holder_document: str | None
    card_brand: str | None
    card_last_four: str | None
    exp_month: int | None
    exp_year: int | None
    card_type: str | None
    card_status: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class BillingPaymentMethodRepository(Protocol):
    def list_for_user(
        self, *, user_id: UUID, account_id: UUID | None = None
    ) -> list[BillingPaymentMethodRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, method_id: UUID
    ) -> BillingPaymentMethodRecord | None: ...
    def add(
        self, *, billing_account_id: UUID, fields: dict[str, object]
    ) -> BillingPaymentMethodRecord: ...
    def update(
        self, *, method_id: UUID, fields: dict[str, object]
    ) -> BillingPaymentMethodRecord: ...
    def soft_delete(self, *, method_id: UUID) -> None: ...
