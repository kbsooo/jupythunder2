"""Entry point for the jupythunder2 CLI experience."""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .config import JT2Settings, load_config
from .tui.repl import JT2Repl

CONSOLE = Console()
app = typer.Typer(add_completion=False, rich_markup_mode="rich")


def _load_splash() -> str:
    try:
        splash_path = resources.files("jupythunder2") / "assets" / "splash.txt"
        return splash_path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return "jupythunder2"


def _show_splash(settings: JT2Settings) -> None:
    splash = _load_splash()
    subtitle = f"model=[bold]{settings.model}[/] | auto_execute={'ON' if settings.auto_execute else 'OFF'}"
    CONSOLE.print(Panel(splash, title="jupythunder2", subtitle=subtitle, highlight=True))


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="사용할 설정 파일 경로",
    ),
    auto: Optional[bool] = typer.Option(
        None,
        "--auto",
        help="세션 자동 실행 여부를 강제로 지정합니다.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="설정만 출력하고 종료합니다.",
    ),
) -> None:
    """Run the interactive jt2 session by default."""
    if ctx.invoked_subcommand is not None:
        return

    settings = load_config(config_path)
    if auto is not None:
        settings = settings.model_copy(update={"auto_execute": auto})

    if dry_run:
        CONSOLE.print(Panel(settings.model_dump_json(indent=2, ensure_ascii=False), title="configuration"))
        return

    _show_splash(settings)
    repl = JT2Repl(settings=settings)
    try:
        repl.run()
    except KeyboardInterrupt:
        CONSOLE.print("\n[bold yellow]세션을 종료합니다.[/]")
    finally:
        repl.shutdown()


def entrypoint() -> None:
    """Typer entrypoint for `jt2`."""
    app()


if __name__ == "__main__":  # pragma: no cover
    entrypoint()
