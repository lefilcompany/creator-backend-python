from collections.abc import Iterator

import pytest
from fastapi import HTTPException

from creator.api.dependencies import Principal, get_principal
from creator.config import Settings, get_settings
from creator.infrastructure.db import get_db
from creator.infrastructure.queue import get_generation_queue
from creator.services.ai.factory import UnconfiguredLLMProvider


def test_settings_are_cached() -> None:
    assert get_settings() is get_settings()


def test_principal_is_created_for_bearer_token() -> None:
    principal = get_principal("Bearer token", Settings(auth_required=True))

    assert principal == Principal(subject="unverified-token")


def test_missing_required_auth_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal(None, Settings(auth_required=True))

    assert error.value.status_code == 401


def test_malformed_auth_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal("Basic token", Settings())

    assert error.value.status_code == 401


def test_db_dependency_yields_a_session() -> None:
    session: Iterator[object] = get_db()

    assert next(session).__class__.__name__ == "Session"
    session.close()


def test_queue_factory_uses_generation_queue() -> None:
    queue = get_generation_queue()

    assert queue.name == "generations"


def test_unconfigured_provider_is_explicit() -> None:
    assert isinstance(UnconfiguredLLMProvider(), UnconfiguredLLMProvider)
