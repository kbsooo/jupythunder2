"""Runtime configuration helpers for jupythunder2."""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator

DEFAULT_CONFIG_FILES = [
    Path.cwd() / ".jt2.toml",
    Path.home() / ".config" / "jt2" / "config.toml",
]


class JT2Settings(BaseModel):
    model: str = Field(default="codegemma:7b", description="기본 LLM 모델 이름")
    auto_execute: bool = Field(default=False, description="코드 셀 자동 실행 여부")
    run_root: Path = Field(default_factory=lambda: Path("runs"), description="세션 아티팩트 저장 경로")
    max_execution_seconds: float = Field(default=60.0, gt=0, description="코드 셀 실행 타임아웃(초)")
    history_limit: int = Field(default=10, ge=1, description="대화 히스토리 전송 최대 개수")

    @model_validator(mode="after")
    def _normalize_paths(self) -> "JT2Settings":
        self.run_root = self.run_root.expanduser()
        return self

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump()
        data["run_root"] = str(self.run_root)
        return data


def _load_toml(path: Path) -> Dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config(explicit_path: Optional[Path] = None) -> JT2Settings:
    """Load configuration from the first available location."""
    candidates = []
    if explicit_path is not None:
        candidates.append(explicit_path.expanduser())
    candidates.extend(DEFAULT_CONFIG_FILES)

    config_data: Dict[str, Any] = {}
    for candidate in candidates:
        if candidate.is_file():
            config_data = _load_toml(candidate)
            break

    return JT2Settings(**config_data)
