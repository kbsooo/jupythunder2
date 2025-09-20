"""Thin wrapper around the Ollama Python client."""
from __future__ import annotations

from typing import Optional


class LLMProviderError(RuntimeError):
    """Raised when the LLM backend cannot be reached or responds with an error."""


class LLMProvider:
    """Helper that talks to a local Ollama instance."""

    def __init__(self, model: str, host: Optional[str] = None) -> None:
        try:
            from ollama import Client
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise LLMProviderError("ollama 클라이언트를 불러올 수 없습니다. `pip install ollama`를 확인하세요.") from exc

        self.model = model
        self._client = Client(host=host) if host else Client()

    def complete(self, prompt: str, temperature: float = 0.1) -> str:
        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": temperature},
                stream=False,
            )
        except Exception as exc:  # pragma: no cover - network/LLM failure
            raise LLMProviderError(str(exc)) from exc

        if isinstance(response, dict):
            text = response.get("response")
        else:
            text = getattr(response, "response", None)

        if not text:
            raise LLMProviderError("LLM 응답이 비어 있습니다.")
        return text


__all__ = ["LLMProvider", "LLMProviderError"]
