"""jupythunder2의 Typer 기반 CLI 진입점."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from . import __version__
from .agent import PlanningAgent
from .ascii_art import render_splash
from .kernel import KernelExecutionError, KernelSession

app = typer.Typer(help="jupythunder2 CLI 에이전트")
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="버전 정보를 출력하고 종료",
        is_flag=True,
    ),
) -> None:
    """기본 콜백: 버전 옵션 처리 및 도움말 노출."""

    if version:
        console.print(f"jupythunder2 v{__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(render_splash(), style="bold cyan")
        console.print("명령어 예시: `jupythunder2 plan \"분석 목표\"`", style="dim")


@app.command(short_help="요구사항 기반 실행 계획 작성")
def plan(
    goal: str = typer.Argument(..., help="생성하고 싶은 목표 혹은 작업 설명"),
    context: Optional[str] = typer.Option(
        None,
        "--context",
        "-c",
        help="추가로 고려할 배경 정보",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="사용할 LLM 제공자 (기본값: 환경 설정)",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="사용할 모델 이름 (기본값: 환경 설정)",
    ),
    use_dummy: bool = typer.Option(
        False,
        "--dummy",
        help="강제로 더미 LLM을 사용",
    ),
    splash: bool = typer.Option(
        True,
        "--splash/--no-splash",
        help="ASCII 아트를 출력할지 여부",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="LLM 원본 JSON을 그대로 출력",
    ),
) -> None:
    """주어진 목표를 토대로 실행 계획을 생성한다."""

    if splash:
        console.print(render_splash(), style="bold cyan")

    agent = PlanningAgent.from_env(
        provider_override=provider,
        model_override=model,
        use_dummy=use_dummy,
    )

    execution_plan = agent.draft_plan(goal=goal, context=context)

    if raw:
        console.print(json.dumps(execution_plan.to_dict(), ensure_ascii=False, indent=2))
        return

    console.print(Panel(execution_plan.summary or "요약 정보가 제공되지 않았습니다.", title="요약"))
    console.print(execution_plan.to_rich_table())


@app.command(name="execute", short_help="코드 셀을 실행하고 결과를 출력")
def execute_cell(
    code: Optional[str] = typer.Option(
        None,
        "--code",
        "-c",
        help="실행할 파이썬 코드 (여러 줄은 따옴표로 감싸 입력)",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="실행할 코드가 담긴 파일 경로",
    ),
    kernel: str = typer.Option(
        "python3",
        "--kernel",
        help="사용할 커널 이름",
    ),
    timeout: float = typer.Option(
        30.0,
        "--timeout",
        min=1.0,
        max=300.0,
        help="커널 응답 대기 시간(초)",
    ),
    splash: bool = typer.Option(
        False,
        "--splash/--no-splash",
        help="ASCII 아트를 출력할지 여부",
    ),
) -> None:
    """Jupyter 커널을 통해 단일 코드 셀을 실행한다."""

    if bool(code) == bool(path):
        raise typer.BadParameter("--code 또는 --path 중 하나만 지정해주세요.")

    if path is not None:
        code = path.read_text()

    assert code is not None

    if splash:
        console.print(render_splash(), style="bold cyan")

    console.print(
        Panel(
            Syntax(code, "python", theme="monokai", line_numbers=True),
            title="코드",
            border_style="cyan",
        )
    )

    try:
        with KernelSession(kernel_name=kernel) as session:
            result = session.execute(code, timeout=timeout)
    except KernelExecutionError as exc:
        console.print(Panel(str(exc), title="실행 실패", style="bold red"))
        raise typer.Exit(code=1) from exc

    _render_execution_result(result)

    if not result.succeeded:
        raise typer.Exit(code=1)


def _render_execution_result(result) -> None:
    from rich.text import Text

    if result.execution_count is not None:
        console.print(Text(f"실행 횟수: [{result.execution_count}]", style="dim"))

    if result.stdout:
        console.print(
            Panel(result.stdout.rstrip("\n") or "(empty)", title="stdout", border_style="green"),
        )
    if result.stderr:
        console.print(
            Panel(result.stderr.rstrip("\n") or "(empty)", title="stderr", border_style="red"),
        )
    if result.result:
        console.print(Panel(result.result, title="result", border_style="magenta"))

    for index, display in enumerate(result.displays, start=1):
        text_output = display.text()
        if text_output:
            console.print(
                Panel(text_output, title=f"display #{index}", border_style="blue"),
            )
        else:
            console.print(
                Panel(
                    "텍스트 외의 출력 형식은 현재 CLI에서 지원되지 않습니다.",
                    title=f"display #{index}",
                    border_style="yellow",
                )
            )

    if result.error:
        error_text = Text()
        error_text.append(f"{result.error.name}: {result.error.value}\n", style="bold red")
        if result.error.traceback:
            error_text.append("\n".join(result.error.traceback))
        console.print(Panel(error_text, title="error", border_style="red"))


def run() -> None:  # pragma: no cover - Typer 실행 래퍼
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
