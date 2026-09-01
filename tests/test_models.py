from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from creator.domain.generation import GenerationJobStatus
from creator.infrastructure.db import Base
from creator.infrastructure.models import (
    Content,
    Generation,
    GenerationJob,
    GenerationJobStatusEvent,
    Image,
    Settings,
    User,
    Workspace,
    WorkspaceMembership,
)


def constraint_names(table_name: str, constraint_type: type[object]) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name or ""
        for constraint in table.constraints
        if isinstance(constraint, constraint_type)
    }


def index_names(table_name: str) -> set[str]:
    return {index.name or "" for index in Base.metadata.tables[table_name].indexes}


def test_initial_relational_model_tables_are_registered() -> None:
    assert {
        User.__tablename__,
        Settings.__tablename__,
        Workspace.__tablename__,
        WorkspaceMembership.__tablename__,
        Content.__tablename__,
        Generation.__tablename__,
        GenerationJob.__tablename__,
        GenerationJobStatusEvent.__tablename__,
        Image.__tablename__,
    } <= set(Base.metadata.tables)


def test_generation_job_status_enum_reuses_domain_values() -> None:
    status_type = Base.metadata.tables["generation_jobs"].c.status.type

    assert status_type.enums == [status.value for status in GenerationJobStatus]


def test_settings_and_image_uniqueness_constraints_are_explicit() -> None:
    assert "uq_users_external_id" in constraint_names("users", UniqueConstraint)
    assert "uq_settings_user_id" in constraint_names("settings", UniqueConstraint)
    assert "uq_images_generation_id" in constraint_names("images", UniqueConstraint)
    assert "uq_images_storage_path" in constraint_names("images", UniqueConstraint)
    assert "uq_images_active_content_version" in index_names("images")

    version_index = next(
        index
        for index in Base.metadata.tables["images"].indexes
        if index.name == "uq_images_active_content_version"
    )

    assert version_index.unique is True
    assert str(version_index.dialect_options["postgresql"]["where"]) == "deleted_at IS NULL"


def test_history_and_queue_indexes_are_explicit() -> None:
    assert "ix_generation_job_status_events_job_occurred_at" in index_names(
        "generation_job_status_events"
    )
    assert "ix_generation_jobs_status_created_at" in index_names("generation_jobs")
    assert "ix_generation_jobs_workspace_status_created_at" in index_names("generation_jobs")
    assert "uq_generation_jobs_external_id" in index_names("generation_jobs")


def test_required_image_columns_and_checks_are_present() -> None:
    image_table = Base.metadata.tables["images"]

    assert {
        "storage_path",
        "public_url",
        "mime_type",
        "width",
        "height",
        "model",
        "prompt",
        "created_at",
    } <= set(image_table.c.keys())
    assert "ck_images_version_number_positive" in constraint_names("images", CheckConstraint)
    assert "ck_images_mime_type_supported" in constraint_names("images", CheckConstraint)
    assert "ck_images_width_positive" in constraint_names("images", CheckConstraint)
    assert "ck_images_height_positive" in constraint_names("images", CheckConstraint)


def test_workspace_integrity_uses_composite_foreign_keys() -> None:
    generation_fks = constraint_names("generations", ForeignKeyConstraint)
    image_fks = constraint_names("images", ForeignKeyConstraint)
    job_fks = constraint_names("generation_jobs", ForeignKeyConstraint)

    assert "fk_generations_content_workspace" in generation_fks
    assert "fk_images_content_workspace" in image_fks
    assert "fk_images_generation_workspace_content" in image_fks
    assert "fk_generation_jobs_generation_workspace" in job_fks


def test_soft_delete_columns_are_on_recoverable_business_tables() -> None:
    for table_name in [
        "users",
        "workspaces",
        "workspace_memberships",
        "contents",
        "generations",
        "generation_jobs",
        "images",
    ]:
        assert "deleted_at" in Base.metadata.tables[table_name].c

    assert "deleted_at" not in Base.metadata.tables["generation_job_status_events"].c
