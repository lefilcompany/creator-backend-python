from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from creator.application.content_generation import WorkspaceAccessDeniedError
from creator.application.unit_of_work import UnitOfWork
from creator.config import Settings
from creator.domain.exceptions import DomainError, EntityNotFoundError
from creator.prompts import build_text_improvement_prompt, prompt_template_metadata
from creator.repositories import ContentRecord, UserRecord
from creator.services.ai.provider import LLMProvider


class ContentImprovementInvalidResponseError(DomainError):
    """Raised when a provider response cannot satisfy the improvement contract."""


@dataclass(frozen=True, slots=True)
class ImproveContentCommand:
    workspace_id: UUID
    text: str | None
    content_id: UUID | None
    objective: str
    context: dict[str, Any]
    audience: str | None = None


@dataclass(frozen=True, slots=True)
class ImprovedContentPreview:
    text: str
    justification: str
    original_text: str
    objective: str
    persistence: str
    content_id: UUID | None
    prompt_template: dict[str, Any]


def improve_content(
    *,
    unit_of_work: UnitOfWork,
    settings: Settings,
    llm_provider: LLMProvider,
    user: UserRecord,
    command: ImproveContentCommand,
) -> ImprovedContentPreview:
    if not unit_of_work.contents.user_has_workspace_access(
        user_id=user.id,
        workspace_id=command.workspace_id,
    ):
        raise WorkspaceAccessDeniedError("Workspace access denied")

    original_text = command.text
    if original_text is None:
        content = _content_for_improvement(
            unit_of_work=unit_of_work,
            user=user,
            content_id=command.content_id,
            workspace_id=command.workspace_id,
        )
        original_text = _text_from_content(content)

    rendered_prompt = build_text_improvement_prompt(
        objective=command.objective,
        context={
            "workspace_id": str(command.workspace_id),
            "request_context": command.context,
            "persistence": "preview_only",
            "output_contract": {"format": "json", "required": ["text", "justification"]},
        },
        user_input={
            "text": original_text,
            "objective": command.objective,
            "audience": command.audience,
        },
        metadata={"provider": "gemini", "model": settings.gemini_text_model},
    )
    provider_output = llm_provider.generate_text(rendered_prompt.text)
    parsed = _parse_provider_output(provider_output)

    return ImprovedContentPreview(
        text=parsed["text"],
        justification=parsed["justification"],
        original_text=original_text,
        objective=command.objective,
        persistence="preview_only",
        content_id=command.content_id,
        prompt_template=prompt_template_metadata(rendered_prompt),
    )


def _content_for_improvement(
    *,
    unit_of_work: UnitOfWork,
    user: UserRecord,
    content_id: UUID | None,
    workspace_id: UUID,
) -> ContentRecord:
    if content_id is None:
        raise EntityNotFoundError("Content not found")
    content = unit_of_work.contents.get_by_id_for_user(
        user_id=user.id,
        content_id=content_id,
    )
    if content is None:
        raise EntityNotFoundError("Content not found")
    if content.workspace_id != workspace_id:
        raise WorkspaceAccessDeniedError("Workspace access denied")
    return content


def _text_from_content(content: ContentRecord) -> str:
    if content.content_type != "TEXT":
        raise ContentImprovementInvalidResponseError("Content is not text")
    text = content.payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ContentImprovementInvalidResponseError("Content text is unavailable")
    return text


def _parse_provider_output(provider_output: str) -> dict[str, str]:
    try:
        payload: Any = json.loads(provider_output)
    except json.JSONDecodeError as error:
        raise ContentImprovementInvalidResponseError(
            "LLM provider returned a non-JSON improvement response"
        ) from error
    if not isinstance(payload, dict):
        raise ContentImprovementInvalidResponseError(
            "LLM provider returned an invalid improvement response"
        )
    text = payload.get("text")
    justification = payload.get("justification")
    if not isinstance(text, str) or not text.strip():
        raise ContentImprovementInvalidResponseError("LLM provider did not return improved text")
    if not isinstance(justification, str) or not justification.strip():
        raise ContentImprovementInvalidResponseError(
            "LLM provider did not return an improvement justification"
        )
    return {"text": text.strip(), "justification": justification.strip()}
