from creator.config import Settings
from creator.services.ai.provider import LLMProvider


class ProviderNotConfiguredError(RuntimeError):
    """Raised when a provider cannot safely be used."""


class UnconfiguredLLMProvider:
    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        raise ProviderNotConfiguredError("LLM provider is not configured")


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.gemini_api_key:
        # The real Gemini adapter is tracked by ADR-001's implementation issue.
        return UnconfiguredLLMProvider()
    return UnconfiguredLLMProvider()
