from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from creator.services.agents.contracts import AgentExecutionContext, AgentExecutionResult
from creator.services.agents.runner import StructuredAgentRunner
from creator.services.ai.provider import LLMProvider


class CrewAIMultiAgentOrchestrator:
    """CrewAI-compatible adapter boundary.

    The workflow engine owns sequencing and persistence. This adapter owns the
    provider-facing specialist execution, so replacing it with a CrewAI Flow or
    another orchestration runtime does not alter application contracts.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._runner = StructuredAgentRunner(provider)
        self._provider = provider

    def kickoff(self, goal: str, inputs: Mapping[str, object] | None = None) -> str:
        payload = dict(inputs or {})
        prompt = f"Goal: {goal}\nInputs: {payload}"
        return self._provider.generate_text(prompt, temperature=0.2)

    def execute(
        self, context: AgentExecutionContext, output_model: type[BaseModel]
    ) -> AgentExecutionResult:
        return self._runner.run(context, output_model)
