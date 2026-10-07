"""Workspace- and Brand-scoped knowledge sources and chunks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from creator.infrastructure.db import Base

from .types import timestamp_tz, uuid_pk


class BrandKnowledgeDocument(Base):
    __tablename__ = "brand_knowledge_documents"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", "brand_id", name="uq_bk_documents_scope"),
        ForeignKeyConstraint(
            ["brand_id", "workspace_id"],
            ["brands.id", "brands.workspace_id"],
            ondelete="CASCADE",
            name="fk_bk_documents_brand_workspace",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_bk_documents_deleted_after_created",
        ),
        Index(
            "ix_bk_documents_workspace_brand",
            "workspace_id",
            "brand_id",
            "deleted_at",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(2000), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)


class BrandKnowledgeChunk(Base):
    __tablename__ = "brand_knowledge_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "workspace_id", "brand_id"],
            [
                "brand_knowledge_documents.id",
                "brand_knowledge_documents.workspace_id",
                "brand_knowledge_documents.brand_id",
            ],
            ondelete="CASCADE",
            name="fk_bk_chunks_document_scope",
        ),
        UniqueConstraint("document_id", "chunk_index", name="uq_bk_chunks_document_index"),
        CheckConstraint("chunk_index >= 0", name="ck_bk_chunks_index_nonnegative"),
        CheckConstraint("jsonb_typeof(embedding) = 'array'", name="ck_bk_chunks_embedding_array"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="ck_bk_chunks_metadata_object"),
        CheckConstraint("length(content) BETWEEN 1 AND 100000", name="ck_bk_chunks_content_length"),
        Index(
            "ix_bk_chunks_workspace_brand", "workspace_id", "brand_id", "document_id", "chunk_index"
        ),
        Index("ix_bk_chunks_document_index", "document_id", "chunk_index"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now()
    )
