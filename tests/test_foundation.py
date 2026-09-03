import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request as UrlRequest
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from creator.api.dependencies import get_current_user, get_principal
from creator.config import Settings, get_settings
from creator.domain.auth import Principal
from creator.infrastructure.auth import (
    AuthConfigurationError,
    AuthInvalidResponseError,
    AuthLoginRejectedError,
    AuthRateLimitedError,
    AuthSignupRejectedError,
    AuthTimeoutError,
    SupabaseAuthClient,
    SupabaseAuthTokenVerifier,
)
from creator.infrastructure.db import get_db
from creator.infrastructure.queue import get_generation_queue
from creator.repositories import UserRecord
from creator.services.ai.factory import UnconfiguredLLMProvider

JWT_SECRET = "test-supabase-jwt-secret-with-32-bytes"
JWT_HS512_SECRET = "test-supabase-jwt-secret-with-64-plus-bytes-for-hs512-negative-test"
SUPABASE_URL = "https://creator-test.supabase.co"
SUPABASE_ANON_KEY = "test-supabase-anon-key"
NOW = datetime(2026, 9, 1, tzinfo=UTC)


RSA_PRIVATE_KEY_ONE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
RSA_PRIVATE_KEY_TWO = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeSigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class FakeJwksClient:
    def __init__(self, keys: dict[str, object]) -> None:
        self.keys = keys
        self.requested_kids: list[str] = []

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        kid = jwt.get_unverified_header(token)["kid"]
        self.requested_kids.append(kid)
        return FakeSigningKey(self.keys[kid])


class FakeSupabaseResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body


class FakeSupabaseOpener:
    def __init__(self, response: FakeSupabaseResponse | None = None) -> None:
        self.response = response
        self.requests: list[UrlRequest] = []
        self.timeouts: list[float] = []

    def __call__(self, request: UrlRequest, timeout: float) -> FakeSupabaseResponse:
        self.requests.append(request)
        self.timeouts.append(timeout)
        if self.response is None:
            raise TimeoutError
        return self.response


class FakeUserRepository:
    def __init__(self, existing: UserRecord | None = None) -> None:
        self.existing = existing
        self.added: list[dict[str, str | None]] = []
        self.updated: list[dict[str, object]] = []

    def add(
        self,
        *,
        external_id: str,
        email: str | None = None,
        display_name: str | None = None,
        global_role: str = "membro",
    ) -> UserRecord:
        self.added.append(
            {"external_id": external_id, "email": email, "display_name": display_name}
        )
        return user_record(external_id=external_id, email=email, display_name=display_name)

    def get_by_id(self, user_id: UUID, *, include_deleted: bool = False) -> UserRecord | None:
        return None

    def get_by_external_id(
        self, external_id: str, *, include_deleted: bool = False
    ) -> UserRecord | None:
        return self.existing

    def update_profile(
        self,
        user_id: UUID,
        *,
        email: str | None = None,
        display_name: str | None = None,
    ) -> UserRecord:
        self.updated.append({"user_id": user_id, "email": email, "display_name": display_name})
        return user_record(
            user_id=user_id,
            external_id=self.existing.external_id if self.existing else "principal-123",
            email=email,
            display_name=display_name,
        )

    def soft_delete(self, user_id: UUID) -> None:
        return None


class FakeUnitOfWork:
    def __init__(self, users: FakeUserRepository) -> None:
        self.users = users
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None


def supabase_auth_settings() -> Settings:
    return Settings(
        auth_required=True,
        supabase_url=SUPABASE_URL,
        supabase_jwt_secret=JWT_SECRET,
    )


def supabase_login_settings() -> Settings:
    return Settings(
        supabase_url=SUPABASE_URL,
        supabase_anon_key=SUPABASE_ANON_KEY,
        supabase_auth_timeout_seconds=3,
    )


def supabase_access_token(
    *,
    subject: str = "principal-123",
    expires_delta: timedelta = timedelta(minutes=5),
    secret: str = JWT_SECRET,
    audience: str = "authenticated",
    issuer: str = f"{SUPABASE_URL}/auth/v1",
    role: str = "authenticated",
) -> str:
    return jwt.encode(
        {
            "sub": subject,
            "aud": audience,
            "iss": issuer,
            "exp": datetime.now(UTC) + expires_delta,
            "iat": datetime.now(UTC),
            "email": "principal@example.com",
            "role": role,
            "session_id": "session-123",
            "user_metadata": {"name": "Principal Example"},
        },
        secret,
        algorithm="HS256",
    )


def supabase_rs256_access_token(subject: str, kid: str, private_key: object) -> str:
    return jwt.encode(
        {
            "sub": subject,
            "aud": "authenticated",
            "iss": f"{SUPABASE_URL}/auth/v1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
            "email": f"{subject}@example.com",
            "role": "authenticated",
            "session_id": f"session-{subject}",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def user_record(
    *,
    user_id: UUID | None = None,
    external_id: str = "principal-123",
    email: str | None = "principal@example.com",
    display_name: str | None = "Principal Example",
    deleted_at: datetime | None = None,
) -> UserRecord:
    return UserRecord(
        id=user_id or uuid4(),
        external_id=external_id,
        email=email,
        display_name=display_name,
        global_role="membro",
        created_at=NOW,
        updated_at=NOW,
        deleted_at=deleted_at,
    )


def test_settings_are_cached() -> None:
    assert get_settings() is get_settings()


def test_principal_is_created_for_valid_supabase_token() -> None:
    principal = get_principal(f"Bearer {supabase_access_token()}", supabase_auth_settings())

    assert principal == Principal(
        subject="principal-123",
        email="principal@example.com",
        role="authenticated",
        session_id="session-123",
    )


def test_missing_required_auth_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal(None, Settings(auth_required=True))

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_malformed_auth_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal("Basic token", Settings())

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_expired_supabase_token_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal(
            f"Bearer {supabase_access_token(expires_delta=timedelta(minutes=-1))}",
            supabase_auth_settings(),
        )

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_supabase_token_with_invalid_signature_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal(
            f"Bearer {supabase_access_token(secret='wrong-secret-with-32-bytes-for-tests')}",
            supabase_auth_settings(),
        )

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_token_with_invalid_issuer_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal(
            f"Bearer {supabase_access_token(issuer='https://evil.example/auth/v1')}",
            supabase_auth_settings(),
        )

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_token_with_invalid_audience_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal(
            f"Bearer {supabase_access_token(audience='anon')}",
            supabase_auth_settings(),
        )

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_token_with_unallowed_role_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal(
            f"Bearer {supabase_access_token(role='service_role')}",
            supabase_auth_settings(),
        )

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_token_with_unallowed_algorithm_is_rejected() -> None:
    token = jwt.encode(
        {
            "sub": "principal-123",
            "aud": "authenticated",
            "iss": f"{SUPABASE_URL}/auth/v1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
            "role": "authenticated",
            "session_id": "session-123",
        },
        JWT_HS512_SECRET,
        algorithm="HS512",
    )

    with pytest.raises(HTTPException) as error:
        get_principal(f"Bearer {token}", supabase_auth_settings())

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_jwks_verifier_accepts_rotated_asymmetric_keys_even_when_secret_exists() -> None:
    jwks_client = FakeJwksClient(
        {
            "key-one": RSA_PRIVATE_KEY_ONE.public_key(),
            "key-two": RSA_PRIVATE_KEY_TWO.public_key(),
        }
    )
    verifier = SupabaseAuthTokenVerifier(supabase_auth_settings(), jwks_client=jwks_client)

    first = verifier.verify(
        supabase_rs256_access_token("principal-one", "key-one", RSA_PRIVATE_KEY_ONE)
    )
    second = verifier.verify(
        supabase_rs256_access_token("principal-two", "key-two", RSA_PRIVATE_KEY_TWO)
    )

    assert first.subject == "principal-one"
    assert second.subject == "principal-two"
    assert jwks_client.requested_kids == ["key-one", "key-two"]


def test_hs256_token_without_secret_is_misconfigured() -> None:
    verifier = SupabaseAuthTokenVerifier(
        Settings(
            _env_file=None,
            auth_required=True,
            supabase_url=SUPABASE_URL,
            supabase_jwt_secret=None,
        )
    )

    with pytest.raises(AuthConfigurationError):
        verifier.verify(supabase_access_token())


def test_current_user_creates_local_user_for_valid_principal() -> None:
    users = FakeUserRepository()
    unit_of_work = FakeUnitOfWork(users)
    principal = Principal(
        subject="principal-123",
        email="principal@example.com",
        role="authenticated",
        session_id="session-123",
        claims={"user_metadata": {"name": "Principal Example"}},
    )

    user = get_current_user(principal, unit_of_work)

    assert user.external_id == "principal-123"
    assert user.email == "principal@example.com"
    assert user.display_name == "Principal Example"
    assert users.added == [
        {
            "external_id": "principal-123",
            "email": "principal@example.com",
            "display_name": "Principal Example",
        }
    ]
    assert unit_of_work.commits == 1


def test_current_user_syncs_existing_local_user_profile() -> None:
    existing = user_record(email="old@example.com", display_name="Old Name")
    users = FakeUserRepository(existing)
    unit_of_work = FakeUnitOfWork(users)
    principal = Principal(
        subject=existing.external_id,
        email="new@example.com",
        role="authenticated",
        session_id="session-123",
        claims={"user_metadata": {"full_name": "New Name"}},
    )

    user = get_current_user(principal, unit_of_work)

    assert user.email == "new@example.com"
    assert user.display_name == "New Name"
    assert users.updated == [
        {"user_id": existing.id, "email": "new@example.com", "display_name": "New Name"}
    ]
    assert unit_of_work.commits == 1


def test_current_user_rejects_soft_deleted_local_user() -> None:
    users = FakeUserRepository(user_record(deleted_at=NOW))
    unit_of_work = FakeUnitOfWork(users)
    principal = Principal(subject="principal-123", role="authenticated", session_id="session-123")

    with pytest.raises(HTTPException) as error:
        get_current_user(principal, unit_of_work)

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTHENTICATION_INVALID"


def test_required_supabase_auth_without_settings_fails_closed() -> None:
    with pytest.raises(HTTPException) as error:
        get_principal(
            f"Bearer {supabase_access_token()}",
            Settings(auth_required=True, supabase_url=""),
        )

    assert error.value.status_code == 500
    assert error.value.detail["code"] == "AUTHENTICATION_MISCONFIGURED"


def test_optional_supabase_auth_without_settings_is_anonymous() -> None:
    principal = get_principal(
        f"Bearer {supabase_access_token()}",
        Settings(auth_required=False, supabase_url=""),
    )

    assert principal is None


def test_supabase_auth_client_signs_in_with_password_without_real_network() -> None:
    opener = FakeSupabaseOpener(
        FakeSupabaseResponse(
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "principal-123",
                    "email": "principal@example.com",
                    "role": "authenticated",
                    "aud": "authenticated",
                },
            }
        )
    )
    client = SupabaseAuthClient(supabase_login_settings(), opener=opener)

    session = client.sign_in_with_password(
        email="principal@example.com",
        password="correct-password",
    )

    assert session.access_token == "access-token"
    assert session.refresh_token == "refresh-token"
    assert session.principal == Principal(
        subject="principal-123",
        email="principal@example.com",
        role="authenticated",
    )
    assert opener.requests[0].full_url == f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    assert opener.requests[0].get_header("Apikey") == SUPABASE_ANON_KEY
    assert opener.timeouts == [3]


def test_supabase_auth_client_signs_up_with_confirmation_required() -> None:
    opener = FakeSupabaseOpener(
        FakeSupabaseResponse(
            {
                "id": "principal-123",
                "email": "new-principal@example.com",
                "role": "authenticated",
                "aud": "authenticated",
            }
        )
    )
    client = SupabaseAuthClient(supabase_login_settings(), opener=opener)

    result = client.sign_up_with_password(
        email="new-principal@example.com",
        password="correct-password",
    )

    assert result.principal == Principal(
        subject="principal-123",
        email="new-principal@example.com",
        role="authenticated",
    )
    assert result.session is None
    assert result.confirmation_required is True
    assert opener.requests[0].full_url == f"{SUPABASE_URL}/auth/v1/signup"


def test_supabase_auth_client_signs_up_with_immediate_session() -> None:
    opener = FakeSupabaseOpener(
        FakeSupabaseResponse(
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "principal-123",
                    "email": "new-principal@example.com",
                    "role": "authenticated",
                    "aud": "authenticated",
                },
            }
        )
    )
    client = SupabaseAuthClient(supabase_login_settings(), opener=opener)

    result = client.sign_up_with_password(
        email="new-principal@example.com",
        password="correct-password",
    )

    assert result.session is not None
    assert result.session.access_token == "access-token"
    assert result.confirmation_required is False


def test_supabase_auth_client_differentiates_rate_limit() -> None:
    client = SupabaseAuthClient(
        supabase_login_settings(),
        opener=FakeSupabaseOpener(FakeSupabaseResponse({"error": "rate_limit"}, status=429)),
    )

    with pytest.raises(AuthRateLimitedError):
        client.sign_in_with_password(email="principal@example.com", password="password")


def test_supabase_auth_client_treats_422_login_as_rejected() -> None:
    client = SupabaseAuthClient(
        supabase_login_settings(),
        opener=FakeSupabaseOpener(
            FakeSupabaseResponse(
                {"code": "invalid_credentials", "message": "Invalid login credentials"},
                status=422,
            )
        ),
    )

    with pytest.raises(AuthLoginRejectedError) as error:
        client.sign_in_with_password(email="principal@example.com", password="password")

    assert error.value.provider_code == "invalid_credentials"
    assert error.value.provider_message == "Invalid login credentials"


def test_supabase_auth_client_treats_http_422_signup_as_rejected() -> None:
    def opener(request: UrlRequest, timeout: float) -> FakeSupabaseResponse:
        raise HTTPError(
            request.full_url,
            422,
            "Unprocessable Entity",
            hdrs={},
            fp=BytesIO(b'{"code":"user_already_exists","msg":"User already registered"}'),
        )

    client = SupabaseAuthClient(supabase_login_settings(), opener=opener)

    with pytest.raises(AuthSignupRejectedError) as error:
        client.sign_up_with_password(email="principal@example.com", password="password")

    assert error.value.provider_code == "user_already_exists"
    assert error.value.provider_message == "User already registered"


def test_supabase_auth_client_differentiates_timeout() -> None:
    client = SupabaseAuthClient(supabase_login_settings(), opener=FakeSupabaseOpener())

    with pytest.raises(AuthTimeoutError):
        client.sign_in_with_password(email="principal@example.com", password="password")


def test_supabase_auth_client_differentiates_invalid_response() -> None:
    client = SupabaseAuthClient(
        supabase_login_settings(),
        opener=FakeSupabaseOpener(FakeSupabaseResponse({"access_token": "missing-fields"})),
    )

    with pytest.raises(AuthInvalidResponseError):
        client.sign_in_with_password(email="principal@example.com", password="password")


def test_db_dependency_yields_a_session() -> None:
    session: Iterator[object] = get_db()

    assert next(session).__class__.__name__ == "Session"
    session.close()


def test_queue_factory_uses_generation_queue() -> None:
    queue = get_generation_queue()

    assert queue.name == "generations"


def test_unconfigured_provider_is_explicit() -> None:
    assert isinstance(UnconfiguredLLMProvider(), UnconfiguredLLMProvider)
