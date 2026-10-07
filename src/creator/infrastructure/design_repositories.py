from __future__ import annotations

# mypy: disable-error-code=no-untyped-def
# mypy: disallow_untyped_calls=False
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import schema_models
from creator.repositories.design import DesignStructureRecord, DesignStructureRepository


class SqlAlchemyDesignStructureRepository(DesignStructureRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return DesignStructureRecord(
            x.id, x.post_structure_id, x.created_at, x.updated_at, x.deleted_at
        )

    def _owned(self, uid, did):
        return self.s.scalar(
            select(schema_models.DesignStructure)
            .join(schema_models.PostStructure)
            .where(
                schema_models.DesignStructure.id == did,
                schema_models.PostStructure.created_by == uid,
                schema_models.DesignStructure.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id):
        return [
            self._r(x)
            for x in self.s.scalars(
                select(schema_models.DesignStructure)
                .join(schema_models.PostStructure)
                .where(
                    schema_models.PostStructure.created_by == user_id,
                    schema_models.DesignStructure.deleted_at.is_(None),
                )
            ).all()
        ]

    def get_for_user(self, *, user_id, design_id):
        x = self._owned(user_id, design_id)
        return self._r(x) if x else None

    def add(self, *, post_structure_id):
        x = schema_models.DesignStructure(post_structure_id=post_structure_id)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, design_id, fields):
        x = self.s.get(schema_models.DesignStructure, design_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Design structure not found")
        for key, value in fields.items():
            setattr(x, key, value)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, design_id):
        x = self.s.get(schema_models.DesignStructure, design_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Design structure not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()
