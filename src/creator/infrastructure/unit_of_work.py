from __future__ import annotations

from collections.abc import Callable, Generator
from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from creator.domain.exceptions import PersistenceError
from creator.domain.repositories import (
    ContentRepository,
    ImageGenerationRepository,
    SettingsRepository,
    UserRepository,
)
from creator.infrastructure.db import SessionLocal
from creator.infrastructure.repositories import (
    SqlAlchemyContentRepository,
    SqlAlchemyImageGenerationRepository,
    SqlAlchemySettingsRepository,
    SqlAlchemyUserRepository,
    map_sqlalchemy_error,
)

SessionFactory = Callable[[], Session]


class SqlAlchemyUnitOfWork:
    users: UserRepository
    settings: SettingsRepository
    contents: ContentRepository
    image_generations: ImageGenerationRepository

    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._committed = False

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        session = self._session_factory()
        self._session = session
        self.users = SqlAlchemyUserRepository(session)
        self.settings = SqlAlchemySettingsRepository(session)
        self.contents = SqlAlchemyContentRepository(session)
        self.image_generations = SqlAlchemyImageGenerationRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            if exc_type is not None or not self._committed:
                session.rollback()
        finally:
            session.close()

    def commit(self) -> None:
        session = self._require_session()
        try:
            session.commit()
        except SQLAlchemyError as error:
            session.rollback()
            raise map_sqlalchemy_error(error) from error
        self._committed = True

    def rollback(self) -> None:
        self._require_session().rollback()
        self._committed = False

    def _require_session(self) -> Session:
        if self._session is None:
            raise PersistenceError("Unit of Work is not active")
        return self._session


def get_unit_of_work() -> Generator[SqlAlchemyUnitOfWork, None, None]:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        yield unit_of_work
