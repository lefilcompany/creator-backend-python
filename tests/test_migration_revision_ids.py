from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_migration_revision_ids_fit_alembic_version_column() -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    scripts = ScriptDirectory.from_config(config)

    revision_ids = [script.revision for script in scripts.walk_revisions()]

    assert revision_ids
    assert all(len(revision_id) <= 32 for revision_id in revision_ids)
