from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path() -> Path:
    """Use an isolated Windows temp directory without pytest's ACL-sensitive cleanup."""
    return Path(tempfile.mkdtemp(prefix="creator-pytest-"))
