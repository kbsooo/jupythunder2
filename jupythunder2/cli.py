"""jupythunder2의 Typer 기반 CLI 진입점."""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from . import __version__
from .agent import PlanningAgent
from .ascii_art import render_splash

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


def run() -> None:  # pragma: no cover - Typer 실행 래퍼
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
