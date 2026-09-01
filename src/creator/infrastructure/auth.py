from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import jwt
from jwt import (
    ExpiredSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
    PyJWKClient,
    PyJWKClientError,
)

from creator.config import Settings
from creator.domain.auth import AuthSession, AuthSignupResult, Principal

ASYMMETRIC_JWT_ALGORITHMS = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA")
REQUIRED_JWT_CLAIMS = ("iss", "aud", "exp", "iat", "sub", "role", "session_id")


class AuthTokenVerifier(Protocol):
    def verify(self, token: str) -> Principal: ...


class JwksClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


class AuthClient(Protocol):
    def sign_in_with_password(self, *, email: str, password: str) -> AuthSession: ...

    def sign_up_with_password(self, *, email: str, password: str) -> AuthSignupResult: ...


class AuthError(Exception):
    """Base class for authentication failures at the Creator boundary."""


class AuthConfigurationError(AuthError):
    """Raised when required Supabase Auth settings are missing."""


class AccessTokenExpiredError(AuthError):
    """Raised when a Supabase access token is expired."""


class AccessTokenInvalidError(AuthError):
    """Raised when a Supabase access token cannot be trusted."""


class AuthLoginRejectedError(AuthError):
    """Raised when Supabase rejects the provided credentials."""


class AuthSignupRejectedError(AuthError):
    """Raised when Supabase rejects the signup request."""


class AuthRateLimitedError(AuthError):
    """Raised when Supabase rejects login because of quota or rate limits."""


class AuthTimeoutError(AuthError):
    """Raised when Supabase Auth does not respond before the configured timeout."""


class AuthUpstreamError(AuthError):
    """Raised when Supabase Auth returns an unexpected upstream error."""


class AuthInvalidResponseError(AuthError):
    """Raised when Supabase Auth returns a response Creator cannot normalize."""


class SupabaseAuthTokenVerifier:
    def __init__(self, settings: Settings, jwks_client: JwksClient | None = None) -> None:
        self._settings = settings
        self._jwks_client: JwksClient | None = jwks_client

    def verify(self, token: str) -> Principal:
        try:
            claims = self._decode_token(token)
        except ExpiredSignatureError as error:
            raise AccessTokenExpiredError("Supabase access token is expired") from error
        except (InvalidTokenError, MissingRequiredClaimError, PyJWKClientError) as error:
            raise AccessTokenInvalidError("Supabase access token is invalid") from error

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AccessTokenInvalidError("Supabase access token is missing subject")
        role = _string_claim(claims, "role")
        if role != "authenticated":
            raise AccessTokenInvalidError("Supabase access token role is not allowed")

        return Principal(
            subject=subject,
            email=_string_claim(claims, "email"),
            role=role,
            session_id=_string_claim(claims, "session_id"),
            claims=dict(claims),
        )

    def _decode_token(self, token: str) -> dict[str, Any]:
        self._require_base_settings()
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if not isinstance(algorithm, str) or algorithm not in self._allowed_algorithms:
            raise AccessTokenInvalidError("Supabase access token uses an unsupported algorithm")

        decode_kwargs: dict[str, Any] = {
            "audience": self._settings.supabase_jwt_audience,
            "issuer": self._issuer,
            "options": {"require": list(REQUIRED_JWT_CLAIMS)},
        }

        if algorithm == "HS256":
            if not self._settings.supabase_jwt_secret:
                raise AuthConfigurationError("SUPABASE_JWT_SECRET is required for HS256 tokens")
            decoded = jwt.decode(
                token,
                self._settings.supabase_jwt_secret,
                algorithms=["HS256"],
                **decode_kwargs,
            )
            return decoded

        if algorithm not in ASYMMETRIC_JWT_ALGORITHMS:
            raise AccessTokenInvalidError("Supabase access token uses an unsupported algorithm")

        signing_key = self._jwks().get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            **decode_kwargs,
        )
        return decoded

    def _require_base_settings(self) -> None:
        if not self._settings.supabase_url:
            raise AuthConfigurationError("SUPABASE_URL is required when AUTH_REQUIRED is true")

    @property
    def _allowed_algorithms(self) -> set[str]:
        return set(self._settings.supabase_allowed_jwt_algorithms)

    @property
    def _issuer(self) -> str:
        if not self._settings.supabase_url:
            raise AuthConfigurationError("SUPABASE_URL is required when AUTH_REQUIRED is true")
        return f"{self._settings.supabase_url.rstrip('/')}/auth/v1"

    def _jwks(self) -> JwksClient:
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(
                f"{self._issuer}/.well-known/jwks.json",
                lifespan=self._settings.supabase_jwks_cache_seconds,
                timeout=self._settings.supabase_auth_timeout_seconds,
            )
        return self._jwks_client


UrlOpen = Callable[[Request, float], Any]


def _urlopen(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)


class SupabaseAuthClient:
    def __init__(self, settings: Settings, opener: UrlOpen | None = None) -> None:
        self._settings = settings
        self._opener = opener or _urlopen

    def sign_in_with_password(self, *, email: str, password: str) -> AuthSession:
        self._require_login_settings()
        response_body = self._post(
            f"{self._auth_url}/token?grant_type=password",
            {"email": email, "password": password},
            rejected_error=AuthLoginRejectedError,
        )
        return self._parse_login_response(response_body)

    def sign_up_with_password(self, *, email: str, password: str) -> AuthSignupResult:
        self._require_login_settings()
        response_body = self._post(
            f"{self._auth_url}/signup",
            {"email": email, "password": password},
            rejected_error=AuthSignupRejectedError,
        )
        return self._parse_signup_response(response_body)

    def _post(
        self,
        url: str,
        payload: dict[str, str],
        *,
        rejected_error: type[AuthError],
    ) -> bytes:
        try:
            encoded_payload = json.dumps(payload).encode("utf-8")
            request = Request(
                url,
                data=encoded_payload,
                headers={
                    "apikey": self._anon_key,
                    "Authorization": f"Bearer {self._anon_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            response = self._opener(request, self._settings.supabase_auth_timeout_seconds)
            status_code = int(getattr(response, "status", 200))
            response_body = bytes(response.read())
        except HTTPError as error:
            self._raise_for_http_error(error, rejected_error=rejected_error)
        except TimeoutError as error:
            raise AuthTimeoutError("Supabase Auth login timed out") from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise AuthTimeoutError("Supabase Auth login timed out") from error
            raise AuthUpstreamError("Supabase Auth request failed") from error

        if status_code >= 500:
            raise AuthUpstreamError("Supabase Auth returned an upstream error")
        if status_code == 429:
            raise AuthRateLimitedError("Supabase Auth rate limit exceeded")
        if status_code in {400, 401, 403}:
            raise rejected_error("Supabase Auth rejected the request")
        if status_code >= 400:
            raise AuthUpstreamError("Supabase Auth request failed")
        return response_body

    def _raise_for_http_error(
        self,
        error: HTTPError,
        *,
        rejected_error: type[AuthError],
    ) -> None:
        if error.code == 429:
            raise AuthRateLimitedError("Supabase Auth rate limit exceeded") from error
        if error.code in {400, 401, 403}:
            raise rejected_error("Supabase Auth rejected the request") from error
        if error.code >= 500:
            raise AuthUpstreamError("Supabase Auth returned an upstream error") from error
        raise AuthUpstreamError("Supabase Auth request failed") from error

    def _parse_login_response(self, response_body: bytes) -> AuthSession:
        payload = self._decode_json_response(response_body)
        return _session_from_payload(payload)

    def _parse_signup_response(self, response_body: bytes) -> AuthSignupResult:
        payload = self._decode_json_response(response_body)
        session_payload = payload.get("session")
        if isinstance(session_payload, dict):
            session = _session_from_payload(session_payload)
            user = session_payload.get("user")
        elif "access_token" in payload:
            session = _session_from_payload(payload)
            user = payload.get("user")
        else:
            session = None
            user = payload.get("user", payload)

        if not isinstance(user, dict):
            raise AuthInvalidResponseError("Supabase Auth response is missing user")

        principal = _principal_from_user(user)
        return AuthSignupResult(
            principal=principal,
            session=session,
            confirmation_required=session is None,
            provider="supabase",
            metadata=_metadata(user),
        )

    def _decode_json_response(self, response_body: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AuthInvalidResponseError("Supabase Auth returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise AuthInvalidResponseError("Supabase Auth returned a non-object response")
        return payload

    def _require_login_settings(self) -> None:
        if not self._settings.supabase_url:
            raise AuthConfigurationError("SUPABASE_URL is required for Supabase Auth login")
        if not self._settings.supabase_anon_key:
            raise AuthConfigurationError("SUPABASE_ANON_KEY is required for Supabase Auth login")

    @property
    def _auth_url(self) -> str:
        if not self._settings.supabase_url:
            raise AuthConfigurationError("SUPABASE_URL is required for Supabase Auth login")
        return f"{self._settings.supabase_url.rstrip('/')}/auth/v1"

    @property
    def _anon_key(self) -> str:
        if not self._settings.supabase_anon_key:
            raise AuthConfigurationError("SUPABASE_ANON_KEY is required for Supabase Auth login")
        return self._settings.supabase_anon_key


def create_auth_token_verifier(settings: Settings) -> AuthTokenVerifier:
    return SupabaseAuthTokenVerifier(settings)


def create_auth_client(settings: Settings) -> AuthClient:
    return SupabaseAuthClient(settings)


def _string_claim(claims: dict[str, Any], claim_name: str) -> str | None:
    value = claims.get(claim_name)
    if isinstance(value, str) and value:
        return value
    return None


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AuthInvalidResponseError(f"Supabase Auth response is missing {key}")
    return value


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or value <= 0:
        raise AuthInvalidResponseError(f"Supabase Auth response is missing {key}")
    return value


def _principal_from_user(user: dict[str, Any]) -> Principal:
    return Principal(
        subject=_required_string(user, "id"),
        email=_optional_string(user, "email"),
        role=_optional_string(user, "role"),
        claims={},
    )


def _session_from_payload(payload: dict[str, Any]) -> AuthSession:
    user = payload.get("user")
    if not isinstance(user, dict):
        raise AuthInvalidResponseError("Supabase Auth response is missing user")

    return AuthSession(
        access_token=_required_string(payload, "access_token"),
        refresh_token=_required_string(payload, "refresh_token"),
        token_type=_required_string(payload, "token_type"),
        expires_in=_required_int(payload, "expires_in"),
        principal=_principal_from_user(user),
        provider="supabase",
        metadata=_metadata(user),
    )


def _metadata(user: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("app_metadata", "user_metadata", "aud", "created_at", "last_sign_in_at"):
        value = user.get(key)
        if value is not None:
            metadata[key] = value
    return metadata
