from creator.config import Settings
from creator.services.ai.gemini import GeminiLLMProvider
from creator.services.ai.provider import LLMProvider, ProviderNotConfiguredError
from creator.services.ai.reviewer import (
    MultimodalImageReviewer,
    UnconfiguredMultimodalImageReviewer,
)


class UnconfiguredLLMProvider:
    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        raise ProviderNotConfiguredError("LLM provider is not configured")


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.gemini_api_key:
        return GeminiLLMProvider(settings)
    return UnconfiguredLLMProvider()


def create_image_reviewer(settings: Settings) -> MultimodalImageReviewer:
    if settings.gemini_api_key:
        from creator.integrations.gemini.image_reviewer import GeminiMultimodalImageReviewer

        return GeminiMultimodalImageReviewer(settings)
    return UnconfiguredMultimodalImageReviewer()
