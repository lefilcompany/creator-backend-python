from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import cast
from uuid import UUID, uuid4

from pydantic import BaseModel

from creator.application.image_storage import GeneratedImage, persist_generated_image
from creator.config import get_settings
from creator.domain.agent_workflow import (
    AgentWorkflowStatus,
    AgentWorkflowStepRole,
)
from creator.domain.pipeline_events import PipelineEvent, PipelineEventType
from creator.infrastructure.storage import create_storage_provider
from creator.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from creator.repositories import AgentWorkflowRunRecord, ImageRecord, JsonObject, UserRecord
from creator.services.agents.contracts import (
    AgentExecutionContext,
    BusinessOutput,
    PlannerOutput,
    WriterOutput,
)
from creator.services.agents.factory import create_multi_agent_orchestrator
from creator.services.agents.orchestrator import MultiAgentOrchestrator
from creator.services.agents.pipeline import (
    PipelineEnvelope,
    consume,
    context_hash,
    emit,
    stable_hash,
)
from creator.services.ai.factory import create_image_reviewer
from creator.services.ai.image_provider import (
    ImageGenerationRequest,
    ImageGenerationResult,
    create_image_generator,
)
from creator.services.ai.reviewer import ImageReviewRequest
from creator.services.retrieval.factory import (
    RetrievalProviderNotConfiguredError,
    create_semantic_retriever,
)

logger = logging.getLogger(__name__)


def run_image_agent_workflow(
    run_id: str, request_id: str | None = None, stage: str | None = None
) -> None:
    try:
        parsed_run_id = UUID(run_id)
    except ValueError:
        return
    started_at = time.perf_counter()
    settings = get_settings()
    try:
        run, user = _claim_run(parsed_run_id, stage=stage)
        if run is None or user is None:
            return
        brand, brand_settings = _load_brand_context(run, user.id)
        orchestrator = create_multi_agent_orchestrator(settings)
        completed_business = _completed_stage_output(run.id, AgentWorkflowStepRole.BUSINESS)
        if completed_business is None:
            business = _execute_agent_step(
                run_id=run.id,
                role=AgentWorkflowStepRole.BUSINESS,
                inputs={
                    "workflow": run.input,
                    "brand": brand,
                    "brand_settings": brand_settings,
                    "knowledge": _knowledge(run),
                },
                orchestrator=orchestrator,
                output_model=BusinessOutput,
            )
        else:
            business = cast(BusinessOutput, completed_business)
        correlation_id = UUID(str(run.id))
        shared_context = {
            "workspace_id": str(run.workspace_id),
            "brand_id": str(run.brand_id),
            "campaign": run.input.get("campaign", ""),
            "persona": run.input.get("persona", {}),
            "feedback": run.input.get("human_feedback", ""),
            "knowledge": _knowledge(run),
        }
        business_envelope = emit(
            role="BUSINESS",
            output=business,
            workspace_id=run.workspace_id,
            brand_id=run.brand_id,
            correlation_id=correlation_id,
            context_digest=context_hash(shared_context),
        )
        if stage == "BUSINESS":
            _advance_stage(run.id, AgentWorkflowStatus.RUNNING, "PLANNER")
            return
        planner = _completed_stage_output(run.id, AgentWorkflowStepRole.PLANNER)
        if planner is None:
            planner = _execute_agent_step(
                run_id=run.id,
                role=AgentWorkflowStepRole.PLANNER,
                inputs={
                    "workflow": run.input,
                    "predecessor": {
                        "schema": "business.output.v1",
                        "payload": business_envelope.payload,
                        "payload_hash": business_envelope.payload_hash,
                        "context_hash": business_envelope.provenance.context_hash,
                    },
                },
                orchestrator=orchestrator,
                output_model=PlannerOutput,
            )
        planner_envelope = emit(
            role="PLANNER",
            output=planner,
            workspace_id=run.workspace_id,
            brand_id=run.brand_id,
            correlation_id=correlation_id,
            context_digest=business_envelope.provenance.context_hash,
        )
        consume(
            business_envelope,
            predecessor="BUSINESS",
            successor="PLANNER",
            workspace_id=run.workspace_id,
            output_schema=PlannerOutput,
        )
        quantity_value = run.input.get("quantity", 1)
        quantity = quantity_value if isinstance(quantity_value, int) else 1
        validated_planner = cast(
            PlannerOutput,
            consume(
                planner_envelope,
                predecessor="PLANNER",
                successor="WRITER",
                workspace_id=run.workspace_id,
                output_schema=WriterOutput,
            ),
        )
        posts = validated_planner.posts[:quantity]
        if stage == "PLANNER":
            _advance_stage(run.id, AgentWorkflowStatus.RUNNING, "WRITER")
            return
        if stage == "WRITER":
            for index, post in enumerate(posts, start=1):
                _execute_agent_step(
                    run_id=run.id,
                    role=AgentWorkflowStepRole.WRITER,
                    inputs={
                        "business_context": business.model_dump(mode="json"),
                        "predecessor": {
                            "schema": "planner.output.v1",
                            "payload": planner_envelope.payload,
                            "payload_hash": planner_envelope.payload_hash,
                            "context_hash": planner_envelope.provenance.context_hash,
                        },
                        "post": post.model_dump(mode="json"),
                        "feedback": str(run.input.get("human_feedback", "")),
                        "item": index,
                    },
                    orchestrator=orchestrator,
                    output_model=WriterOutput,
                )
            _advance_stage(run.id, AgentWorkflowStatus.RUNNING, "ARTIST")
            return
        if stage == "ARTIST":
            _run_artist_stage(run, user, settings)
            return
        if stage == "REVIEWER":
            _run_reviewer_stage(run, user, business, settings)
            return
        final_image_ids: list[str] = []
        feedback = str(run.input.get("human_feedback", ""))
        for index, post in enumerate(posts, start=1):
            accepted_image = _run_post_until_accepted(
                run=run,
                user=user,
                index=index,
                business=business,
                planner_envelope=planner_envelope,
                post=post.model_dump(mode="json"),
                feedback=feedback,
                orchestrator=orchestrator,
                settings=settings,
            )
            final_image_ids.append(str(accepted_image))

        with SqlAlchemyUnitOfWork() as unit_of_work:
            latest = unit_of_work.agent_workflows.get_internal(run.id)
            if latest is None:
                return
            if latest.human_review.value == "OPTIONAL":
                unit_of_work.agent_workflows.transition(
                    run.id,
                    AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW,
                    current_step="REVIEWER",
                    final_image_ids=final_image_ids,
                )
            else:
                unit_of_work.agent_workflows.transition(
                    run.id,
                    AgentWorkflowStatus.COMPLETED,
                    current_step="DELIVERY",
                    final_image_ids=final_image_ids,
                )
            unit_of_work.commit()
        logger.info(
            "image_agent_workflow_completed",
            extra={
                "run_id": str(run.id),
                "request_id": request_id,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )
    except Exception as error:
        logger.exception(
            "image_agent_workflow_failed", extra={"run_id": run_id, "request_id": request_id}
        )
        code = _failure_code(error)
        if code in {"REVIEW_QUALITY_REJECTED", "REVIEW_SAFETY_REJECTED"}:
            _reject_workflow(parsed_run_id, code, "Image was rejected by the Reviewer")
        else:
            _fail_workflow(parsed_run_id, code, "Image agent workflow failed")


def _claim_run(
    run_id: UUID, *, stage: str | None = None
) -> tuple[AgentWorkflowRunRecord | None, UserRecord | None]:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        run = unit_of_work.agent_workflows.get_internal(run_id)
        if run is None:
            return None, None
        allowed_statuses = {AgentWorkflowStatus.PENDING, AgentWorkflowStatus.REFINING}
        if stage in {"PLANNER", "WRITER"}:
            allowed_statuses.add(AgentWorkflowStatus.RUNNING)
        if run.status not in allowed_statuses:
            return None, None
        user = (
            unit_of_work.users.get_by_id(run.requested_by_user_id)
            if run.requested_by_user_id
            else None
        )
        if user is None:
            return None, None
        if run.status != AgentWorkflowStatus.RUNNING:
            run = unit_of_work.agent_workflows.transition(
                run_id, AgentWorkflowStatus.RUNNING, current_step=stage or "BUSINESS"
            )
            unit_of_work.commit()
        return run, user


def _completed_stage_output(
    run_id: UUID, role: AgentWorkflowStepRole
) -> BusinessOutput | PlannerOutput | None:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        steps = unit_of_work.agent_workflows.list_steps_internal(run_id)
    for step in reversed(steps):
        if step.role == role and step.status.value == "COMPLETED" and step.output:
            if role == AgentWorkflowStepRole.BUSINESS:
                return BusinessOutput.model_validate(step.output)
            return PlannerOutput.model_validate(step.output)
    return None


def _advance_stage(run_id: UUID, status: AgentWorkflowStatus, current_step: str) -> None:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        unit_of_work.agent_workflows.transition(run_id, status, current_step=current_step)
        unit_of_work.commit()


def _run_artist_stage(
    run: AgentWorkflowRunRecord,
    user: UserRecord,
    settings: object,
) -> None:
    """Consume persisted Writer outputs and persist Artist outputs."""
    from creator.config import Settings

    typed_settings = settings if isinstance(settings, Settings) else get_settings()
    with SqlAlchemyUnitOfWork() as unit_of_work:
        writer_steps = [
            step
            for step in unit_of_work.agent_workflows.list_steps_internal(run.id)
            if step.role == AgentWorkflowStepRole.WRITER
            and step.status.value == "COMPLETED"
            and step.output
        ]
    if not writer_steps:
        raise RuntimeError("Writer output is missing for Artist stage")
    for index, step in enumerate(writer_steps, start=1):
        with SqlAlchemyUnitOfWork() as unit_of_work:
            existing_artist = [
                candidate
                for candidate in unit_of_work.agent_workflows.list_steps_internal(run.id)
                if candidate.role == AgentWorkflowStepRole.ARTIST
                and candidate.status.value == "COMPLETED"
                and candidate.predecessor_step_id == step.id
            ]
        if existing_artist:
            continue
        writer = WriterOutput.model_validate(step.output)
        _generate_workflow_image(
            run=run,
            user=user,
            writer=writer,
            predecessor_step_id=step.id,
            index=index,
            refinement_count=run.refinement_count,
            settings=typed_settings,
        )
    _advance_stage(run.id, AgentWorkflowStatus.RUNNING, "REVIEWER")


def _run_reviewer_stage(
    run: AgentWorkflowRunRecord,
    user: UserRecord,
    business: BusinessOutput,
    settings: object,
) -> None:
    """Consume persisted Artist references and run Reviewer independently."""
    from creator.config import Settings

    typed_settings = settings if isinstance(settings, Settings) else get_settings()
    with SqlAlchemyUnitOfWork() as unit_of_work:
        artist_steps = [
            step
            for step in unit_of_work.agent_workflows.list_steps_internal(run.id)
            if step.role == AgentWorkflowStepRole.ARTIST
            and step.status.value == "COMPLETED"
            and step.output
        ]
        writer_steps = [
            step
            for step in unit_of_work.agent_workflows.list_steps_internal(run.id)
            if step.role == AgentWorkflowStepRole.WRITER
            and step.status.value == "COMPLETED"
            and step.output
        ]
    if not artist_steps or len(writer_steps) < len(artist_steps):
        raise RuntimeError("Artist output is missing for Reviewer stage")
    reviewer = create_image_reviewer(typed_settings)
    storage = create_storage_provider(typed_settings)
    final_image_ids: list[str] = []
    for index, artist_step in enumerate(artist_steps, start=1):
        image_id = UUID(str(artist_step.output["image_id"]))
        with SqlAlchemyUnitOfWork() as unit_of_work:
            image_record = unit_of_work.image_generations.get_image_for_user(
                user_id=user.id, image_id=image_id
            )
        if image_record is None or image_record.workspace_id != run.workspace_id:
            raise RuntimeError("Reviewer image is outside the workflow Workspace")
        image_bytes = storage.download(
            image_record.storage_path, max_bytes=typed_settings.storage_max_object_bytes
        )
        writer = WriterOutput.model_validate(writer_steps[index - 1].output)
        review = reviewer.review(
            ImageReviewRequest(
                image_bytes=image_bytes,
                mime_type=image_record.mime_type,
                prompt=writer.direction.visual_prompt,
                briefing=writer.direction.briefing,
                brand_context=business.model_dump(mode="json"),
            )
        )
        _persist_review_step(run, index, writer, review, predecessor_step_id=artist_step.id)
        if review.safety_issues:
            raise RuntimeError("REVIEW_SAFETY_REJECTED")
        if review.decision == "REJECTED":
            raise RuntimeError("REVIEW_QUALITY_REJECTED")
        if review.decision == "REFINE":
            _request_writer_refinement(run, review)
            return
        if review.decision != "APPROVED":
            raise RuntimeError("REVIEW_INVALID_DECISION")
        final_image_ids.append(str(image_record.id))
    with SqlAlchemyUnitOfWork() as unit_of_work:
        latest = unit_of_work.agent_workflows.get_internal(run.id)
        if latest is None:
            raise RuntimeError("Agent workflow not found")
        target = (
            AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW
            if latest.human_review.value == "OPTIONAL"
            else AgentWorkflowStatus.COMPLETED
        )
        current_step = (
            "REVIEWER" if target == AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW else "DELIVERY"
        )
        unit_of_work.agent_workflows.transition(
            run.id, target, current_step=current_step, final_image_ids=final_image_ids
        )
        unit_of_work.commit()


def _request_writer_refinement(run: AgentWorkflowRunRecord, review: object) -> None:
    feedback = "; ".join(getattr(review, "feedback", ())) or "Improve adherence to the review."
    with SqlAlchemyUnitOfWork() as unit_of_work:
        updated_input = dict(run.input)
        updated_input["human_feedback"] = feedback
        unit_of_work.agent_workflows.update_input(run.id, updated_input)
        updated = unit_of_work.agent_workflows.transition(
            run.id,
            AgentWorkflowStatus.REFINING,
            current_step="WRITER",
            refinement_count=run.refinement_count + 1,
        )
        outbox = getattr(unit_of_work, "outbox", None)
        if outbox is not None:
            outbox.add(
                workspace_id=updated.workspace_id,
                aggregate_id=updated.id,
                event=PipelineEvent(
                    event_id=uuid4(),
                    event_type=PipelineEventType.WRITER_REFINEMENT_REQUESTED,
                    event_version="1.0",
                    workspace_id=updated.workspace_id,
                    run_id=updated.id,
                    correlation_id=updated.id,
                    payload_ref={"feedback": feedback, "precedence": "REVIEWER"},
                ),
            )
        unit_of_work.commit()


def _load_brand_context(
    run: AgentWorkflowRunRecord, user_id: UUID
) -> tuple[JsonObject, JsonObject]:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        brand = unit_of_work.brands.get_for_user(user_id=user_id, brand_id=run.brand_id)
        if brand is None or brand.workspace_id != run.workspace_id:
            raise RuntimeError("Brand is outside the workflow Workspace")
        settings = unit_of_work.brand_settings.get_for_user(user_id=user_id, brand_id=run.brand_id)
        return (
            {
                "id": str(brand.id),
                "name": brand.name,
                "description": brand.description,
                "voice": brand.brand_voice,
                "metadata": brand.metadata,
            },
            {
                "voice_settings": settings.voice_settings,
                "visual_settings": settings.visual_settings,
                "generation_defaults": settings.generation_defaults,
            }
            if settings
            else {},
        )


def _knowledge(run: AgentWorkflowRunRecord) -> list[dict[str, object]]:
    query = str(run.input.get("campaign", ""))
    try:
        documents = create_semantic_retriever(get_settings()).search(
            query, workspace_id=str(run.workspace_id), top_k=get_settings().rag_top_k
        )
        return [
            {"content": item.content, "score": item.score, "metadata": dict(item.metadata)}
            for item in documents
        ]
    except RetrievalProviderNotConfiguredError:
        return []


def _execute_agent_step[OutputModel: BaseModel](
    *,
    run_id: UUID,
    role: AgentWorkflowStepRole,
    inputs: Mapping[str, object],
    orchestrator: MultiAgentOrchestrator,
    output_model: type[OutputModel],
) -> OutputModel:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        run = unit_of_work.agent_workflows.get_internal(run_id)
        if run is None:
            raise RuntimeError("Agent workflow not found")
        existing_steps = unit_of_work.agent_workflows.list_steps_internal(run_id)
        if role in {AgentWorkflowStepRole.BUSINESS, AgentWorkflowStepRole.PLANNER}:
            completed = next(
                (
                    candidate
                    for candidate in reversed(existing_steps)
                    if candidate.role == role
                    and candidate.status.value == "COMPLETED"
                    and candidate.output
                ),
                None,
            )
            if completed is not None:
                try:
                    return output_model.model_validate(completed.output)
                except Exception as exc:
                    raise RuntimeError("Completed pipeline output is invalid") from exc
        sequence = len(existing_steps) + 1
        step = unit_of_work.agent_workflows.add_step(
            run_id=run_id,
            workspace_id=run.workspace_id,
            sequence_number=sequence,
            role=role,
            attempt=run.refinement_count + 1,
            input=dict(inputs),
        )
        unit_of_work.commit()
    try:
        result = orchestrator.execute(
            AgentExecutionContext(
                workspace_id=run.workspace_id,
                brand_id=run.brand_id,
                role=role,
                inputs=inputs,
                prompt_template_id=f"agent.{role.value.lower()}.v1",
                prompt_template_version="1.0",
            ),
            output_model,
        )
    except Exception:
        with SqlAlchemyUnitOfWork() as unit_of_work:
            unit_of_work.agent_workflows.fail_step(
                step.id, error_code="AGENT_OUTPUT_INVALID", error_message="Specialist agent failed"
            )
            unit_of_work.commit()
        raise
    with SqlAlchemyUnitOfWork() as unit_of_work:
        predecessor = unit_of_work.agent_workflows.list_steps_internal(run_id)
        output_hash = stable_hash(result.output.model_dump(mode="json"))
        unit_of_work.agent_workflows.complete_step(
            step.id,
            output=result.output.model_dump(mode="json"),
            prompt=result.prompt,
            prompt_template_id=f"agent.{role.value.lower()}.v1",
            prompt_template_version="1.0",
            input_hash=result.input_hash,
            provider=result.provider,
            model=result.model,
            output_hash=output_hash,
            schema_name=output_model.__name__,
            schema_version="1.0",
            predecessor_step_id=predecessor[-1].id if predecessor else None,
            correlation_id=run_id,
        )
        event_type = {
            AgentWorkflowStepRole.BUSINESS: PipelineEventType.BUSINESS_COMPLETED,
            AgentWorkflowStepRole.PLANNER: PipelineEventType.PLANNER_COMPLETED,
            AgentWorkflowStepRole.WRITER: PipelineEventType.WRITER_COMPLETED,
        }.get(role)
        outbox = getattr(unit_of_work, "outbox", None)
        if event_type is not None and outbox is not None:
            outbox.add(
                workspace_id=run.workspace_id,
                aggregate_id=run_id,
                event=PipelineEvent(
                    event_id=UUID(str(step.id)),
                    event_type=event_type,
                    event_version="1.0",
                    workspace_id=run.workspace_id,
                    run_id=run_id,
                    step_id=step.id,
                    predecessor_step_id=predecessor[-1].id if predecessor else None,
                    correlation_id=run_id,
                    input_hash=result.input_hash,
                    output_hash=output_hash,
                    payload_ref={"step_id": str(step.id), "schema": output_model.__name__},
                ),
            )
        unit_of_work.commit()
    return cast(OutputModel, result.output)


def _run_post_until_accepted(
    *,
    run: AgentWorkflowRunRecord,
    user: UserRecord,
    index: int,
    business: BusinessOutput,
    planner_envelope: PipelineEnvelope,
    post: JsonObject,
    feedback: str,
    orchestrator: MultiAgentOrchestrator,
    settings: object,
) -> UUID:
    from creator.config import Settings

    typed_settings = settings if isinstance(settings, Settings) else get_settings()
    reviewer = create_image_reviewer(typed_settings)
    refinement_count = run.refinement_count
    while True:
        writer = _execute_agent_step(
            run_id=run.id,
            role=AgentWorkflowStepRole.WRITER,
            inputs={
                "business_context": business.model_dump(mode="json"),
                "predecessor": {
                    "schema": "planner.output.v1",
                    "payload": planner_envelope.payload,
                    "payload_hash": planner_envelope.payload_hash,
                    "context_hash": planner_envelope.provenance.context_hash,
                },
                "post": post,
                "feedback": feedback,
                "item": index,
            },
            orchestrator=orchestrator,
            output_model=WriterOutput,
        )
        image_record, generated = _generate_workflow_image(
            run=run,
            user=user,
            writer=writer,
            index=index,
            refinement_count=refinement_count,
            settings=typed_settings,
        )
        review = reviewer.review(
            ImageReviewRequest(
                image_bytes=generated.image_bytes,
                mime_type=generated.mime_type,
                prompt=writer.direction.visual_prompt,
                briefing=writer.direction.briefing,
                brand_context=business.model_dump(mode="json"),
            )
        )
        _persist_review_step(run, index, writer, review)
        if review.safety_issues:
            raise RuntimeError("REVIEW_SAFETY_REJECTED")
        if review.decision not in {"APPROVED", "REFINE", "REJECTED"}:
            raise RuntimeError("REVIEW_INVALID_DECISION")
        if review.decision == "APPROVED":
            return image_record.id
        if review.decision == "REJECTED":
            raise RuntimeError("REVIEW_QUALITY_REJECTED")
        if refinement_count >= run.max_refinements:
            raise RuntimeError("MAX_REFINEMENTS_EXCEEDED")
        refinement_count += 1
        feedback = (
            "; ".join(review.feedback) or "Improve adherence to the briefing and brand direction."
        )
        with SqlAlchemyUnitOfWork() as unit_of_work:
            unit_of_work.agent_workflows.transition(
                run.id,
                AgentWorkflowStatus.REFINING,
                current_step="WRITER",
                refinement_count=refinement_count,
            )
            unit_of_work.agent_workflows.transition(
                run.id, AgentWorkflowStatus.RUNNING, current_step="WRITER"
            )
            unit_of_work.commit()


def _generate_workflow_image(
    *,
    run: AgentWorkflowRunRecord,
    user: UserRecord,
    writer: WriterOutput,
    index: int,
    refinement_count: int,
    settings: object,
    predecessor_step_id: UUID | None = None,
) -> tuple[ImageRecord, ImageGenerationResult]:
    from creator.config import Settings

    typed_settings = settings if isinstance(settings, Settings) else get_settings()
    parameters: JsonObject = {
        "agent_workflow_run_id": str(run.id),
        "item": index,
        "agent_role": "ARTIST",
    }
    with SqlAlchemyUnitOfWork() as unit_of_work:
        job = unit_of_work.image_generations.create_image_generation(
            workspace_id=run.workspace_id,
            content_id=run.content_id,
            requested_by_user_id=user.id,
            model=typed_settings.gemini_image_model,
            prompt=writer.direction.visual_prompt,
            parameters=parameters,
            external_id=f"agent-workflow:{run.id}:{index}:{refinement_count}",
            max_attempts=typed_settings.image_generation_job_max_attempts,
        )
        unit_of_work.commit()
    with SqlAlchemyUnitOfWork() as unit_of_work:
        work_item = unit_of_work.image_generations.claim_pending_by_id(job.id)
        unit_of_work.commit()
    if work_item is None:
        raise RuntimeError("Image Generation Job could not be claimed")
    generated = create_image_generator(typed_settings).generate(
        ImageGenerationRequest(
            prompt=writer.direction.visual_prompt,
            model=typed_settings.gemini_image_model,
            metadata={"agent_workflow_run_id": str(run.id), "item": index},
        )
    )
    with SqlAlchemyUnitOfWork() as unit_of_work:
        image_record = persist_generated_image(
            unit_of_work=unit_of_work,
            storage=create_storage_provider(typed_settings),
            job=work_item.job,
            user=user,
            image=GeneratedImage(
                content=generated.image_bytes,
                mime_type=generated.mime_type,
                width=generated.width,
                height=generated.height,
                model=generated.model,
                prompt=generated.prompt,
                metadata=generated.metadata,
            ),
        )
    _persist_artist_step(
        run, index, writer, image_record.id, predecessor_step_id=predecessor_step_id
    )
    return image_record, generated


def _persist_artist_step(
    run: AgentWorkflowRunRecord,
    index: int,
    writer: WriterOutput,
    image_id: UUID,
    predecessor_step_id: UUID | None = None,
) -> None:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        _execute_artifact_step(
            unit_of_work,
            run,
            AgentWorkflowStepRole.ARTIST,
            index,
            {"direction": writer.direction.model_dump(mode="json")},
            {"image_id": str(image_id)},
            predecessor_step_id=predecessor_step_id,
        )
        step = unit_of_work.agent_workflows.list_steps_internal(run.id)[-1]
        outbox = getattr(unit_of_work, "outbox", None)
        if outbox is not None:
            outbox.add(
                workspace_id=run.workspace_id,
                aggregate_id=run.id,
                event=PipelineEvent(
                    event_id=step.id,
                    event_type=PipelineEventType.ARTIST_COMPLETED,
                    event_version="1.0",
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                    step_id=step.id,
                    predecessor_step_id=step.predecessor_step_id,
                    correlation_id=run.id,
                    output_hash=stable_hash(step.output),
                    payload_ref={"step_id": str(step.id), "schema": "ArtistOutput"},
                ),
            )
        unit_of_work.commit()


def _persist_review_step(
    run: AgentWorkflowRunRecord,
    index: int,
    writer: WriterOutput,
    review: object,
    predecessor_step_id: UUID | None = None,
) -> None:
    output = (
        review
        if isinstance(review, dict)
        else {
            "decision": getattr(review, "decision", "REJECTED"),
            "score": getattr(review, "score", 0),
            "feedback": list(getattr(review, "feedback", ())),
            "safety_issues": list(getattr(review, "safety_issues", ())),
        }
    )
    with SqlAlchemyUnitOfWork() as unit_of_work:
        _execute_artifact_step(
            unit_of_work,
            run,
            AgentWorkflowStepRole.REVIEWER,
            index,
            {"prompt": writer.direction.visual_prompt},
            output,
            predecessor_step_id=predecessor_step_id,
        )
        step = unit_of_work.agent_workflows.list_steps_internal(run.id)[-1]
        outbox = getattr(unit_of_work, "outbox", None)
        if outbox is not None:
            outbox.add(
                workspace_id=run.workspace_id,
                aggregate_id=run.id,
                event=PipelineEvent(
                    event_id=step.id,
                    event_type=PipelineEventType.REVIEWER_COMPLETED,
                    event_version="1.0",
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                    step_id=step.id,
                    predecessor_step_id=step.predecessor_step_id,
                    correlation_id=run.id,
                    output_hash=stable_hash(step.output),
                    payload_ref={"step_id": str(step.id), "schema": "ReviewOutput"},
                ),
            )
        unit_of_work.commit()


def _execute_artifact_step(
    unit_of_work: SqlAlchemyUnitOfWork,
    run: AgentWorkflowRunRecord,
    role: AgentWorkflowStepRole,
    sequence: int,
    input: JsonObject,
    output: JsonObject,
    predecessor_step_id: UUID | None = None,
) -> None:
    step = unit_of_work.agent_workflows.add_step(
        run_id=run.id,
        workspace_id=run.workspace_id,
        sequence_number=len(unit_of_work.agent_workflows.list_steps_internal(run.id)) + 1,
        role=role,
        attempt=run.refinement_count + 1,
        input=input,
    )
    unit_of_work.agent_workflows.complete_step(
        step.id,
        output=output,
        decision=str(output.get("decision", "")) or None,
        predecessor_step_id=predecessor_step_id,
    )


def _fail_workflow(run_id: UUID, code: str, message: str) -> None:
    try:
        with SqlAlchemyUnitOfWork() as unit_of_work:
            run = unit_of_work.agent_workflows.get_internal(run_id)
            if run is None or run.status in {
                AgentWorkflowStatus.COMPLETED,
                AgentWorkflowStatus.REJECTED,
                AgentWorkflowStatus.FAILED,
            }:
                return
            unit_of_work.agent_workflows.transition(
                run_id,
                AgentWorkflowStatus.FAILED,
                current_step=run.current_step,
                failure_code=code,
                failure_message=message,
            )
            unit_of_work.commit()
    except Exception:
        logger.exception(
            "image_agent_workflow_failure_persistence_failed", extra={"run_id": str(run_id)}
        )


def _reject_workflow(run_id: UUID, code: str, message: str) -> None:
    try:
        with SqlAlchemyUnitOfWork() as unit_of_work:
            run = unit_of_work.agent_workflows.get_internal(run_id)
            if run is None or run.status in {
                AgentWorkflowStatus.COMPLETED,
                AgentWorkflowStatus.REJECTED,
                AgentWorkflowStatus.FAILED,
            }:
                return
            unit_of_work.agent_workflows.transition(
                run_id,
                AgentWorkflowStatus.REJECTED,
                current_step=run.current_step,
                failure_code=code,
                failure_message=message,
            )
            unit_of_work.commit()
    except Exception:
        logger.exception(
            "image_agent_workflow_rejection_persistence_failed", extra={"run_id": str(run_id)}
        )


def _failure_code(error: Exception) -> str:
    return str(error).split(":", 1)[0][:100] or "AGENT_WORKFLOW_FAILED"
