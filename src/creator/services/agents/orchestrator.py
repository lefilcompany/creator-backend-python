from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel

from creator.services.agents.contracts import AgentExecutionContext, AgentExecutionResult


class MultiAgentOrchestrator(Protocol):
    def kickoff(self, goal: str, inputs: Mapping[str, object] | None = None) -> str:
        """Run a validated multi-agent workflow for a Workspace-scoped goal."""

    def execute(
        self, context: AgentExecutionContext, output_model: type[BaseModel]
    ) -> AgentExecutionResult:
        """Execute one validated specialist role behind the provider boundary."""
