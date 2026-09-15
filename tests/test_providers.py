import pytest

from creator.config import Settings
from creator.services.agents.factory import (
    AgentOrchestratorNotConfiguredError,
    create_multi_agent_orchestrator,
)
from creator.services.ai.factory import ProviderNotConfiguredError, create_llm_provider


def test_unconfigured_provider_fails_closed() -> None:
    provider = create_llm_provider(Settings(gemini_api_key=None))

    with pytest.raises(ProviderNotConfiguredError):
        provider.generate_text("hello")


def test_unconfigured_multi_agent_orchestrator_fails_closed() -> None:
    orchestrator = create_multi_agent_orchestrator(Settings(crewai_enabled=False))

    with pytest.raises(AgentOrchestratorNotConfiguredError):
        orchestrator.kickoff("Plan a Workspace content campaign")
