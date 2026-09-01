from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    email: str | None = None
    role: str | None = None
    session_id: str | None = None
    claims: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class AuthSession:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    principal: Principal
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class AuthSignupResult:
    principal: Principal
    session: AuthSession | None
    confirmation_required: bool
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
