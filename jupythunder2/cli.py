"""Entry point for the jupythunder2 CLI experience."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .config import JT2Settings, load_config
from .tui.repl import JT2Repl
from .store.codebook import CodebookLogger, discover_codebooks

app = typer.Typer(add_completion=False, rich_markup_mode="rich")


def _load_splash() -> str:
    try:
        splash_path = resources.files("jupythunder2") / "assets" / "splash.txt"
        return splash_path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return "jupythunder2"


def _create_console(use_color: bool) -> Console:
    return Console(no_color=not use_color, highlight=use_color)


def _show_splash(console: Console, settings: JT2Settings) -> None:
    splash = _load_splash()
    if settings.use_color:
        subtitle = f"model=[bold]{settings.model}[/] | auto_execute={'ON' if settings.auto_execute else 'OFF'}"
    else:
        subtitle = f"model={settings.model} | auto_execute={'ON' if settings.auto_execute else 'OFF'}"
    console.print(Panel(splash, title="jupythunder2", subtitle=subtitle, highlight=settings.use_color))


def _choose_codebook(settings: JT2Settings, console: Console) -> CodebookLogger:
    entries = discover_codebooks(settings.codebook_root)
    if not entries:
        return _create_new_codebook(settings, console)

    console.print("기존 코드북이 발견되었습니다.")
    for idx, entry in enumerate(entries, start=1):
        console.print(f"[{idx}] {entry.stem} · {entry.summary}")

    if typer.confirm("새 코드북을 생성할까요?", default=False):
        return _create_new_codebook(settings, console)

    while True:
        choice = typer.prompt("불러올 코드북 번호를 입력하세요", default="1").strip()
        try:
            index = int(choice)
        except ValueError:
            console.print("번호로 입력해주세요.")
            continue
        if 1 <= index <= len(entries):
            entry = entries[index - 1]
            console.print(f"코드북 선택: {entry.stem} · {entry.summary}")
            return CodebookLogger.open_existing(settings.codebook_root, entry.stem)
        console.print("목록에 있는 번호를 선택해주세요.")


def _create_new_codebook(settings: JT2Settings, console: Console) -> CodebookLogger:
    summary = typer.prompt("새 노트북의 한 줄 요약을 입력하세요", default="새 세션")
    logger = CodebookLogger.create(settings.codebook_root, summary)
    console.print(f"새 코드북 생성: {logger.stem} · {logger.summary}")
    return logger


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
    color: Optional[bool] = typer.Option(
        None,
        "--color/--no-color",
        help="컬러 출력 사용 여부를 강제로 지정합니다.",
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
    updates: dict[str, object] = {}
    if auto is not None:
        updates["auto_execute"] = auto
    if color is not None:
        updates["use_color"] = color
    if updates:
        settings = settings.model_copy(update=updates)

    console = _create_console(settings.use_color)

    try:
        if dry_run:
            payload = _serialize_settings(settings)
            console.print(Panel(payload, title="configuration"))
            return

        _show_splash(console, settings)
        codebook = _choose_codebook(settings, console)
        repl = JT2Repl(settings=settings, codebook=codebook, console=console)
        try:
            repl.run()
        except KeyboardInterrupt:
            console.print("\n세션을 종료합니다.")
        finally:
            repl.shutdown()
    except TypeError as exc:
        message = str(exc)
        if "model_dump_json" in message and "ensure_ascii" in message:
            payload = json.dumps(settings.to_dict(), indent=2, ensure_ascii=False)
            console.print(Panel(payload, title="configuration"))
            return
        raise


def _serialize_settings(settings: JT2Settings) -> str:
    try:
        return settings.model_dump_json(indent=2, ensure_ascii=False)
    except TypeError as exc:
        if "ensure_ascii" not in str(exc):
            raise
    try:
        return settings.model_dump_json(indent=2)
    except TypeError:
        return json.dumps(settings.to_dict(), indent=2, ensure_ascii=False)


def entrypoint() -> None:
    """Typer entrypoint for `jt2`."""
    app()


if __name__ == "__main__":  # pragma: no cover
    entrypoint()
