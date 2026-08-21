from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.llm.ollama import OllamaProvider

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class ChatResponse(BaseModel):
    response: str
    model: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    provider = OllamaProvider()

    try:
        response = await provider.generate(request.message)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Local Ollama request failed: {exc}",
        ) from exc

    return ChatResponse(response=response, model=provider.model)
