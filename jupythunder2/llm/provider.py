"""Thin wrapper around the Ollama Python client."""
from __future__ import annotations

from typing import Optional


class LLMProviderError(RuntimeError):
    """Raised when the LLM backend cannot be reached or responds with an error."""


class LLMProvider:
    """Helper that talks to a local or remote Ollama instance."""

    def __init__(self, model: str, host: Optional[str] = None, request_timeout: float = 30.0) -> None:
        try:
            from ollama import Client
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise LLMProviderError("ollama 클라이언트를 불러올 수 없습니다. `pip install ollama`를 확인하세요.") from exc

        client_kwargs = {}
        if host:
            client_kwargs["host"] = host
        if request_timeout is not None:
            client_kwargs["timeout"] = request_timeout

        self.model = model
        self._host = host
        self._timeout = request_timeout
        self._client = Client(**client_kwargs)

    def complete(self, prompt: str, temperature: float = 0.1) -> str:
        try:
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": temperature},
                stream=False,
            )
        except Exception as exc:  # pragma: no cover - network/LLM failure
            message = str(exc)
            exc_name = type(exc).__name__
            if "timeout" in message.lower() or "Timeout" in exc_name:
                host_info = f" ({self._host})" if self._host else ""
                raise LLMProviderError(
                    f"LLM 응답이 {self._timeout:.1f}초 안에 도착하지 않았습니다{host_info}. 서버 상태를 확인하세요."
                ) from exc
            raise LLMProviderError(message or exc_name) from exc

        if isinstance(response, dict):
            text = response.get("response")
        else:
            text = getattr(response, "response", None)

        if not text:
            raise LLMProviderError("LLM 응답이 비어 있습니다.")
        return text


__all__ = ["LLMProvider", "LLMProviderError"]
