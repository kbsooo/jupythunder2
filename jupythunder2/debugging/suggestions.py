"""LLM을 활용한 컨텍스트 인지형 디버깅 로직."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, List, Optional

from ..agent.llm import LLMClient, LLMGenerationError, OllamaLLMClient
from ..config import AgentSettings, load_agent_settings
from ..history import ExecutedCell, ExecutionHistory


@dataclass(slots=True)
class DebugSuggestion:
    """LLM이 제안한 디버깅 도움말."""

    summary: str
    root_cause: str
    recommendation: str
    patch: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "root_cause": self.root_cause,
            "recommendation": self.recommendation,
            "patch": self.patch,
        }


class DebuggingAgent:
    """커널 실행 오류를 분석하고 수정 제안을 생성한다."""

    def __init__(self, llm_client: LLMClient, settings: AgentSettings) -> None:
        self._llm = llm_client
        self._settings = settings

    @classmethod
    def from_env(
        cls,
        *,
        provider_override: str | None = None,
        model_override: str | None = None,
        use_dummy: bool | None = None,
    ) -> "DebuggingAgent":
        settings = load_agent_settings()
        if provider_override:
            settings.provider = provider_override
        if model_override:
            settings.model = model_override

        if use_dummy is None:
            use_dummy = settings.provider.lower() == "dummy"

        if use_dummy:
            llm_client: LLMClient = _DummyDebugLLMClient()
        else:
            provider = settings.provider.lower()
            if provider != "ollama":
                raise LLMGenerationError(
                    f"지원되지 않는 LLM 제공자입니다: {settings.provider}. 현재는 'ollama' 또는 'dummy'만 지원합니다."
                )
            llm_client = OllamaLLMClient(
                model=settings.model,
                temperature=settings.temperature,
                base_url=settings.base_url,
            )

        return cls(llm_client=llm_client, settings=settings)

    def suggest_fix(
        self,
        *,
        failing_code: str,
        error_name: str,
        error_value: str,
        traceback: Iterable[str],
        history: ExecutionHistory,
    ) -> DebugSuggestion:
        error_name = error_name or "UnknownError"
        error_value = error_value or ""
        prompt = self._build_prompt(
            failing_code=failing_code,
            error_name=error_name,
            error_value=error_value,
            traceback=list(traceback),
            history=history.recent(5),
        )
        response = self._safe_generate(prompt)
        try:
            return self._parse_response(response)
        except DebugSuggestionParsingError as exc:
            if not self._settings.allow_fallback:
                raise
            return self._build_fallback_suggestion(
                failing_code=failing_code,
                error_name=error_name,
                error_value=error_value,
            )

    def _safe_generate(self, prompt: str) -> str:
        try:
            return self._llm.generate(prompt)
        except (LLMGenerationError, Exception):  # noqa: BLE001 - 외부 LLM 오류 포착
            if not self._settings.allow_fallback:
                raise
            return json.dumps(
                _DummyDebugLLMClient().generate_structured(),
                ensure_ascii=False,
                indent=2,
            )

    def _build_prompt(
        self,
        *,
        failing_code: str,
        error_name: str,
        error_value: str,
        traceback: List[str],
        history: List[ExecutedCell],
    ) -> str:
        history_lines = []
        for entry in history:
            line = {
                "code": entry.code,
                "stdout": entry.stdout,
                "stderr": entry.stderr,
                "result": entry.result,
                "error_name": entry.error_name,
                "error_value": entry.error_value,
            }
            history_lines.append(line)

        prompt = {
            "instruction": (
                "You are an expert Python debugging assistant. "
                "Given the failing code cell, the error details, and limited execution history, "
                "produce a JSON object that explains the likely root cause and actionable fix."
            ),
            "failing_code": failing_code,
            "error": {
                "name": error_name,
                "value": error_value,
                "traceback": list(traceback),
            },
            "history": history_lines,
            "response_schema": {
                "summary": "concise human-readable summary of the failure",
                "root_cause": "diagnosis of the underlying issue",
                "recommendation": "specific steps or code changes to fix the problem",
                "patch": "optional minimal code diff or snippet",
            },
            "rules": [
                "Respond with valid JSON only",
                "Keep summary under 160 characters",
                "If uncertain, state assumptions explicitly",
            ],
        }
        return json.dumps(prompt, ensure_ascii=False, indent=2)

    def _parse_response(self, response: str) -> DebugSuggestion:
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            raise DebugSuggestionParsingError("LLM 응답이 JSON 형식이 아닙니다.") from exc

        summary = str(payload.get("summary", "수정 요약을 생성하지 못했습니다.")).strip()
        root_cause = str(payload.get("root_cause", "원인을 파악하지 못했습니다.")).strip()
        recommendation = str(payload.get("recommendation", "수정 제안을 생성하지 못했습니다.")).strip()
        patch_raw = payload.get("patch")
        patch = str(patch_raw).strip() if patch_raw else None

        if not summary or not recommendation:
            raise DebugSuggestionParsingError("필수 필드(summary, recommendation)가 비어 있습니다.")

        return DebugSuggestion(
            summary=summary,
            root_cause=root_cause or "원인을 파악하지 못했습니다.",
            recommendation=recommendation,
            patch=patch or None,
        )

    def _build_fallback_suggestion(
        self,
        *,
        failing_code: str,
        error_name: str,
        error_value: str,
    ) -> DebugSuggestion:
        return DebugSuggestion(
            summary=f"{error_name}: {error_value}",
            root_cause="LLM 응답 파싱에 실패하여 자동 추론을 제공할 수 없습니다.",
            recommendation=(
                "코드를 수동으로 검토하고 에러 메시지와 스택트레이스를 참고하여 수정해주세요."
            ),
            patch=_extract_likely_patch(failing_code, error_name),
        )


class DebugSuggestionParsingError(ValueError):
    """LLM 디버깅 응답을 파싱하지 못했을 때 사용."""


class _DummyDebugLLMClient:
    """테스트 용도로 간단한 디버깅 제안을 반환."""

    def generate(self, prompt: str) -> str:  # pragma: no cover - 간단한 더미 응답
        return json.dumps(self.generate_structured(), ensure_ascii=False, indent=2)

    @staticmethod
    def generate_structured() -> dict:
        return {
            "summary": "오류를 재현하고 정확한 원인을 파악하세요.",
            "root_cause": "아직 원인을 파악하지 못했습니다. 입력값과 환경을 점검하세요.",
            "recommendation": "변수 값과 함수 입력을 로깅하고 단위 테스트를 추가해보세요.",
            "patch": None,
        }


def _extract_likely_patch(code: str, error_name: str) -> Optional[str]:
    if "ZeroDivisionError" in error_name:
        return "if denominator == 0: raise ValueError('denominator must be non-zero')"
    if "NameError" in error_name:
        return "# 변수 선언 또는 import를 확인하세요"
    return None
