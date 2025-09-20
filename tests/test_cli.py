from typer.testing import CliRunner

from jupythunder2.cli import app


def test_cli_dry_run() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--dry-run"])

    assert result.exit_code == 0
    assert "configuration" in result.stdout
