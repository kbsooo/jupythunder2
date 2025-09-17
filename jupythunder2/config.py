"""에이전트 환경설정 로직."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(slots=True)
class AgentSettings:
    """에이전트 실행에 필요한 환경 설정."""

    provider: str = "ollama"
    model: str = "codegemma:7b"
    base_url: str | None = None
    temperature: float = 0.1
    allow_fallback: bool = True


def load_agent_settings() -> AgentSettings:
    """환경 변수를 기반으로 `AgentSettings`를 구성한다."""

    return AgentSettings(
        provider=os.getenv("JUPYTHUNDER2_PROVIDER", "ollama"),
        model=os.getenv("JUPYTHUNDER2_MODEL", "codegemma:7b"),
        base_url=os.getenv("JUPYTHUNDER2_BASE_URL"),
        temperature=_parse_float(os.getenv("JUPYTHUNDER2_TEMPERATURE"), 0.1),
        allow_fallback=_parse_bool(os.getenv("JUPYTHUNDER2_ALLOW_FALLBACK"), True),
    )
