from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from creator.api import dependencies
from creator.api.dependencies import get_current_user, get_principal
from creator.config import Settings, get_settings
from creator.domain.auth import Principal
from creator.infrastructure.auth import AccessTokenInvalidError
from creator.infrastructure.db import get_db
from creator.infrastructure.queue import get_generation_queue
from creator.services.agents.factory import UnconfiguredMultiAgentOrchestrator
from creator.services.ai.factory import UnconfiguredLLMProvider


def test_settings_are_cached() -> None:
    assert get_settings() is get_settings()


def test_required_auth_without_supabase_configuration_fails_closed() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal("Bearer token", Settings(auth_required=True))

    assert error.value.status_code == 500
    assert error.value.detail["code"] == "AUTHENTICATION_MISCONFIGURED"


def test_optional_auth_without_supabase_configuration_returns_none() -> None:
    assert get_principal("Bearer token", Settings(auth_required=False)) is None


def test_optional_auth_without_credentials_returns_none() -> None:
    assert get_principal(None, Settings(auth_required=False)) is None


def test_principal_is_created_from_auth_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeVerifier:
        def verify(self, token: str) -> Principal:
            return Principal(subject=token)

    monkeypatch.setattr(
        dependencies,
        "create_auth_token_verifier",
        lambda settings: FakeVerifier(),
    )

    assert get_principal("Bearer principal-id", Settings(auth_required=True)) == Principal(
        subject="principal-id"
    )


def test_invalid_bearer_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeVerifier:
        def verify(self, token: str) -> Principal:
            raise AccessTokenInvalidError("invalid")

    monkeypatch.setattr(
        dependencies,
        "create_auth_token_verifier",
        lambda settings: FakeVerifier(),
    )

    with pytest.raises(HTTPException) as error:
        get_principal("Bearer token", Settings(auth_required=True))

    assert error.value.status_code == 401


def test_current_user_creates_missing_user() -> None:
    created_user = SimpleNamespace(
        id="user-id",
        external_id="principal-id",
        email="person@example.com",
        display_name="Person",
        deleted_at=None,
    )

    class FakeUsers:
        def get_by_external_id(self, external_id: str, *, include_deleted: bool) -> None:
            return None

        def add(
            self,
            *,
            external_id: str,
            email: str | None,
            display_name: str | None,
        ) -> SimpleNamespace:
            assert external_id == "principal-id"
            assert email == "person@example.com"
            assert display_name == "Person"
            return created_user

    class FakeUnitOfWork:
        users = FakeUsers()

        def commit(self) -> None:
            self.committed = True

    unit_of_work = FakeUnitOfWork()
    principal = Principal(
        subject="principal-id",
        email="person@example.com",
        claims={"user_metadata": {"display_name": "Person"}},
    )

    assert get_current_user(principal, unit_of_work) is created_user
    assert unit_of_work.committed is True


def test_current_user_rejects_missing_principal() -> None:
    with pytest.raises(HTTPException) as error:
        get_current_user(None, SimpleNamespace())

    assert error.value.status_code == 401


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


def test_unconfigured_multi_agent_orchestrator_is_explicit() -> None:
    assert isinstance(UnconfiguredMultiAgentOrchestrator(), UnconfiguredMultiAgentOrchestrator)
