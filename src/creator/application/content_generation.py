from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from creator.application.unit_of_work import UnitOfWork
from creator.config import Settings
from creator.domain.exceptions import DomainError, PersistenceError
from creator.prompts import (
    build_content_generation_prompt,
    generation_parameters_with_prompt_template,
)
from creator.repositories import GeneratedTextContentRecord, UserRecord
from creator.services.ai.provider import LLMProvider


class WorkspaceAccessDeniedError(DomainError):
    """Raised when a Principal has no active Membership for a Workspace."""


class ContentGenerationPersistenceError(PersistenceError):
    """Raised when generated Content cannot be persisted."""


@dataclass(frozen=True, slots=True)
class GenerateContentCommand:
    workspace_id: UUID
    topic: str
    audience: str
    tone: str | None
    content_type: str
    brand_voice: str | None


def generate_content(
    *,
    unit_of_work: UnitOfWork,
    settings: Settings,
    llm_provider: LLMProvider,
    user: UserRecord,
    command: GenerateContentCommand,
) -> GeneratedTextContentRecord:
    if not unit_of_work.contents.user_has_workspace_access(
        user_id=user.id,
        workspace_id=command.workspace_id,
    ):
        raise WorkspaceAccessDeniedError("Workspace access denied")

    stored_settings = unit_of_work.settings.get_by_user_id(user.id)
    settings_preferences = (
        {
            "brand_name": stored_settings.brand_name,
            "segment": stored_settings.segment,
            "tone": stored_settings.tone,
            "voice": stored_settings.voice,
            "visual_style": stored_settings.visual_style,
            "default_preferences": stored_settings.default_preferences,
        }
        if stored_settings
        else {}
    )
    request_payload = _request_payload(
        command,
        default_tone=stored_settings.tone if stored_settings else "professional",
        default_brand_voice=stored_settings.voice if stored_settings else "Clear and useful",
    )
    rendered_prompt = build_content_generation_prompt(
        context={
            "workspace_id": str(command.workspace_id),
            "settings": settings_preferences,
        },
        user_input=request_payload,
        metadata={"provider": "gemini", "model": settings.gemini_text_model},
    )
    generated_text = llm_provider.generate_text(rendered_prompt.text)

    content_payload: dict[str, object] = {
        "text": generated_text,
        "request": request_payload,
        "metadata": {
            "provider": "gemini",
            "model": settings.gemini_text_model,
            **rendered_prompt.metadata,
        },
    }
    generation_parameters = cast(
        dict[str, object],
        generation_parameters_with_prompt_template(
            {
                "provider": "gemini",
                "model": settings.gemini_text_model,
                "request": request_payload,
                "settings_context": {"included": bool(settings_preferences)},
            },
            rendered_prompt,
        ),
    )

    try:
        generated = unit_of_work.contents.create_text_generation(
            workspace_id=command.workspace_id,
            requested_by_user_id=user.id,
            title=command.topic,
            payload=content_payload,
            model=settings.gemini_text_model,
            prompt=rendered_prompt.text,
            parameters=generation_parameters,
        )
        unit_of_work.commit()
    except PersistenceError as error:
        unit_of_work.rollback()
        raise ContentGenerationPersistenceError(
            "Generated Content could not be persisted"
        ) from error

    return generated


def _request_payload(
    command: GenerateContentCommand,
    *,
    default_tone: str,
    default_brand_voice: str,
) -> dict[str, object]:
    return {
        "topic": command.topic,
        "audience": command.audience,
        "tone": command.tone or default_tone,
        "content_type": command.content_type,
        "brand_voice": command.brand_voice or default_brand_voice,
    }
