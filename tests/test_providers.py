import pytest

from creator.config import Settings
from creator.services.ai.factory import ProviderNotConfiguredError, create_llm_provider


def test_unconfigured_provider_fails_closed() -> None:
    provider = create_llm_provider(Settings(gemini_api_key=None))

    with pytest.raises(ProviderNotConfiguredError):
        provider.generate_text("hello")
