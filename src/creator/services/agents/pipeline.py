"""Versioned, typed hand-off contracts for the specialist pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from creator.services.agents.contracts import (
    BusinessOutput,
    PlannerOutput,
    ReviewOutput,
    WriterOutput,
)


class PipelineContractError(ValueError):
    """The predecessor cannot legally be consumed by the next specialist."""


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    brand_id: UUID
    correlation_id: UUID
    source_step: str
    source_hash: str = Field(min_length=64, max_length=64)
    context_hash: str = Field(min_length=64, max_length=64)


class PipelineEnvelope(BaseModel):
    """The only state handed between agents; prompts are deliberately absent."""

    model_config = ConfigDict(extra="forbid")

    schema_name: str
    schema_version: str
    payload: dict[str, Any]
    provenance: Provenance

    @property
    def payload_hash(self) -> str:
        return stable_hash(self.payload)


@dataclass(frozen=True, slots=True)
class PipelineEdge:
    predecessor: str
    successor: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    version: str
    required_fields: tuple[str, ...]
    allowed_transform: str


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def context_hash(context: dict[str, Any]) -> str:
    return stable_hash(context)


EDGES: tuple[PipelineEdge, ...] = (
    PipelineEdge(
        "BUSINESS",
        "PLANNER",
        BusinessOutput,
        PlannerOutput,
        "1.0",
        ("brand_summary", "voice", "visual_direction"),
        "identity",
    ),
    PipelineEdge(
        "PLANNER", "WRITER", PlannerOutput, WriterOutput, "1.0", ("posts",), "select_post"
    ),
    PipelineEdge(
        "WRITER",
        "ARTIST",
        WriterOutput,
        WriterOutput,
        "1.0",
        ("caption", "direction"),
        "identity",
    ),
    PipelineEdge(
        "ARTIST", "REVIEWER", WriterOutput, ReviewOutput, "1.0", ("direction",), "identity"
    ),
    PipelineEdge(
        "REVIEWER",
        "WRITER",
        ReviewOutput,
        WriterOutput,
        "1.0",
        ("decision", "feedback"),
        "feedback_only",
    ),
)


def edge(predecessor: str, successor: str) -> PipelineEdge:
    for candidate in EDGES:
        if candidate.predecessor == predecessor and candidate.successor == successor:
            return candidate
    raise PipelineContractError(f"Unsupported pipeline edge {predecessor}->{successor}")


def emit(
    *,
    role: str,
    output: BaseModel,
    workspace_id: UUID,
    brand_id: UUID,
    correlation_id: UUID,
    context_digest: str,
) -> PipelineEnvelope:
    return PipelineEnvelope(
        schema_name=output.__class__.__name__,
        schema_version="1.0",
        payload=output.model_dump(mode="json"),
        provenance=Provenance(
            workspace_id=workspace_id,
            brand_id=brand_id,
            correlation_id=correlation_id,
            source_step=role,
            source_hash=stable_hash(output.model_dump(mode="json")),
            context_hash=context_digest,
        ),
    )


def consume(
    envelope: PipelineEnvelope,
    *,
    predecessor: str,
    successor: str,
    workspace_id: UUID,
    output_schema: type[BaseModel],
) -> BaseModel:
    contract = edge(predecessor, successor)
    if envelope.provenance.workspace_id != workspace_id:
        raise PipelineContractError("Workspace mismatch")
    if envelope.schema_version != contract.version:
        raise PipelineContractError("Schema version mismatch")
    try:
        result = contract.input_schema.model_validate(envelope.payload)
    except Exception as exc:
        raise PipelineContractError("Invalid or incomplete predecessor output") from exc
    if output_schema is not contract.output_schema and successor not in {"WRITER", "ARTIST"}:
        raise PipelineContractError("Output schema is incompatible with edge")
    return result


def refinement_feedback(envelope: PipelineEnvelope, *, workspace_id: UUID) -> dict[str, Any]:
    review = consume(
        envelope,
        predecessor="REVIEWER",
        successor="WRITER",
        workspace_id=workspace_id,
        output_schema=WriterOutput,
    )
    if not isinstance(review, ReviewOutput):
        raise PipelineContractError("Reviewer output is not structured feedback")
    return {
        "feedback": list(review.feedback),
        "review_hash": envelope.provenance.source_hash,
        "precedence": "REVIEWER",
        "correlation_id": str(envelope.provenance.correlation_id),
    }


def new_correlation_id() -> UUID:
    return uuid4()
