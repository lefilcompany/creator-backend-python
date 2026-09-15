from creator.config import Settings
from creator.services.ai.gemini import GeminiLLMProvider
from creator.services.ai.provider import LLMProvider, ProviderNotConfiguredError


class UnconfiguredLLMProvider:
    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        raise ProviderNotConfiguredError("LLM provider is not configured")


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.gemini_api_key:
        return GeminiLLMProvider(settings)
    return UnconfiguredLLMProvider()
