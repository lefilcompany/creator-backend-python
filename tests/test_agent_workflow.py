from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from creator.application.agent_image_workflow import (
    AgentWorkflowDecisionError,
    AgentWorkflowIdempotencyConflictError,
    AgentWorkflowInputError,
    AgentWorkflowQueueError,
    StartImageWorkflowCommand,
    decide_image_workflow,
    start_image_workflow,
)
from creator.config import Settings
from creator.domain.agent_workflow import (
    AgentWorkflowStatus,
    AgentWorkflowStepRole,
    AgentWorkflowStepStatus,
    HumanReviewMode,
    WorkflowDecision,
    can_transition_agent_workflow,
)
from creator.repositories import (
    AgentWorkflowRunRecord,
    AgentWorkflowStepRecord,
    ContentRecord,
    ImageRecord,
)
from creator.services.agents.contracts import AgentExecutionContext, BusinessOutput
from creator.services.agents.runner import StructuredAgentRunner
from creator.services.ai.image_provider import ImageGenerationResult
from creator.services.ai.reviewer import UnconfiguredMultimodalImageReviewer
from creator.services.storage.provider import StorageValidationError

WORKSPACE_ID = UUID("10000000-0000-0000-0000-000000000001")
BRAND_ID = UUID("31000000-0000-0000-0000-000000000001")
USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def _run(
    status: AgentWorkflowStatus = AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW,
) -> AgentWorkflowRunRecord:
    now = datetime.now(UTC)
    return AgentWorkflowRunRecord(
        id=UUID("41000000-0000-0000-0000-000000000001"),
        workspace_id=WORKSPACE_ID,
        content_id=UUID("21000000-0000-0000-0000-000000000001"),
        brand_id=BRAND_ID,
        requested_by_user_id=USER_ID,
        idempotency_key="key",
        request_fingerprint="fingerprint",
        status=status,
        human_review=HumanReviewMode.OPTIONAL,
        max_refinements=3,
        refinement_count=0,
        current_step="REVIEWER",
        input={"campaign": "Launch", "persona": "Creators", "quantity": 1},
        final_image_ids=[str(UUID("52000000-0000-0000-0000-000000000001"))],
        failure_code=None,
        failure_message=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
        deleted_at=None,
    )


class FakeBrand:
    workspace_id = WORKSPACE_ID
    id = BRAND_ID


class FakeContents:
    def add(self, **kwargs: object) -> ContentRecord:
        now = datetime.now(UTC)
        return ContentRecord(
            id=UUID("21000000-0000-0000-0000-000000000001"),
            workspace_id=WORKSPACE_ID,
            created_by_user_id=USER_ID,
            content_type="IMAGE",
            title=str(kwargs.get("title")),
            payload=kwargs.get("payload", {}),
            created_at=now,
            updated_at=now,
            deleted_at=None,
            brand_id=BRAND_ID,
            project_id=None,
        )


class FakeWorkflowRepository:
    def __init__(self, run: AgentWorkflowRunRecord | None = None) -> None:
        self.run = run
        self.updated_input: dict[str, object] | None = None
        self.transitions: list[tuple[UUID, AgentWorkflowStatus]] = []

    def get_by_idempotency(self, **kwargs: object) -> AgentWorkflowRunRecord | None:
        return self.run

    def create_run(self, **kwargs: object) -> AgentWorkflowRunRecord:
        self.run = _run(AgentWorkflowStatus.PENDING)
        return self.run

    def get_for_user(self, **kwargs: object) -> AgentWorkflowRunRecord | None:
        return self.run

    def update_input(self, run_id: UUID, input: dict[str, object]) -> AgentWorkflowRunRecord:
        self.updated_input = input
        assert self.run is not None
        return self.run

    def transition(
        self, run_id: UUID, target: AgentWorkflowStatus, **kwargs: object
    ) -> AgentWorkflowRunRecord:
        self.transitions.append((run_id, target))
        assert self.run is not None
        return self.run


class FakeUow:
    def __init__(
        self, run: AgentWorkflowRunRecord | None = None, *, brand: object | None = FakeBrand()
    ) -> None:
        self.brands = type("Brands", (), {"get_for_user": lambda self, **kwargs: brand})()
        self.contents = FakeContents()
        self.agent_workflows = FakeWorkflowRepository(run)
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class FakeQueue:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[UUID] = []

    def enqueue_agent_workflow(self, *, run_id: UUID, request_id: UUID) -> object:
        self.calls.append(run_id)
        if self.error:
            raise self.error
        return object()


def test_agent_workflow_transitions_are_explicit() -> None:
    assert can_transition_agent_workflow(AgentWorkflowStatus.PENDING, AgentWorkflowStatus.RUNNING)
    assert can_transition_agent_workflow(
        AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW, AgentWorkflowStatus.REJECTED
    )
    assert not can_transition_agent_workflow(
        AgentWorkflowStatus.COMPLETED, AgentWorkflowStatus.RUNNING
    )


def test_start_image_workflow_derives_workspace_and_is_idempotent() -> None:
    uow = FakeUow()
    queue = FakeQueue()
    command = StartImageWorkflowCommand(
        brand_id=BRAND_ID,
        campaign="Launch",
        persona="Creators",
        quantity=1,
        extra_instructions=None,
        human_review="AUTO",
        max_refinements=None,
        extensions={},
        idempotency_key="key",
        request_id=uuid4(),
    )
    run = start_image_workflow(
        unit_of_work=uow,
        queue=queue,
        settings=Settings(agent_workflow_max_refinements=3),
        user=type("User", (), {"id": USER_ID})(),
        command=command,
    )
    assert run.status == AgentWorkflowStatus.PENDING
    assert queue.calls == [run.id]
    assert uow.commits == 1


def test_start_image_workflow_rejects_conflicts_limits_and_queue_failures() -> None:
    user = type("User", (), {"id": USER_ID})()
    command = StartImageWorkflowCommand(
        brand_id=BRAND_ID,
        campaign="Launch",
        persona="Creators",
        quantity=1,
        extra_instructions=None,
        human_review="AUTO",
        max_refinements=3,
        extensions={},
        idempotency_key="key",
        request_id=uuid4(),
    )
    conflict = FakeUow(_run(AgentWorkflowStatus.PENDING))
    with pytest.raises(AgentWorkflowIdempotencyConflictError):
        start_image_workflow(
            unit_of_work=conflict,
            queue=FakeQueue(),
            settings=Settings(agent_workflow_max_refinements=3),
            user=user,
            command=command,
        )
    limited = FakeUow()
    with pytest.raises(AgentWorkflowInputError):
        start_image_workflow(
            unit_of_work=limited,
            queue=FakeQueue(),
            settings=Settings(agent_workflow_max_refinements=2),
            user=user,
            command=command,
        )
    with pytest.raises(AgentWorkflowQueueError):
        start_image_workflow(
            unit_of_work=FakeUow(),
            queue=FakeQueue(RuntimeError("redis")),
            settings=Settings(agent_workflow_max_refinements=3),
            user=user,
            command=command,
        )


def test_human_decisions_approve_reject_and_refine() -> None:
    user = type("User", (), {"id": USER_ID})()
    request_id = uuid4()
    approved = FakeUow(_run())
    result = decide_image_workflow(
        unit_of_work=approved,
        queue=FakeQueue(),
        run_id=approved.agent_workflows.run.id,
        user=user,
        request_id=request_id,
        decision=WorkflowDecision.APPROVE,
        feedback=None,
    )
    assert result.status == AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW
    refined = FakeUow(_run())
    queue = FakeQueue()
    decide_image_workflow(
        unit_of_work=refined,
        queue=queue,
        run_id=refined.agent_workflows.run.id,
        user=user,
        request_id=request_id,
        decision=WorkflowDecision.REFINE,
        feedback="Use more contrast",
    )
    assert (
        refined.agent_workflows.updated_input
        and refined.agent_workflows.updated_input["human_feedback"] == "Use more contrast"
    )
    assert queue.calls
    rejected = FakeUow(_run())
    decide_image_workflow(
        unit_of_work=rejected,
        queue=FakeQueue(),
        run_id=rejected.agent_workflows.run.id,
        user=user,
        request_id=request_id,
        decision=WorkflowDecision.REJECT,
        feedback="Not aligned",
    )
    assert rejected.agent_workflows.transitions[-1][1] == AgentWorkflowStatus.REJECTED


def test_human_refine_requires_feedback_and_waiting_state() -> None:
    user = type("User", (), {"id": USER_ID})()
    uow = FakeUow(_run())
    with pytest.raises(AgentWorkflowDecisionError):
        decide_image_workflow(
            unit_of_work=uow,
            queue=FakeQueue(),
            run_id=uow.agent_workflows.run.id,
            user=user,
            request_id=uuid4(),
            decision=WorkflowDecision.REFINE,
            feedback=None,
        )
    invalid = FakeUow(_run(AgentWorkflowStatus.COMPLETED))
    with pytest.raises(AgentWorkflowDecisionError):
        decide_image_workflow(
            unit_of_work=invalid,
            queue=FakeQueue(),
            run_id=invalid.agent_workflows.run.id,
            user=user,
            request_id=uuid4(),
            decision=WorkflowDecision.APPROVE,
            feedback=None,
        )


class FakeLLM:
    model = "fake-model"

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        return (
            '{"brand_summary":"A","voice":"Clear","visual_direction":"Bright",'
            '"constraints":[],"knowledge_sources":[]}'
        )


def test_structured_agent_runner_validates_json_and_prompt_is_deterministic() -> None:
    context = AgentExecutionContext(
        workspace_id=WORKSPACE_ID,
        brand_id=BRAND_ID,
        role=AgentWorkflowStepRole.BUSINESS,
        inputs={"campaign": "Launch"},
        prompt_template_id="agent.business.v1",
        prompt_template_version="1.0",
    )
    first = StructuredAgentRunner(FakeLLM()).run(context, BusinessOutput)
    second = StructuredAgentRunner(FakeLLM()).run(context, BusinessOutput)
    assert first.input_hash == second.input_hash
    assert first.output.brand_summary == "A"


def test_unconfigured_reviewer_fails_closed() -> None:
    with pytest.raises(RuntimeError):
        UnconfiguredMultimodalImageReviewer().review(None)  # type: ignore[arg-type]


def test_reviewer_terminal_codes_are_preserved_for_a_rejection() -> None:
    from creator.workers.agent_workflow import _failure_code

    assert _failure_code(RuntimeError("REVIEW_QUALITY_REJECTED")) == "REVIEW_QUALITY_REJECTED"
    assert _failure_code(RuntimeError("REVIEW_SAFETY_REJECTED")) == "REVIEW_SAFETY_REJECTED"


def test_storage_validation_type_remains_explicit() -> None:
    assert issubclass(StorageValidationError, RuntimeError)


class WorkflowLLM:
    model = "fake-workflow-model"

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        if "BUSINESS" in prompt:
            return (
                '{"brand_summary":"Brand","voice":"Clear",'
                '"visual_direction":"Bright","constraints":[],"knowledge_sources":[]}'
            )
        if "PLANNER" in prompt:
            return (
                '{"posts":[{"theme":"Launch","objective":"Awareness",'
                '"big_idea":"Start","main_message":"Discover"}]}'
            )
        return (
            '{"caption":"Discover","direction":{"briefing":"Bright launch",'
            '"keywords":["bright"],"copy":"Discover",'
            '"visual_prompt":"A bright product image"}}'
        )


class WorkflowRepo:
    def __init__(self, run: AgentWorkflowRunRecord) -> None:
        self.run = run
        self.steps: list[AgentWorkflowStepRecord] = []
        self.transitions: list[AgentWorkflowStatus] = []

    def get_internal(self, run_id: UUID) -> AgentWorkflowRunRecord | None:
        return self.run if run_id == self.run.id else None

    def transition(
        self, run_id: UUID, target: AgentWorkflowStatus, **kwargs: object
    ) -> AgentWorkflowRunRecord:
        self.transitions.append(target)
        self.run = replace(
            self.run,
            status=target,
            current_step=kwargs.get("current_step", self.run.current_step),
            refinement_count=kwargs.get("refinement_count", self.run.refinement_count),
            final_image_ids=kwargs.get("final_image_ids", self.run.final_image_ids),
        )
        return self.run

    def list_steps_internal(self, run_id: UUID) -> list[AgentWorkflowStepRecord]:
        return list(self.steps)

    def add_step(self, **kwargs: object) -> AgentWorkflowStepRecord:
        now = datetime.now(UTC)
        step = AgentWorkflowStepRecord(
            id=uuid4(),
            run_id=self.run.id,
            workspace_id=WORKSPACE_ID,
            sequence_number=len(self.steps) + 1,
            role=kwargs["role"],
            status=AgentWorkflowStepStatus.RUNNING,
            attempt=1,
            input=kwargs["input"],
            output={},
            prompt=None,
            prompt_template_id=None,
            prompt_template_version=None,
            input_hash=None,
            provider=None,
            model=None,
            decision=None,
            error_code=None,
            error_message=None,
            started_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.steps.append(step)
        return step

    def complete_step(self, step_id: UUID, **kwargs: object) -> AgentWorkflowStepRecord:
        return next(step for step in self.steps if step.id == step_id)

    def fail_step(self, step_id: UUID, **kwargs: object) -> None:
        return None


class WorkerUow:
    shared_repo: WorkflowRepo

    def __init__(self) -> None:
        self.agent_workflows = self.shared_repo
        self.users = SimpleNamespace(
            get_by_id=lambda user_id: SimpleNamespace(id=USER_ID, external_id="principal")
        )
        self.brands = SimpleNamespace(
            get_for_user=lambda **kwargs: SimpleNamespace(
                id=BRAND_ID,
                workspace_id=WORKSPACE_ID,
                name="Brand",
                description="Description",
                brand_voice="Clear",
                metadata={},
            )
        )
        self.brand_settings = SimpleNamespace(get_for_user=lambda **kwargs: None)
        self.image_generations = SimpleNamespace(
            create_image_generation=lambda **kwargs: SimpleNamespace(id=uuid4()),
            claim_pending_by_id=lambda job_id: SimpleNamespace(job=SimpleNamespace(id=job_id)),
        )

    def __enter__(self) -> WorkerUow:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def commit(self) -> None:
        return None


def test_worker_runs_specialists_and_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    import creator.workers.agent_workflow as worker

    run = replace(_run(AgentWorkflowStatus.PENDING), human_review=HumanReviewMode.AUTO)
    repo = WorkflowRepo(run)
    WorkerUow.shared_repo = repo
    image_id = UUID("52000000-0000-0000-0000-000000000009")
    image = ImageRecord(
        id=image_id,
        workspace_id=WORKSPACE_ID,
        content_id=run.content_id,
        generation_id=uuid4(),
        version_number=1,
        storage_path="workflow/image.png",
        public_url="https://example.com/image.png",
        mime_type="image/png",
        width=512,
        height=512,
        model="fake-image",
        prompt="A bright product image",
        metadata={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )

    class Reviewer:
        def review(self, request: object) -> object:
            return SimpleNamespace(decision="APPROVED", score=1.0, feedback=(), safety_issues=())

    monkeypatch.setattr(worker, "SqlAlchemyUnitOfWork", WorkerUow)
    monkeypatch.setattr(worker, "get_settings", lambda: Settings(gemini_api_key=None))
    monkeypatch.setattr(worker, "create_llm_provider", lambda settings: WorkflowLLM())
    monkeypatch.setattr(worker, "create_image_reviewer", lambda settings: Reviewer())
    monkeypatch.setattr(
        worker,
        "create_image_generator",
        lambda settings: SimpleNamespace(
            generate=lambda request: ImageGenerationResult(
                image_bytes=b"image",
                mime_type="image/png",
                width=512,
                height=512,
                model="fake-image",
                prompt="A bright product image",
                metadata={},
            )
        ),
    )
    monkeypatch.setattr(worker, "create_storage_provider", lambda settings: object())
    monkeypatch.setattr(worker, "persist_generated_image", lambda **kwargs: image)
    monkeypatch.setattr(
        worker,
        "create_semantic_retriever",
        lambda settings: SimpleNamespace(search=lambda *args, **kwargs: []),
    )

    worker.run_image_agent_workflow(str(run.id), "request")

    assert repo.run.status == AgentWorkflowStatus.COMPLETED
    assert repo.run.final_image_ids == [str(image_id)]
    assert [step.role for step in repo.steps] == [
        AgentWorkflowStepRole.BUSINESS,
        AgentWorkflowStepRole.PLANNER,
        AgentWorkflowStepRole.WRITER,
        AgentWorkflowStepRole.ARTIST,
        AgentWorkflowStepRole.REVIEWER,
    ]
