from uuid import uuid4

import pytest

from creator.services.agents.contracts import BusinessOutput, PlannerOutput, ReviewOutput
from creator.services.agents.pipeline import (
    PipelineContractError,
    PipelineEnvelope,
    consume,
    context_hash,
    emit,
    refinement_feedback,
)


def _business() -> BusinessOutput:
    return BusinessOutput(brand_summary="B", voice="V", visual_direction="D")


def test_handoff_is_structured_and_workspace_bound() -> None:
    workspace, brand, correlation = uuid4(), uuid4(), uuid4()
    envelope = emit(
        role="BUSINESS",
        output=_business(),
        workspace_id=workspace,
        brand_id=brand,
        correlation_id=correlation,
        context_digest=context_hash({"campaign": "launch"}),
    )
    assert (
        consume(
            envelope,
            predecessor="BUSINESS",
            successor="PLANNER",
            workspace_id=workspace,
            output_schema=PlannerOutput,
        )
        == _business()
    )
    assert envelope.provenance.context_hash == context_hash({"campaign": "launch"})

    with pytest.raises(PipelineContractError, match="Workspace"):
        consume(
            envelope,
            predecessor="BUSINESS",
            successor="PLANNER",
            workspace_id=uuid4(),
            output_schema=PlannerOutput,
        )


def test_invalid_or_mismatched_schema_blocks_next_edge() -> None:
    workspace, brand = uuid4(), uuid4()
    envelope = PipelineEnvelope(
        schema_name="BusinessOutput",
        schema_version="9.0",
        payload={"voice": "x"},
        provenance={
            "workspace_id": workspace,
            "brand_id": brand,
            "correlation_id": uuid4(),
            "source_step": "BUSINESS",
            "source_hash": "a" * 64,
            "context_hash": "b" * 64,
        },
    )
    with pytest.raises(PipelineContractError):
        consume(
            envelope,
            predecessor="BUSINESS",
            successor="PLANNER",
            workspace_id=workspace,
            output_schema=PlannerOutput,
        )


def test_reviewer_feedback_preserves_precedence_and_origin() -> None:
    workspace, brand, correlation = uuid4(), uuid4(), uuid4()
    review = ReviewOutput(
        decision="REFINE",
        score=0.7,
        brand_adherence=0.8,
        brief_adherence=0.6,
        technical_quality=0.7,
        feedback=["More contrast"],
    )
    envelope = emit(
        role="REVIEWER",
        output=review,
        workspace_id=workspace,
        brand_id=brand,
        correlation_id=correlation,
        context_digest=context_hash({"campaign": "launch"}),
    )
    feedback = refinement_feedback(envelope, workspace_id=workspace)
    assert feedback["feedback"] == ["More contrast"]
    assert feedback["precedence"] == "REVIEWER"
    assert feedback["review_hash"] == envelope.provenance.source_hash
