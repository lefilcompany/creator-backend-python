from typing import Protocol


class ProviderNotConfiguredError(RuntimeError):
    """Raised when a provider cannot safely be used."""


class LLMProvider(Protocol):
    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate text for a validated prompt."""
