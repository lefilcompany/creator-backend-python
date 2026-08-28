from creator.config import Settings
from creator.services.ai.factory import ProviderNotConfiguredError


class GeminiLLMProvider:
    """Gemini boundary; network integration is delivered by ADR-001 issue."""

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise ProviderNotConfiguredError("GEMINI_API_KEY is required")
        self.model = settings.gemini_text_model

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        raise ProviderNotConfiguredError("Gemini network adapter is not implemented")
