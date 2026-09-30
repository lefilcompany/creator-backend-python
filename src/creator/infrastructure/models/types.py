"""Shared SQLAlchemy scalar types."""

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID

uuid_pk = PGUUID(as_uuid=True)
timestamp_tz = DateTime(timezone=True)

__all__ = ["timestamp_tz", "uuid_pk"]
