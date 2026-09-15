from collections.abc import Mapping

from creator.config import Settings
from creator.services.agents.orchestrator import MultiAgentOrchestrator


class AgentOrchestratorNotConfiguredError(RuntimeError):
    """Raised when a multi-agent orchestrator cannot safely be used."""


class UnconfiguredMultiAgentOrchestrator:
    def kickoff(self, goal: str, inputs: Mapping[str, object] | None = None) -> str:
        raise AgentOrchestratorNotConfiguredError("Multi-agent orchestrator is not configured")


def create_multi_agent_orchestrator(settings: Settings) -> MultiAgentOrchestrator:
    if settings.crewai_enabled:
        # CrewAI is intentionally kept behind this boundary; the concrete adapter
        # belongs to ADR-011's implementation issue.
        return UnconfiguredMultiAgentOrchestrator()
    return UnconfiguredMultiAgentOrchestrator()
