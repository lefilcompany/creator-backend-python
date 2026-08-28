from types import TracebackType
from typing import Protocol, Self

from creator.domain.repositories import (
    ContentRepository,
    ImageGenerationRepository,
    SettingsRepository,
    UserRepository,
)


class UnitOfWork(Protocol):
    users: UserRepository
    settings: SettingsRepository
    contents: ContentRepository
    image_generations: ImageGenerationRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
