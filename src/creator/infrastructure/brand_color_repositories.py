from __future__ import annotations

# mypy: disable-error-code=no-untyped-def
# mypy: disallow_untyped_calls=False
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import models, schema_models
from creator.repositories.brand_color import BrandColorRecord, BrandColorRepository


class SqlAlchemyBrandColorRepository(BrandColorRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return BrandColorRecord(
            x.id,
            x.brand_id,
            x.workspace_id,
            x.created_by,
            x.order,
            x.color_name,
            x.hex_code,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def _q(self, uid):
        return (
            select(schema_models.BrandColor)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == schema_models.BrandColor.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == uid,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.BrandColor.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id, brand_id=None):
        q = self._q(user_id)
        if brand_id is not None:
            q = q.where(schema_models.BrandColor.brand_id == brand_id)
        return [self._r(x) for x in self.s.scalars(q).all()]

    def get_for_user(self, *, user_id, color_id):
        x = self.s.scalar(self._q(user_id).where(schema_models.BrandColor.id == color_id))
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.BrandColor(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, color_id, fields):
        x = self.s.get(schema_models.BrandColor, color_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Brand color not found")
        for k, v in fields.items():
            setattr(x, k, v)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, color_id):
        x = self.s.get(schema_models.BrandColor, color_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Brand color not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()
