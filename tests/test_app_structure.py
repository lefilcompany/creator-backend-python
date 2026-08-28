import importlib


def test_executable_app_modules_are_importable() -> None:
    for module_name in [
        "creator.api",
        "creator.config",
        "creator.domain",
        "creator.infrastructure",
        "creator.integrations",
        "creator.repositories",
        "creator.services",
    ]:
        assert importlib.import_module(module_name)
