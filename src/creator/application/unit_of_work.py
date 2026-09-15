from types import TracebackType
from typing import Protocol, Self

from creator.repositories import (
    AssetRepository,
    BrandRepository,
    BrandSettingsRepository,
    ContentRepository,
    GenerationRepository,
    ImageGenerationRepository,
    ProjectRepository,
    SettingsRepository,
    UserRepository,
    WorkspaceRepository,
)


class UnitOfWork(Protocol):
    users: UserRepository
    settings: SettingsRepository
    workspaces: WorkspaceRepository
    brands: BrandRepository
    projects: ProjectRepository
    contents: ContentRepository
    generations: GenerationRepository
    assets: AssetRepository
    brand_settings: BrandSettingsRepository
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
