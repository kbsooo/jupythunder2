"""Lightweight heuristics for error summarisation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..runtime.kernel import ExecutionError


@dataclass
class DebugSummary:
    explanation: str
    suggestion: Optional[str] = None


class Debugger:
    """Provide human-readable summaries for kernel errors."""

    def summarize(self, error: ExecutionError) -> DebugSummary:
        explanation = f"{error.ename}: {error.evalue}" if error.evalue else error.ename
        suggestion: Optional[str] = None

        if error.ename in {"NameError", "UnboundLocalError"}:
            suggestion = "변수나 함수가 정의되어 있는지 확인하세요. 스펠링을 다시 검토해보세요."
        elif error.ename in {"ModuleNotFoundError", "ImportError"}:
            suggestion = "필요한 패키지가 설치되었는지와 모듈 경로가 정확한지 확인하세요."
        elif error.ename == "TypeError":
            suggestion = "함수나 메서드에 전달한 인자 타입과 개수를 재확인하세요."
        elif error.ename == "ValueError":
            suggestion = "입력 값이 허용 범위/형식에 맞는지 검증해보세요."
        elif error.ename == "SyntaxError":
            suggestion = "해당 줄 근처의 문법 오류(괄호 닫힘, 콜론 등)를 다시 살펴보세요."
        elif error.ename == "FileNotFoundError":
            suggestion = "파일 경로와 현재 작업 디렉터리가 올바른지 확인하세요."

        return DebugSummary(explanation=explanation, suggestion=suggestion)


__all__ = ["Debugger", "DebugSummary"]
