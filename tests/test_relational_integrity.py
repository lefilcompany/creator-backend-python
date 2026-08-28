from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "users",
    "settings",
    "workspaces",
    "workspace_memberships",
    "contents",
    "generations",
    "generation_jobs",
    "generation_job_status_events",
    "images",
}


def test_database_url() -> str:
    url = os.getenv("CREATOR_TEST_DATABASE_URL")
    if not url:
        pytest.skip("CREATOR_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(url)
    database_name = parsed_url.database or ""
    if "test" not in database_name.lower():
        pytest.skip("CREATOR_TEST_DATABASE_URL must point to a database with 'test' in its name")

    return url


def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def reset_public_schema(engine: Engine) -> None:
    with engine.connect() as connection:
        autocommit_connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        autocommit_connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        autocommit_connection.execute(text("CREATE SCHEMA public"))


@pytest.fixture()
def migrated_engine() -> Any:
    database_url = test_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    config = alembic_config(database_url)
    reset_public_schema(engine)
    command.upgrade(config, "head")

    try:
        yield engine
    finally:
        command.downgrade(config, "base")
        reset_public_schema(engine)
        engine.dispose()


def seed_user_workspace_content(connection: Any) -> dict[str, Any]:
    suffix = uuid4()
    user_id = connection.execute(
        text(
            """
            INSERT INTO users (auth_subject, email, display_name)
            VALUES (:auth_subject, :email, :display_name)
            RETURNING id
            """
        ),
        {
            "auth_subject": f"supabase:{suffix}",
            "email": f"{suffix}@example.com",
            "display_name": "Creator Test User",
        },
    ).scalar_one()
    workspace_id = connection.execute(
        text("INSERT INTO workspaces (name) VALUES (:name) RETURNING id"),
        {"name": f"Workspace {suffix}"},
    ).scalar_one()
    connection.execute(
        text(
            """
            INSERT INTO workspace_memberships (workspace_id, user_id, role)
            VALUES (:workspace_id, :user_id, 'owner')
            """
        ),
        {"workspace_id": workspace_id, "user_id": user_id},
    )
    content_id = connection.execute(
        text(
            """
            INSERT INTO contents (workspace_id, created_by_user_id, type, title)
            VALUES (:workspace_id, :user_id, 'IMAGE', :title)
            RETURNING id
            """
        ),
        {"workspace_id": workspace_id, "user_id": user_id, "title": f"Image {suffix}"},
    ).scalar_one()
    return {"user_id": user_id, "workspace_id": workspace_id, "content_id": content_id}


def seed_generation(connection: Any, ids: dict[str, Any]) -> Any:
    return connection.execute(
        text(
            """
            INSERT INTO generations (
                workspace_id,
                content_id,
                requested_by_user_id,
                type,
                model,
                prompt
            )
            VALUES (
                :workspace_id,
                :content_id,
                :user_id,
                'IMAGE',
                'gemini-test',
                'Generate a launch image'
            )
            RETURNING id
            """
        ),
        ids,
    ).scalar_one()


def seed_job(connection: Any, ids: dict[str, Any], generation_id: Any) -> Any:
    return connection.execute(
        text(
            """
            INSERT INTO generation_jobs (workspace_id, generation_id)
            VALUES (:workspace_id, :generation_id)
            RETURNING id
            """
        ),
        {"workspace_id": ids["workspace_id"], "generation_id": generation_id},
    ).scalar_one()


def insert_image(connection: Any, ids: dict[str, Any], generation_id: Any, **overrides: Any) -> Any:
    values = {
        "workspace_id": ids["workspace_id"],
        "content_id": ids["content_id"],
        "generation_id": generation_id,
        "version_number": 1,
        "storage_path": f"{ids['workspace_id']}/{uuid4()}.png",
        "public_url": f"https://example.com/{uuid4()}.png",
        "mime_type": "image/png",
        "width": 1024,
        "height": 768,
        "model": "gemini-test",
        "prompt": "Generate a launch image",
    }
    values.update(overrides)
    return connection.execute(
        text(
            """
            INSERT INTO images (
                workspace_id,
                content_id,
                generation_id,
                version_number,
                storage_path,
                public_url,
                mime_type,
                width,
                height,
                model,
                prompt
            )
            VALUES (
                :workspace_id,
                :content_id,
                :generation_id,
                :version_number,
                :storage_path,
                :public_url,
                :mime_type,
                :width,
                :height,
                :model,
                :prompt
            )
            RETURNING id
            """
        ),
        values,
    ).scalar_one()


def test_alembic_upgrade_and_downgrade_clean_database() -> None:
    database_url = test_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    config = alembic_config(database_url)
    reset_public_schema(engine)

    try:
        command.upgrade(config, "head")
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())

        command.downgrade(config, "base")
        assert EXPECTED_TABLES.isdisjoint(set(inspect(engine).get_table_names()))
    finally:
        reset_public_schema(engine)
        engine.dispose()


def test_settings_are_unique_per_user(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        ids = seed_user_workspace_content(connection)
        connection.execute(
            text("INSERT INTO settings (user_id) VALUES (:user_id)"),
            {"user_id": ids["user_id"]},
        )

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO settings (user_id) VALUES (:user_id)"),
            {"user_id": ids["user_id"]},
        )


def test_completed_image_requires_valid_generation(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        ids = seed_user_workspace_content(connection)

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        insert_image(connection, ids, uuid4())

    with migrated_engine.begin() as connection:
        generation_id = seed_generation(connection, ids)
        image_id = insert_image(connection, ids, generation_id)

    assert image_id is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"mime_type": "image/gif"},
        {"width": 0},
        {"height": 0},
        {"version_number": 0},
        {"prompt": ""},
    ],
)
def test_image_integrity_constraints_reject_invalid_metadata(
    migrated_engine: Engine,
    overrides: dict[str, Any],
) -> None:
    with migrated_engine.begin() as connection:
        ids = seed_user_workspace_content(connection)
        generation_id = seed_generation(connection, ids)

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        insert_image(connection, ids, generation_id, **overrides)


def test_external_id_is_unique_when_present(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        ids = seed_user_workspace_content(connection)
        first_generation_id = seed_generation(connection, ids)
        second_generation_id = seed_generation(connection, ids)
        connection.execute(
            text(
                """
                INSERT INTO generation_jobs (workspace_id, generation_id, external_id)
                VALUES (:workspace_id, :generation_id, 'provider-job-1')
                """
            ),
            {"workspace_id": ids["workspace_id"], "generation_id": first_generation_id},
        )

    with pytest.raises(IntegrityError), migrated_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO generation_jobs (workspace_id, generation_id, external_id)
                VALUES (:workspace_id, :generation_id, 'provider-job-1')
                """
            ),
            {"workspace_id": ids["workspace_id"], "generation_id": second_generation_id},
        )


def test_status_history_reconstructs_job_transitions(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        ids = seed_user_workspace_content(connection)
        generation_id = seed_generation(connection, ids)
        job_id = seed_job(connection, ids, generation_id)
        connection.execute(
            text(
                """
                INSERT INTO generation_job_status_events (
                    generation_job_id,
                    previous_status,
                    status
                )
                VALUES (:job_id, NULL, 'PENDING'), (:job_id, 'PENDING', 'PROCESSING')
                """
            ),
            {"job_id": job_id},
        )
        statuses = connection.execute(
            text(
                """
                SELECT previous_status, status
                FROM generation_job_status_events
                WHERE generation_job_id = :job_id
                ORDER BY occurred_at, id
                """
            ),
            {"job_id": job_id},
        ).all()

    assert statuses == [(None, "PENDING"), ("PENDING", "PROCESSING")]


def test_soft_delete_preserves_image_record(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        ids = seed_user_workspace_content(connection)
        generation_id = seed_generation(connection, ids)
        image_id = insert_image(connection, ids, generation_id)
        connection.execute(
            text("UPDATE images SET deleted_at = now() WHERE id = :image_id"),
            {"image_id": image_id},
        )
        row = connection.execute(
            text("SELECT count(*) AS total, count(deleted_at) AS deleted FROM images"),
        ).one()

    assert row.total == 1
    assert row.deleted == 1


def test_concurrent_image_version_insert_allows_one_winner(migrated_engine: Engine) -> None:
    with migrated_engine.begin() as connection:
        ids = seed_user_workspace_content(connection)
        first_generation_id = seed_generation(connection, ids)
        second_generation_id = seed_generation(connection, ids)

    errors: list[BaseException] = []

    with migrated_engine.connect() as first_connection:
        first_transaction = first_connection.begin()
        insert_image(first_connection, ids, first_generation_id)

        def insert_competing_version() -> None:
            try:
                with migrated_engine.begin() as second_connection:
                    second_connection.execute(text("SET LOCAL statement_timeout = '5000ms'"))
                    insert_image(second_connection, ids, second_generation_id)
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=insert_competing_version)
        thread.start()
        time.sleep(0.2)
        first_transaction.commit()
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], IntegrityError)
