from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from creator.prompts.agents import build_agent_prompt, json_output_instructions
from creator.services.agents.contracts import AgentExecutionContext, AgentExecutionResult
from creator.services.ai.provider import LLMProvider

OutputModel = TypeVar("OutputModel", bound=BaseModel)


class StructuredAgentRunner:
    """Provider-neutral runner for specialist contracts.

    CrewAI adapters can replace this runner without changing the workflow state
    machine or persistence boundary.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def run(
        self, context: AgentExecutionContext, output_model: type[OutputModel]
    ) -> AgentExecutionResult:
        rendered = build_agent_prompt(
            context.role.value,
            {
                **dict(context.inputs),
                "output_instructions": json_output_instructions(output_model.__name__),
            },
        )
        raw = self._provider.generate_text(rendered.text, temperature=0.2)
        payload = json.loads(_strip_json_fence(raw))
        output = output_model.model_validate(payload)
        return AgentExecutionResult(
            output=output,
            prompt=rendered.text,
            input_hash=rendered.input_hash,
            provider=self._provider.__class__.__name__,
            model=getattr(self._provider, "model", None),
        )


def _strip_json_fence(text: str) -> str:
    normalized = text.strip()
    if normalized.startswith("```"):
        normalized = normalized.split("\n", 1)[-1]
        if normalized.endswith("```"):
            normalized = normalized[:-3]
    return normalized.strip()
