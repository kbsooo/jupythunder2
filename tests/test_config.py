from pathlib import Path

import os
from typer.testing import CliRunner

from jupythunder2 import cli
from jupythunder2.config import (
    AgentSettings,
    RuntimeSettings,
    get_config_path,
    load_agent_settings,
    load_runtime_settings,
    read_config,
    reset_config,
    update_agent_settings,
    update_runtime_settings,
)


def test_agent_settings_roundtrip(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    monkeypatch.setenv("JUPYTHUNDER2_CONFIG_PATH", str(config_path))

    update_agent_settings(
        AgentSettings(provider="dummy", model="mock", temperature=0.3, allow_fallback=False)
    )

    settings = load_agent_settings()
    assert settings.provider == "dummy"
    assert settings.model == "mock"
    assert settings.temperature == 0.3
    assert not settings.allow_fallback

    monkeypatch.setenv("JUPYTHUNDER2_MODEL", "env-model")
    settings_env = load_agent_settings()
    assert settings_env.model == "env-model"


def test_runtime_settings_roundtrip(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    monkeypatch.setenv("JUPYTHUNDER2_CONFIG_PATH", str(config_path))

    update_runtime_settings(
        RuntimeSettings(history_limit=99, default_history_file="/tmp/history.json", workflows_dir="/tmp/wf")
    )

    runtime = load_runtime_settings()
    assert runtime.history_limit == 99
    assert runtime.default_history_file == "/tmp/history.json"
    assert runtime.workflows_dir == "/tmp/wf"

    monkeypatch.setenv("JUPYTHUNDER2_HISTORY_LIMIT", "123")
    runtime_env = load_runtime_settings()
    assert runtime_env.history_limit == 123


def test_reset_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    monkeypatch.setenv("JUPYTHUNDER2_CONFIG_PATH", str(config_path))

    update_agent_settings(AgentSettings())
    assert config_path.exists()

    reset_config()
    assert not config_path.exists()


def test_cli_config_show(tmp_path, monkeypatch):
    config_path = tmp_path / "config.toml"
    monkeypatch.setenv("JUPYTHUNDER2_CONFIG_PATH", str(config_path))

    update_agent_settings(AgentSettings(provider="dummy"))
    runner = CliRunner()
    result = runner.invoke(cli.app, ["config", "show"])
    assert result.exit_code == 0
    assert "dummy" in result.stdout
