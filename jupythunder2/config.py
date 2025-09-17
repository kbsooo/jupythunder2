"""에이전트 및 런타임 설정 관리."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:  # Python 3.11+
    import tomllib as toml
except ModuleNotFoundError:  # pragma: no cover - fallback for older versions
    import tomli as toml  # type: ignore

import tomli_w

CONFIG_PATH_ENV = "JUPYTHUNDER2_CONFIG_PATH"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "jupythunder2" / "config.toml"


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
    base_url: Optional[str] = None
    temperature: float = 0.1
    allow_fallback: bool = True


@dataclass(slots=True)
class RuntimeSettings:
    """실행 전반에 사용되는 설정."""

    history_limit: int = 50
    default_history_file: Optional[str] = None
    workflows_dir: Optional[str] = None


def _config_path() -> Path:
    override = os.getenv(CONFIG_PATH_ENV)
    if override:
        return Path(override).expanduser()
    return DEFAULT_CONFIG_PATH


def read_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return toml.loads(path.read_text())
    except Exception:  # pragma: no cover - 파일 손상 등
        return {}


def write_config(data: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fp:
        tomli_w.dump(data, fp)


def load_agent_settings() -> AgentSettings:
    """환경 변수와 설정 파일을 기반으로 `AgentSettings`를 구성한다."""

    config = read_config()
    agent_cfg = config.get("agent", {})

    settings = AgentSettings(
        provider=str(agent_cfg.get("provider", "ollama")),
        model=str(agent_cfg.get("model", "codegemma:7b")),
        base_url=agent_cfg.get("base_url"),
        temperature=float(agent_cfg.get("temperature", 0.1)),
        allow_fallback=bool(agent_cfg.get("allow_fallback", True)),
    )

    return AgentSettings(
        provider=os.getenv("JUPYTHUNDER2_PROVIDER", settings.provider),
        model=os.getenv("JUPYTHUNDER2_MODEL", settings.model),
        base_url=os.getenv("JUPYTHUNDER2_BASE_URL", settings.base_url),
        temperature=_parse_float(os.getenv("JUPYTHUNDER2_TEMPERATURE"), settings.temperature),
        allow_fallback=_parse_bool(
            os.getenv("JUPYTHUNDER2_ALLOW_FALLBACK"), settings.allow_fallback
        ),
    )


def load_runtime_settings() -> RuntimeSettings:
    config = read_config()
    runtime_cfg = config.get("runtime", {})

    settings = RuntimeSettings(
        history_limit=int(runtime_cfg.get("history_limit", 50)),
        default_history_file=runtime_cfg.get("default_history_file"),
        workflows_dir=runtime_cfg.get("workflows_dir"),
    )

    history_limit_env = os.getenv("JUPYTHUNDER2_HISTORY_LIMIT")
    if history_limit_env:
        try:
            settings.history_limit = max(1, int(history_limit_env))
        except ValueError:
            pass

    history_file_env = os.getenv("JUPYTHUNDER2_HISTORY_FILE")
    if history_file_env:
        settings.default_history_file = history_file_env

    workflows_dir_env = os.getenv("JUPYTHUNDER2_WORKFLOWS_DIR")
    if workflows_dir_env:
        settings.workflows_dir = workflows_dir_env

    return settings


def update_agent_settings(settings: AgentSettings) -> None:
    config = read_config()
    config.setdefault("agent", {})
    payload = {
        "provider": settings.provider,
        "model": settings.model,
        "temperature": settings.temperature,
        "allow_fallback": settings.allow_fallback,
    }
    if settings.base_url is not None:
        payload["base_url"] = settings.base_url
    else:
        config["agent"].pop("base_url", None)
    config["agent"].update(payload)
    write_config(config)


def update_runtime_settings(settings: RuntimeSettings) -> None:
    config = read_config()
    config.setdefault("runtime", {})
    payload = {
        "history_limit": settings.history_limit,
    }
    if settings.default_history_file is not None:
        payload["default_history_file"] = settings.default_history_file
    else:
        config["runtime"].pop("default_history_file", None)
    if settings.workflows_dir is not None:
        payload["workflows_dir"] = settings.workflows_dir
    else:
        config["runtime"].pop("workflows_dir", None)
    config["runtime"].update(payload)
    write_config(config)


def reset_config() -> None:
    path = _config_path()
    if path.exists():
        path.unlink()


def get_config_path() -> Path:
    return _config_path()
