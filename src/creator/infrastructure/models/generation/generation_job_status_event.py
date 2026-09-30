from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from creator.domain.generation import GenerationJobStatus
from creator.infrastructure import schema_models as _schema_models  # noqa: F401
from creator.infrastructure.db import Base

from ..enums import (
    generation_job_status_enum,
)
from ..types import timestamp_tz, uuid_pk


class GenerationJobStatusEvent(Base):
    __tablename__ = "generation_job_status_events"
    __table_args__ = (
        CheckConstraint(
            "previous_status IS NULL OR previous_status <> status",
            name="ck_generation_job_status_events_status_changed",
        ),
        Index(
            "ix_generation_job_status_events_job_occurred_at", "generation_job_id", "occurred_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    generation_job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_status: Mapped[GenerationJobStatus | None] = mapped_column(generation_job_status_enum)
    status: Mapped[GenerationJobStatus] = mapped_column(generation_job_status_enum, nullable=False)
    occurred_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
