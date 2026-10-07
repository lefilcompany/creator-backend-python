from uuid import UUID

from pydantic import BaseModel


class DesignStructureCreateRequest(BaseModel):
    post_structure_id: UUID
