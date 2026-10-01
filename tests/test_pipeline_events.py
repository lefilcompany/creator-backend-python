from uuid import uuid4

import pytest
from pydantic import ValidationError

from creator.domain.pipeline_events import PipelineEvent, PipelineEventType
from creator.workers import pipeline_events


def test_pipeline_event_is_transport_neutral_and_reference_based() -> None:
    event = PipelineEvent(
        event_id=uuid4(),
        event_type=PipelineEventType.BUSINESS_COMPLETED,
        event_version="1.0",
        workspace_id=uuid4(),
        run_id=uuid4(),
        step_id=uuid4(),
        correlation_id=uuid4(),
        output_hash="a" * 64,
        payload_ref={"schema": "BusinessOutput", "version": "1.0"},
    )
    assert event.payload_ref["schema"] == "BusinessOutput"
    assert "prompt" not in event.payload_ref


def test_pipeline_event_rejects_unknown_version() -> None:
    with pytest.raises(ValidationError):
        PipelineEvent(
            event_id=uuid4(),
            event_type=PipelineEventType.PLANNER_COMPLETED,
            event_version="2.0",
            workspace_id=uuid4(),
            run_id=uuid4(),
            correlation_id=uuid4(),
        )


def test_stage_events_route_to_the_matching_checkpoint(monkeypatch) -> None:
    calls: list[str] = []

    def fake_runner(run_id: str, request_id: str, stage: str) -> None:
        calls.append(stage)

    monkeypatch.setattr(pipeline_events, "run_image_agent_workflow", fake_runner)
    base = {
        "event_id": uuid4(),
        "event_version": "1.0",
        "workspace_id": uuid4(),
        "run_id": uuid4(),
        "correlation_id": uuid4(),
    }
    for event_type, expected in (
        (PipelineEventType.WORKFLOW_STARTED, "BUSINESS"),
        (PipelineEventType.BUSINESS_COMPLETED, "PLANNER"),
        (PipelineEventType.PLANNER_COMPLETED, "WRITER"),
        (PipelineEventType.WRITER_COMPLETED, "ARTIST"),
        (PipelineEventType.ARTIST_COMPLETED, "REVIEWER"),
        (PipelineEventType.WRITER_REFINEMENT_REQUESTED, "WRITER"),
    ):
        pipeline_events.handle_pipeline_event({**base, "event_type": event_type})
        assert calls[-1] == expected
