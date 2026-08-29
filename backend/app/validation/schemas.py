from pydantic import BaseModel, Field


class AvailableCommandsResponse(BaseModel):
    commands: list[str]


class RunCommandRequest(BaseModel):
    command_key: str = Field(min_length=1, max_length=50)


class RunCommandResponse(BaseModel):
    command_key: str
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool
    duration_seconds: float
    passed: bool