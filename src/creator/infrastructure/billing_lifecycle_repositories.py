from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import schema_models
from creator.repositories.billing import (
    ChargeRecord,
    ChargeRepository,
    InvoiceRecord,
    InvoiceRepository,
    SubscriptionRecord,
    SubscriptionRepository,
)


def _subscription(row: schema_models.Subscription) -> SubscriptionRecord:
    return SubscriptionRecord(
        row.id,
        row.billing_account_id,
        row.workspace_id,
        row.plan_id,
        row.status,
        row.payment_method,
        row.billing_day,
        row.start_at,
        row.created_at,
        row.updated_at,
        row.deleted_at,
    )


class SqlAlchemySubscriptionRepository(SubscriptionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _owned(self, user_id: UUID, subscription_id: UUID) -> schema_models.Subscription | None:
        return self._session.scalar(
            select(schema_models.Subscription)
            .join(
                schema_models.BillingAccount,
                schema_models.BillingAccount.id == schema_models.Subscription.billing_account_id,
            )
            .where(
                schema_models.Subscription.id == subscription_id,
                schema_models.BillingAccount.user_id == user_id,
                schema_models.Subscription.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id: UUID) -> list[SubscriptionRecord]:
        rows = self._session.scalars(
            select(schema_models.Subscription)
            .join(
                schema_models.BillingAccount,
                schema_models.BillingAccount.id == schema_models.Subscription.billing_account_id,
            )
            .where(
                schema_models.BillingAccount.user_id == user_id,
                schema_models.Subscription.deleted_at.is_(None),
            )
        ).all()
        return [_subscription(row) for row in rows]

    def get_for_user(self, *, user_id: UUID, subscription_id: UUID) -> SubscriptionRecord | None:
        row = self._owned(user_id, subscription_id)
        return _subscription(row) if row else None

    def add(
        self,
        *,
        billing_account_id: UUID,
        workspace_id: UUID,
        plan_id: UUID,
        payment_method: str | None,
        billing_day: int | None,
        start_at: datetime | None,
    ) -> SubscriptionRecord:
        row = schema_models.Subscription(
            billing_account_id=billing_account_id,
            workspace_id=workspace_id,
            plan_id=plan_id,
            status="pending",
            payment_method=payment_method,
            billing_day=billing_day,
            start_at=start_at,
        )
        self._session.add(row)
        self._session.flush()
        return _subscription(row)

    def update(self, *, subscription_id: UUID, fields: dict[str, object]) -> SubscriptionRecord:
        row = self._session.get(schema_models.Subscription, subscription_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Subscription not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _subscription(row)

    def soft_delete(self, *, subscription_id: UUID) -> None:
        row = self._session.get(schema_models.Subscription, subscription_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Subscription not found")
        row.deleted_at = datetime.now(UTC)
        row.updated_at = row.deleted_at
        self._session.flush()


def _invoice(row: schema_models.Invoice) -> InvoiceRecord:
    return InvoiceRecord(
        row.id,
        row.billing_account_id,
        row.subscription_id,
        row.amount_cents,
        row.currency,
        row.status,
        row.billing_at,
        row.due_at,
        row.created_at,
        row.updated_at,
        row.deleted_at,
    )


class SqlAlchemyInvoiceRepository(InvoiceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _owned(self, user_id: UUID, invoice_id: UUID) -> schema_models.Invoice | None:
        return self._session.scalar(
            select(schema_models.Invoice)
            .join(
                schema_models.BillingAccount,
                schema_models.BillingAccount.id == schema_models.Invoice.billing_account_id,
            )
            .where(
                schema_models.Invoice.id == invoice_id,
                schema_models.BillingAccount.user_id == user_id,
                schema_models.Invoice.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id: UUID) -> list[InvoiceRecord]:
        rows = self._session.scalars(
            select(schema_models.Invoice)
            .join(
                schema_models.BillingAccount,
                schema_models.BillingAccount.id == schema_models.Invoice.billing_account_id,
            )
            .where(
                schema_models.BillingAccount.user_id == user_id,
                schema_models.Invoice.deleted_at.is_(None),
            )
        ).all()
        return [_invoice(row) for row in rows]

    def get_for_user(self, *, user_id: UUID, invoice_id: UUID) -> InvoiceRecord | None:
        row = self._owned(user_id, invoice_id)
        return _invoice(row) if row else None

    def add(
        self,
        *,
        billing_account_id: UUID,
        subscription_id: UUID | None,
        amount_cents: int,
        currency: str,
        billing_at: datetime | None,
        due_at: datetime | None,
    ) -> InvoiceRecord:
        row = schema_models.Invoice(
            billing_account_id=billing_account_id,
            subscription_id=subscription_id,
            amount_cents=amount_cents,
            currency=currency,
            status="pending",
            billing_at=billing_at,
            due_at=due_at,
        )
        self._session.add(row)
        self._session.flush()
        return _invoice(row)

    def update(self, *, invoice_id: UUID, fields: dict[str, object]) -> InvoiceRecord:
        row = self._session.get(schema_models.Invoice, invoice_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Invoice not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _invoice(row)

    def soft_delete(self, *, invoice_id: UUID) -> None:
        row = self._session.get(schema_models.Invoice, invoice_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Invoice not found")
        row.deleted_at = datetime.now(UTC)
        row.updated_at = row.deleted_at
        self._session.flush()


def _charge(row: schema_models.Charge) -> ChargeRecord:
    return ChargeRecord(
        row.id,
        row.billing_account_id,
        row.invoice_id,
        row.amount_cents,
        row.currency,
        row.status,
        row.created_at,
        row.updated_at,
        row.deleted_at,
    )


class SqlAlchemyChargeRepository(ChargeRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _owned(self, user_id: UUID, charge_id: UUID) -> schema_models.Charge | None:
        return self._session.scalar(
            select(schema_models.Charge)
            .join(
                schema_models.BillingAccount,
                schema_models.BillingAccount.id == schema_models.Charge.billing_account_id,
            )
            .where(
                schema_models.Charge.id == charge_id,
                schema_models.BillingAccount.user_id == user_id,
                schema_models.Charge.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id: UUID) -> list[ChargeRecord]:
        rows = self._session.scalars(
            select(schema_models.Charge)
            .join(
                schema_models.BillingAccount,
                schema_models.BillingAccount.id == schema_models.Charge.billing_account_id,
            )
            .where(
                schema_models.BillingAccount.user_id == user_id,
                schema_models.Charge.deleted_at.is_(None),
            )
        ).all()
        return [_charge(row) for row in rows]

    def get_for_user(self, *, user_id: UUID, charge_id: UUID) -> ChargeRecord | None:
        row = self._owned(user_id, charge_id)
        return _charge(row) if row else None

    def add(
        self, *, billing_account_id: UUID, invoice_id: UUID | None, amount_cents: int, currency: str
    ) -> ChargeRecord:
        row = schema_models.Charge(
            billing_account_id=billing_account_id,
            invoice_id=invoice_id,
            amount_cents=amount_cents,
            currency=currency,
            status="pending",
        )
        self._session.add(row)
        self._session.flush()
        return _charge(row)

    def update(self, *, charge_id: UUID, fields: dict[str, object]) -> ChargeRecord:
        row = self._session.get(schema_models.Charge, charge_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Charge not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _charge(row)

    def soft_delete(self, *, charge_id: UUID) -> None:
        row = self._session.get(schema_models.Charge, charge_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Charge not found")
        row.deleted_at = datetime.now(UTC)
        row.updated_at = row.deleted_at
        self._session.flush()
