from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from creator.application.unit_of_work import UnitOfWork
from creator.config import Settings, get_settings
from creator.infrastructure.unit_of_work import get_unit_of_work


@dataclass(frozen=True)
class Principal:
    subject: str


def get_principal(
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,  # type: ignore[assignment]
) -> Principal | None:
    if not authorization:
        if settings.auth_required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    # JWT signature validation is intentionally isolated as ADR-004 work.
    return Principal(subject="unverified-token")


def get_uow(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> UnitOfWork:
    return unit_of_work
