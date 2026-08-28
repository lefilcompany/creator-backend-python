from creator.domain.generation import GenerationJobStatus, can_transition


def test_generation_job_has_documented_lifecycle() -> None:
    assert can_transition(GenerationJobStatus.PENDING, GenerationJobStatus.PROCESSING)
    assert can_transition(GenerationJobStatus.PROCESSING, GenerationJobStatus.COMPLETED)
    assert can_transition(GenerationJobStatus.PROCESSING, GenerationJobStatus.FAILED)
    assert not can_transition(GenerationJobStatus.COMPLETED, GenerationJobStatus.PROCESSING)
