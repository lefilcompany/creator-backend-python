import pytest

from creator.config import Settings
from creator.services.agents.factory import (
    AgentOrchestratorNotConfiguredError,
    create_multi_agent_orchestrator,
)
from creator.services.ai.factory import ProviderNotConfiguredError, create_llm_provider
from creator.services.retrieval.factory import (
    RetrievalProviderNotConfiguredError,
    create_embedding_provider,
    create_semantic_retriever,
    create_tool_calling_provider,
)


def test_unconfigured_provider_fails_closed() -> None:
    provider = create_llm_provider(Settings(gemini_api_key=None))

    with pytest.raises(ProviderNotConfiguredError):
        provider.generate_text("hello")


def test_unconfigured_multi_agent_orchestrator_fails_closed() -> None:
    orchestrator = create_multi_agent_orchestrator(Settings(crewai_enabled=False))

    with pytest.raises(AgentOrchestratorNotConfiguredError):
        orchestrator.kickoff("Plan a Workspace content campaign")


def test_unconfigured_embedding_provider_fails_closed() -> None:
    provider = create_embedding_provider(Settings(langchain_enabled=False))

    with pytest.raises(RetrievalProviderNotConfiguredError):
        provider.embed_query("Find relevant Content")


def test_unconfigured_semantic_retriever_fails_closed() -> None:
    retriever = create_semantic_retriever(Settings(langchain_enabled=False))

    with pytest.raises(RetrievalProviderNotConfiguredError):
        retriever.search("Find relevant Content", workspace_id="workspace-id")


def test_unconfigured_tool_calling_provider_fails_closed() -> None:
    provider = create_tool_calling_provider(Settings(langchain_enabled=False))

    with pytest.raises(RetrievalProviderNotConfiguredError):
        provider.invoke_with_tools("Use a safe tool", tools=[])
