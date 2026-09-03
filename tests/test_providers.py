import pytest

from creator.config import Settings
from creator.services.ai.factory import ProviderNotConfiguredError, create_llm_provider
from creator.services.ai.gemini import GeminiLLMProvider


def test_unconfigured_provider_fails_closed() -> None:
    provider = create_llm_provider(Settings(gemini_api_key=None))

    with pytest.raises(ProviderNotConfiguredError):
        provider.generate_text("hello")


def test_gemini_api_key_selects_gemini_text_provider() -> None:
    provider = create_llm_provider(Settings(gemini_api_key="secret"))

    assert isinstance(provider, GeminiLLMProvider)
