from collections.abc import Mapping
from typing import Protocol


class MultiAgentOrchestrator(Protocol):
    def kickoff(self, goal: str, inputs: Mapping[str, object] | None = None) -> str:
        """Run a validated multi-agent workflow for a Workspace-scoped goal."""
