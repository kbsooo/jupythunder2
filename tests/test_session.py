from pathlib import Path

from typer.testing import CliRunner

from jupythunder2 import cli
from jupythunder2.history import ExecutionHistory


def test_session_runs_script(tmp_path: Path):
    script = tmp_path / "cells.py"
    script.write_text(
        "# %%\n" "value = 41\n" "# %%\n" "print(value + 1)\n"
    )

    history_file = tmp_path / "history.json"

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "session",
            "--script",
            str(script),
            "--history-file",
            str(history_file),
            "--no-splash",
            "--no-suggest",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "스크립트 실행을 완료했습니다." in result.stdout

    history = ExecutionHistory.load(history_file, limit=10)
    cells = history.recent()
    assert len(cells) == 2
    assert cells[-1].stdout.strip() == "42"
