from enum import StrEnum


class GenerationJobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS: dict[GenerationJobStatus, frozenset[GenerationJobStatus]] = {
    GenerationJobStatus.PENDING: frozenset(
        {GenerationJobStatus.PROCESSING, GenerationJobStatus.FAILED}
    ),
    GenerationJobStatus.PROCESSING: frozenset(
        {GenerationJobStatus.COMPLETED, GenerationJobStatus.FAILED}
    ),
    GenerationJobStatus.COMPLETED: frozenset(),
    GenerationJobStatus.FAILED: frozenset(),
}


def can_transition(current: GenerationJobStatus, target: GenerationJobStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
