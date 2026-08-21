import os

import httpx

from app.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:8b")

    async def generate(self, message: str) -> str:
        payload = {
            "model": self.model,
            "prompt": message,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return str(data.get("response", "")).strip()
