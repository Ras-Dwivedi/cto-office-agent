import os
from src.llm.providers.ollama import OllamaProvider


class LLMClient:
    def __init__(self):
        self.provider = OllamaProvider(
            url=os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
            model=os.getenv("OLLAMA_MODEL", "llama3"),
        )

    def complete(self, system: str, user: str) -> str:
        return self.provider.complete(system, user)


# Singleton
llm = LLMClient()
