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
<<<<<<< HEAD
=======
    brands: BrandRepository
    projects: ProjectRepository
>>>>>>> 3f6417bb10585844ad5772267618c4bc9bd474a1
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
