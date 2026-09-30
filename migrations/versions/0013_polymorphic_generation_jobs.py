"""Add provider-neutral artifact contracts to Generation Jobs."""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0013_polymorphic_generation_jobs"
down_revision: str | Sequence[str] | None = "0012_pdf_column_alignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in ("COPY", "CAPTION"):
        op.execute(sa.text(f"ALTER TYPE generation_type ADD VALUE IF NOT EXISTS '{value}'"))
    op.add_column("generation_jobs", sa.Column("artifact_type", sa.Enum("IMAGE", "TEXT", "COPY", "CAPTION", name="generation_type", create_type=False), nullable=True))
    op.execute(sa.text("UPDATE generation_jobs j SET artifact_type = g.type FROM generations g WHERE g.id = j.generation_id AND g.workspace_id = j.workspace_id"))
    op.alter_column("generation_jobs", "artifact_type", nullable=False, server_default=sa.text("'IMAGE'"))
    op.add_column("generation_jobs", sa.Column("operation", sa.String(20), nullable=False, server_default="CREATE"))
    op.add_column("generation_jobs", sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"))
    op.add_column("generation_jobs", sa.Column("idempotency_key", sa.String(255)))
    op.add_column("generation_jobs", sa.Column("failure_policy", sa.String(20), nullable=False, server_default="FAIL"))
    op.add_column("generation_jobs", sa.Column("request_id", UUID(as_uuid=True)))
    for name, column in (("artifact_type", sa.Enum("IMAGE", "TEXT", "COPY", "CAPTION", name="generation_type", create_type=False)), ("version", sa.Integer()), ("correlation_id", sa.String(255)), ("sanitized_result", JSONB()), ("request_id", UUID(as_uuid=True))):
        op.add_column("generation_job_status_events", sa.Column(name, column, nullable=name in {"artifact_type", "correlation_id"}, server_default="1" if name == "version" else None))
    op.execute(sa.text("UPDATE generation_job_status_events SET artifact_type = 'IMAGE', correlation_id = generation_job_id::text WHERE artifact_type IS NULL"))
    op.alter_column("generation_job_status_events", "artifact_type", nullable=False)
    op.alter_column("generation_job_status_events", "correlation_id", nullable=False)


def downgrade() -> None:
    for table, columns in (("generation_job_status_events", ("request_id", "sanitized_result", "correlation_id", "version", "artifact_type")), ("generation_jobs", ("request_id", "failure_policy", "idempotency_key", "timeout_seconds", "operation", "artifact_type"))):
        for column in columns:
            op.drop_column(table, column)
