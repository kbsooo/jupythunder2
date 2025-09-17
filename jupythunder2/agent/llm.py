"""LLM 클라이언트를 추상화한 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMGenerationError(RuntimeError):
    """LLM 호출 실패 시 발생하는 예외."""


class LLMClient(Protocol):
    """LLM 호출을 위한 최소 인터페이스."""

    def generate(self, prompt: str) -> str:  # pragma: no cover - 프로토콜 정의
        ...


@dataclass(slots=True)
class DummyLLMClient:
    """테스트 및 폴백을 위한 더미 LLM."""

    def generate(self, prompt: str) -> str:  # pragma: no cover - 간단 로직
        return (
            "{\n"
            "  \"title\": \"Sample Development Plan\",\n"
            "  \"summary\": \"제공된 목표를 기반으로 한 예시 플랜입니다.\",\n"
            "  \"steps\": [\n"
            "    {\"id\": 1, \"name\": \"Clarify requirements\", \"description\": \"주요 기능과 성공 기준을 정리합니다.\"},\n"
            "    {\"id\": 2, \"name\": \"Design module boundaries\", \"description\": \"핵심 컴포넌트와 책임을 정의합니다.\"},\n"
            "    {\"id\": 3, \"name\": \"Implement incrementally\", \"description\": \"작은 단위로 기능을 구현하고 검증합니다.\"}\n"
            "  ]\n"
            "}"
        )


@dataclass(slots=True)
class OllamaLLMClient:
    """Ollama를 통해 로컬 LLM을 호출한다."""

    model: str
    temperature: float = 0.1
    base_url: str | None = None

    def __post_init__(self) -> None:
        try:
            from langchain_community.chat_models import ChatOllama
        except ImportError as exc:  # pragma: no cover - 설치 문제 핸들링
            raise LLMGenerationError(
                "LangChain Ollama 지원이 설치되지 않았습니다. `langchain-community` 패키지를 확인하세요."
            ) from exc

        self._chat_model = ChatOllama(
            model=self.model,
            temperature=self.temperature,
            base_url=self.base_url,
        )

    def generate(self, prompt: str) -> str:
        try:
            response = self._chat_model.invoke(prompt)
        except Exception as exc:  # pragma: no cover - 외부 I/O
            raise LLMGenerationError("Ollama 모델 호출에 실패했습니다.") from exc

        # LangChain의 응답은 문자열 또는 메시지 객체가 될 수 있다.
        if isinstance(response, str):  # pragma: no cover - 호환성 처리
            return response

        content = getattr(response, "content", None)
        if not content:
            raise LLMGenerationError("Ollama 응답에서 본문을 찾지 못했습니다.")
        return content
