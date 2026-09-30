from pydantic import BaseModel, ConfigDict


class CreatorDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
