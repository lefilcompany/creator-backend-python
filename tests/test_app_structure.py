import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_executable_app_modules_are_importable() -> None:
    for module_name in [
        "creator.api",
        "creator.config",
        "creator.domain",
        "creator.infrastructure",
        "creator.integrations",
        "creator.repositories",
        "creator.services",
    ]:
        assert importlib.import_module(module_name)


def test_container_image_includes_alembic_artifacts() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY alembic.ini ./" in dockerfile
    assert "COPY migrations ./migrations" in dockerfile


def test_compose_runs_migrations_before_api_and_worker() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "  migrate:" in compose
    assert 'command: ["alembic", "upgrade", "head"]' in compose
    assert compose.count("migrate: { condition: service_completed_successfully }") == 2
