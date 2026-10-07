"""Add Workspace- and Brand-scoped knowledge documents and chunks."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0017_brand_knowledge"
down_revision: str | Sequence[str] | None = "0016_credit_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brand_knowledge_documents",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source", sa.String(2000), nullable=False),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", "brand_id", name="uq_bk_documents_scope"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id", "workspace_id"], ["brands.id", "brands.workspace_id"], ondelete="CASCADE", name="fk_bk_documents_brand_workspace"),
        sa.CheckConstraint("deleted_at IS NULL OR deleted_at >= created_at", name="ck_bk_documents_deleted_after_created"),
    )
    op.create_index("ix_bk_documents_workspace_brand", "brand_knowledge_documents", ["workspace_id", "brand_id", "deleted_at", "created_at"])
    op.create_table(
        "brand_knowledge_chunks",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", JSONB, nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id", "workspace_id", "brand_id"], ["brand_knowledge_documents.id", "brand_knowledge_documents.workspace_id", "brand_knowledge_documents.brand_id"], ondelete="CASCADE", name="fk_bk_chunks_document_scope"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_bk_chunks_document_index"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_bk_chunks_index_nonnegative"),
        sa.CheckConstraint("jsonb_typeof(embedding) = 'array'", name="ck_bk_chunks_embedding_array"),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name="ck_bk_chunks_metadata_object"),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 100000", name="ck_bk_chunks_content_length"),
    )
    op.create_index("ix_bk_chunks_workspace_brand", "brand_knowledge_chunks", ["workspace_id", "brand_id", "document_id", "chunk_index"])
    op.create_index("ix_bk_chunks_document_index", "brand_knowledge_chunks", ["document_id", "chunk_index"])


def downgrade() -> None:
    op.drop_index("ix_bk_chunks_document_index", table_name="brand_knowledge_chunks")
    op.drop_index("ix_bk_chunks_workspace_brand", table_name="brand_knowledge_chunks")
    op.drop_table("brand_knowledge_chunks")
    op.drop_index("ix_bk_documents_workspace_brand", table_name="brand_knowledge_documents")
    op.drop_table("brand_knowledge_documents")
