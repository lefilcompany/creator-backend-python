from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class PromptValidationError(ValueError):
    """Raised when prompt inputs cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class PromptBundle:
    template_id: str
    version: str
    system: str
    context: Mapping[str, object] = field(default_factory=dict)
    user_input: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    text: str
    template_id: str
    version: str
    input_hash: str
    metadata: JsonObject


class _Omitted:
    pass


_OMITTED = _Omitted()


def render_prompt(bundle: PromptBundle) -> RenderedPrompt:
    context = normalize_json_object(bundle.context)
    user_input = normalize_json_object(bundle.user_input)
    metadata = normalize_json_object(bundle.metadata)
    input_hash = _input_hash(
        {
            "template_id": bundle.template_id,
            "version": bundle.version,
            "context": context,
            "user_input": user_input,
        }
    )
    prompt_metadata: JsonObject = {
        **metadata,
        "prompt_template_id": bundle.template_id,
        "prompt_template_version": bundle.version,
        "prompt_input_hash": input_hash,
    }
    text = (
        "\n".join(
            [
                "CREATOR_PROMPT",
                f"template_id: {bundle.template_id}",
                f"template_version: {bundle.version}",
                "",
                "SECTION: SYSTEM",
                bundle.system.strip(),
                "",
                "SECTION: CONTEXT_JSON",
                _safe_json_dump(context),
                "",
                "SECTION: USER_INPUT_JSON",
                _safe_json_dump(user_input),
            ]
        )
        + "\n"
    )
    return RenderedPrompt(
        text=text,
        template_id=bundle.template_id,
        version=bundle.version,
        input_hash=input_hash,
        metadata=prompt_metadata,
    )


def prompt_template_metadata(rendered: RenderedPrompt) -> JsonObject:
    return {
        "id": rendered.template_id,
        "version": rendered.version,
        "input_hash": rendered.input_hash,
    }


def generation_parameters_with_prompt_template(
    parameters: Mapping[str, object] | None,
    rendered: RenderedPrompt,
) -> JsonObject:
    normalized = normalize_json_object(parameters or {})
    normalized["prompt_template"] = prompt_template_metadata(rendered)
    return normalized


def normalize_json_object(value: Mapping[str, object]) -> JsonObject:
    normalized = _normalize_value(value)
    if isinstance(normalized, _Omitted):
        return {}
    if not isinstance(normalized, dict):
        raise PromptValidationError("Prompt input must be a JSON object")
    return normalized


def _normalize_value(value: object) -> JsonValue | _Omitted:
    if value is None:
        return _OMITTED
    if isinstance(value, str):
        stripped = value.strip()
        return _escape_structure_markers(stripped) if stripped else _OMITTED
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PromptValidationError("Prompt input contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        normalized_mapping: JsonObject = {}
        for key in sorted(value.keys()):
            if not isinstance(key, str):
                raise PromptValidationError("Prompt input keys must be strings")
            normalized_key = _escape_structure_markers(key.strip())
            if not normalized_key:
                raise PromptValidationError("Prompt input keys must not be empty")
            normalized_child = _normalize_value(value[key])
            if not isinstance(normalized_child, _Omitted):
                normalized_mapping[normalized_key] = normalized_child
        return normalized_mapping if normalized_mapping else _OMITTED
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        normalized_sequence: list[JsonValue] = []
        for item in value:
            normalized_item = _normalize_value(item)
            if not isinstance(normalized_item, _Omitted):
                normalized_sequence.append(normalized_item)
        return normalized_sequence if normalized_sequence else _OMITTED
    raise PromptValidationError("Prompt input contains an unsupported value")


def _input_hash(value: JsonObject) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_json_dump(value: JsonObject) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    )


def _escape_structure_markers(value: str) -> str:
    return (
        value.replace("#", "\\u0023")
        .replace("=", "\\u003d")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("[", "\\u005b")
        .replace("]", "\\u005d")
        .replace(":", "\\u003a")
    )
