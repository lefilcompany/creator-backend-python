from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import schema_models
from creator.repositories.billing import BillingAccountRecord, PlanItemRecord, PlanRecord


def _plan(row: schema_models.Plan) -> PlanRecord:
    return PlanRecord(
        id=row.id,
        code=row.code,
        type=row.type,
        name=row.name,
        description=row.description,
        metadata=dict(row.metadata_json or {}),
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyPlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self) -> list[PlanRecord]:
        rows = self._session.scalars(
            select(schema_models.Plan)
            .where(schema_models.Plan.deleted_at.is_(None))
            .order_by(schema_models.Plan.created_at.desc())
        ).all()
        return [_plan(row) for row in rows]

    def get(self, *, plan_id: UUID) -> PlanRecord | None:
        row = self._session.scalars(
            select(schema_models.Plan).where(
                schema_models.Plan.id == plan_id,
                schema_models.Plan.deleted_at.is_(None),
            )
        ).one_or_none()
        return _plan(row) if row else None

    def add(
        self,
        *,
        code: str,
        type: str,
        name: str,
        description: str | None,
        metadata: dict[str, object],
        is_active: bool,
    ) -> PlanRecord:
        row = schema_models.Plan(
            code=code,
            type=type,
            name=name,
            description=description,
            metadata_json=metadata,
            is_active=is_active,
        )
        self._session.add(row)
        self._session.flush()
        return _plan(row)

    def update(self, *, plan_id: UUID, fields: dict[str, object]) -> PlanRecord:
        row = self._session.get(schema_models.Plan, plan_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Plan not found")
        mapping = {"metadata": "metadata_json"}
        for name, value in fields.items():
            setattr(row, mapping.get(name, name), value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _plan(row)

    def soft_delete(self, *, plan_id: UUID) -> None:
        row = self._session.get(schema_models.Plan, plan_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Plan not found")
        timestamp = datetime.now(UTC)
        row.deleted_at = timestamp
        row.updated_at = timestamp
        self._session.flush()


def _billing_account(row: schema_models.BillingAccount) -> BillingAccountRecord:
    return BillingAccountRecord(
        id=row.id,
        user_id=row.user_id,
        payer_type=row.payer_type,
        name=row.name,
        email=row.email,
        phone=row.phone,
        document=row.document,
        document_type=row.document_type,
        company_name=row.company_name,
        provider=row.provider,
        provider_customer_id=row.provider_customer_id,
        provider_customer_code=row.provider_customer_code,
        delinquent=row.delinquent,
        metadata=dict(row.metadata_json or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyBillingAccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, *, user_id: UUID) -> list[BillingAccountRecord]:
        rows = self._session.scalars(
            select(schema_models.BillingAccount)
            .where(
                schema_models.BillingAccount.user_id == user_id,
                schema_models.BillingAccount.deleted_at.is_(None),
            )
            .order_by(schema_models.BillingAccount.created_at.desc())
        ).all()
        return [_billing_account(row) for row in rows]

    def get_for_user(self, *, user_id: UUID, account_id: UUID) -> BillingAccountRecord | None:
        row = self._session.scalars(
            select(schema_models.BillingAccount).where(
                schema_models.BillingAccount.id == account_id,
                schema_models.BillingAccount.user_id == user_id,
                schema_models.BillingAccount.deleted_at.is_(None),
            )
        ).one_or_none()
        return _billing_account(row) if row else None

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
    ) -> BillingAccountRecord:
        row = schema_models.BillingAccount(
            user_id=user_id,
            payer_type=payer_type,
            name=name,
            email=email,
            phone=phone,
            document=document,
            document_type=document_type,
        )
        self._session.add(row)
        self._session.flush()
        return _billing_account(row)

    def update(
        self, *, user_id: UUID, account_id: UUID, fields: dict[str, object]
    ) -> BillingAccountRecord:
        row = self._session.scalars(
            select(schema_models.BillingAccount).where(
                schema_models.BillingAccount.id == account_id,
                schema_models.BillingAccount.user_id == user_id,
                schema_models.BillingAccount.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            raise ValueError("Billing account not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _billing_account(row)

    def soft_delete(self, *, user_id: UUID, account_id: UUID) -> None:
        row = self._session.scalars(
            select(schema_models.BillingAccount).where(
                schema_models.BillingAccount.id == account_id,
                schema_models.BillingAccount.user_id == user_id,
                schema_models.BillingAccount.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            raise ValueError("Billing account not found")
        timestamp = datetime.now(UTC)
        row.deleted_at = timestamp
        row.updated_at = timestamp
        self._session.flush()


def _plan_item(row: schema_models.PlanItem) -> PlanItemRecord:
    return PlanItemRecord(
        id=row.id,
        plan_id=row.plan_id,
        name=row.name,
        description=row.description,
        quantity=row.quantity,
        cycles=row.cycles,
        pricing_scheme_type=row.pricing_scheme_type,
        price_cents=row.price_cents,
        price_brackets=dict(row.price_brackets) if row.price_brackets else None,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyPlanItemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, *, plan_id: UUID | None = None) -> list[PlanItemRecord]:
        statement = select(schema_models.PlanItem).where(
            schema_models.PlanItem.deleted_at.is_(None)
        )
        if plan_id is not None:
            statement = statement.where(schema_models.PlanItem.plan_id == plan_id)
        rows = self._session.scalars(
            statement.order_by(schema_models.PlanItem.created_at.desc())
        ).all()
        return [_plan_item(row) for row in rows]

    def get(self, *, item_id: UUID) -> PlanItemRecord | None:
        row = self._session.scalars(
            select(schema_models.PlanItem).where(
                schema_models.PlanItem.id == item_id, schema_models.PlanItem.deleted_at.is_(None)
            )
        ).one_or_none()
        return _plan_item(row) if row else None

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
    ) -> PlanItemRecord:
        row = schema_models.PlanItem(
            plan_id=plan_id,
            name=name,
            description=description,
            quantity=quantity,
            cycles=cycles,
            pricing_scheme_type=pricing_scheme_type,
            price_cents=price_cents,
            price_brackets=price_brackets,
            status=status,
        )
        self._session.add(row)
        self._session.flush()
        return _plan_item(row)

    def update(self, *, item_id: UUID, fields: dict[str, object]) -> PlanItemRecord:
        row = self._session.get(schema_models.PlanItem, item_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Plan item not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _plan_item(row)

    def soft_delete(self, *, item_id: UUID) -> None:
        row = self._session.get(schema_models.PlanItem, item_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Plan item not found")
        timestamp = datetime.now(UTC)
        row.deleted_at = timestamp
        row.updated_at = timestamp
        self._session.flush()
