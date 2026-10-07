from uuid import UUID

from pydantic import BaseModel


class WorkspaceCreditTransactionCreateRequest(BaseModel):
    workspace_id: UUID
    amount: int
    transaction_type: str
    reference_type: str | None = None
    reference_id: UUID | None = None
