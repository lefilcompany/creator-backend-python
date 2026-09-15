class DomainError(Exception):
    """Base class for errors that are meaningful to Creator use cases."""


class PersistenceError(DomainError):
    """A persistence boundary operation failed."""


class EntityNotFoundError(PersistenceError):
    """A requested entity does not exist or is outside the caller scope."""


class ConflictError(PersistenceError):
    """A persistence operation conflicts with an existing record."""


class InvalidStateTransitionError(PersistenceError):
    """A Generation Job status transition is not allowed."""


class ConcurrencyError(PersistenceError):
    """A concurrent persistence operation won the same business slot."""
