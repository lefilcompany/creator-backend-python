from __future__ import annotations

# mypy: disable-error-code=no-untyped-def
# mypy: disallow_untyped_calls=False
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import schema_models
from creator.repositories.provider_sync import (
    ProviderCustomerRecord,
    ProviderCustomerRepository,
    ProviderSubscriptionRecord,
    ProviderSubscriptionRepository,
)


class SqlAlchemyProviderCustomerRepository(ProviderCustomerRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return ProviderCustomerRecord(
            x.id,
            x.billing_account_id,
            x.provider,
            x.provider_customer_id,
            x.provider_code,
            x.metadata_json,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def _owned(self, uid, rid):
        return self.s.scalar(
            select(schema_models.ProviderCustomer)
            .join(schema_models.BillingAccount)
            .where(
                schema_models.ProviderCustomer.id == rid,
                schema_models.BillingAccount.user_id == uid,
                schema_models.ProviderCustomer.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id):
        return [
            self._r(x)
            for x in self.s.scalars(
                select(schema_models.ProviderCustomer)
                .join(schema_models.BillingAccount)
                .where(
                    schema_models.BillingAccount.user_id == user_id,
                    schema_models.ProviderCustomer.deleted_at.is_(None),
                )
            ).all()
        ]

    def get_for_user(self, *, user_id, record_id):
        x = self._owned(user_id, record_id)
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.ProviderCustomer(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, record_id, fields):
        x = self.s.get(schema_models.ProviderCustomer, record_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Provider customer not found")
        for k, v in fields.items():
            setattr(x, k, v)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, record_id):
        x = self.s.get(schema_models.ProviderCustomer, record_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Provider customer not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()


class SqlAlchemyProviderSubscriptionRepository(ProviderSubscriptionRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return ProviderSubscriptionRecord(
            x.id,
            x.subscription_id,
            x.provider,
            x.provider_subscription_id,
            x.provider_status,
            x.payload,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def _owned(self, uid, rid):
        return self.s.scalar(
            select(schema_models.ProviderSubscription)
            .join(schema_models.Subscription)
            .join(schema_models.BillingAccount)
            .where(
                schema_models.ProviderSubscription.id == rid,
                schema_models.BillingAccount.user_id == uid,
                schema_models.ProviderSubscription.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id):
        return [
            self._r(x)
            for x in self.s.scalars(
                select(schema_models.ProviderSubscription)
                .join(schema_models.Subscription)
                .join(schema_models.BillingAccount)
                .where(
                    schema_models.BillingAccount.user_id == user_id,
                    schema_models.ProviderSubscription.deleted_at.is_(None),
                )
            ).all()
        ]

    def get_for_user(self, *, user_id, record_id):
        x = self._owned(user_id, record_id)
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.ProviderSubscription(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, record_id, fields):
        x = self.s.get(schema_models.ProviderSubscription, record_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Provider subscription not found")
        for k, v in fields.items():
            setattr(x, k, v)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, record_id):
        x = self.s.get(schema_models.ProviderSubscription, record_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Provider subscription not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()
