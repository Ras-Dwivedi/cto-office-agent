import requests
import logging

logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(self, url: str, model: str, timeout: int = 60):
        self.url = url
        self.model = model
        self.timeout = timeout

    def complete(self, system: str, user: str) -> str:
        prompt = f"""SYSTEM:
{system}

USER:
{user}
"""

        try:
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception:
            logger.exception("Failed to call Ollama API")
            raise RuntimeError("Ollama API call failed")

        data = response.json()

        # Ollama returns {"response": "..."}
        return data.get("response", "").strip()
