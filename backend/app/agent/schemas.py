from pydantic import BaseModel, Field


class ProposeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class ProposeResponse(BaseModel):
    workspace_id: str
    target_path: str
    diff: str
    proposed_content: str
    explanation: str


class ApplyRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    content: str


class ApplyResponse(BaseModel):
    path: str
    bytes_written: int