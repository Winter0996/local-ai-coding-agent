from abc import ABC, abstractmethod


class LLMProvider(ABC):
    model: str

    @abstractmethod
    async def generate(self, message: str) -> str:
        raise NotImplementedError
