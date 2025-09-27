"""Runtime configuration helpers for jupythunder2."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator

DEFAULT_CONFIG_FILES = [
    Path.cwd() / ".jt2.toml",
    Path.home() / ".config" / "jt2" / "config.toml",
]


class JT2Settings(BaseModel):
    model_config = ConfigDict(json_encoders={Path: str})
    model: str = Field(default="codegemma:7b", description="기본 LLM 모델 이름")
    use_color: bool = Field(default=False, description="Rich 컬러/스타일 사용 여부")
    auto_execute: bool = Field(default=True, description="코드 셀 자동 실행 여부")
    kernel_name: str = Field(default="python3", description="사용할 Jupyter 커널 이름")
    codebook_root: Path = Field(default_factory=lambda: Path("codes"), description="노트북/요약 저장 경로")
    run_root: Path = Field(default_factory=lambda: Path("runs"), description="세션 아티팩트 저장 경로")
    max_execution_seconds: float = Field(default=60.0, gt=0, description="코드 셀 실행 타임아웃(초)")
    history_limit: int = Field(default=10, ge=1, description="대화 히스토리 전송 최대 개수")
    llm_host: Optional[str] = Field(default=None, description="Ollama 또는 호환 LLM 서버 주소")
    llm_request_timeout: float = Field(default=30.0, gt=0, description="LLM 응답 대기 타임아웃(초)")

    @model_validator(mode="after")
    def _normalize_paths(self) -> "JT2Settings":
        self.run_root = self.run_root.expanduser()
        self.codebook_root = self.codebook_root.expanduser()
        return self

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump()
        data["run_root"] = str(self.run_root)
        data["codebook_root"] = str(self.codebook_root)
        return data


@dataclass
class ConfigLoadResult:
    settings: JT2Settings
    source: Optional[Path]
    searched: List[Path]



def _load_toml(path: Path) -> Dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config(explicit_path: Optional[Path] = None) -> ConfigLoadResult:
    """Load configuration from the first available location."""
    candidates: List[Path] = []
    if explicit_path is not None:
        candidates.append(explicit_path.expanduser())
    candidates.extend(DEFAULT_CONFIG_FILES)

    config_data: Dict[str, Any] = {}
    loaded_from: Optional[Path] = None
    for candidate in candidates:
        if candidate.is_file():
            config_data = _load_toml(candidate)
            loaded_from = candidate
            break

    return ConfigLoadResult(settings=JT2Settings(**config_data), source=loaded_from, searched=candidates)
