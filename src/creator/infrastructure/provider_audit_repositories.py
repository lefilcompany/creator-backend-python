from __future__ import annotations

# mypy: disable-error-code=no-untyped-def
# mypy: disallow_untyped_calls=False
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import schema_models
from creator.repositories.provider_audit import (
    ProviderIdempotencyKeyRecord,
    ProviderIdempotencyKeyRepository,
    ProviderWebhookEventRecord,
    ProviderWebhookEventRepository,
)


class SqlAlchemyProviderWebhookEventRepository(ProviderWebhookEventRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return ProviderWebhookEventRecord(
            x.id,
            x.provider,
            x.provider_event_id,
            x.dedupe_key,
            x.event_type,
            x.account_id,
            x.resource_type,
            x.resource_id,
            x.payload,
            x.signature_verified,
            x.status,
            x.attempts,
            x.last_error,
            x.received_at,
            x.processed_at,
        )

    def list(self):
        return [
            self._r(x) for x in self.s.scalars(select(schema_models.ProviderWebhookEvent)).all()
        ]

    def get(self, *, event_id):
        x = self.s.get(schema_models.ProviderWebhookEvent, event_id)
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.ProviderWebhookEvent(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, event_id, fields):
        x = self.s.get(schema_models.ProviderWebhookEvent, event_id)
        if x is None:
            raise ValueError("Provider webhook event not found")
        for k, v in fields.items():
            setattr(x, k, v)
        self.s.flush()
        return self._r(x)


class SqlAlchemyProviderIdempotencyKeyRepository(ProviderIdempotencyKeyRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return ProviderIdempotencyKeyRecord(
            x.id,
            x.provider,
            x.idempotency_key,
            x.request_hash,
            x.resource_type,
            x.resource_id,
            x.status,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def list(self):
        return [
            self._r(x)
            for x in self.s.scalars(
                select(schema_models.ProviderIdempotencyKey).where(
                    schema_models.ProviderIdempotencyKey.deleted_at.is_(None)
                )
            ).all()
        ]

    def get(self, *, key_id):
        x = self.s.get(schema_models.ProviderIdempotencyKey, key_id)
        return self._r(x) if x and x.deleted_at is None else None

    def add(self, *, fields):
        x = schema_models.ProviderIdempotencyKey(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, key_id, fields):
        x = self.s.get(schema_models.ProviderIdempotencyKey, key_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Provider idempotency key not found")
        for k, v in fields.items():
            setattr(x, k, v)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)
