"""jupythunder2의 Typer 기반 CLI 진입점."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from . import __version__
from .agent import PlanningAgent
from .ascii_art import render_splash
from .debugging import DebuggingAgent
from .history import ExecutionHistory, build_executed_cell
from .kernel import KernelExecutionError, KernelSession
from .workflows import Workflow, WorkflowRepository, WorkflowRunner, WorkflowStep

app = typer.Typer(help="jupythunder2 CLI 에이전트")
workflow_app = typer.Typer(help="워크플로우 자동화")
app.add_typer(workflow_app, name="workflow")
console = Console()


def _load_history(history_file: Optional[Path], history_limit: int) -> ExecutionHistory:
    if history_file is not None:
        return ExecutionHistory.load(history_file, limit=history_limit)
    return ExecutionHistory(limit=history_limit)


def _render_plan(plan) -> None:
    console.print(Panel(plan.summary or "요약 정보가 제공되지 않았습니다.", title="요약"))
    console.print(plan.to_rich_table())


def _render_code_panel(code: str, *, title: str = "코드") -> None:
    console.print(
        Panel(
            Syntax(code, "python", theme="monokai", line_numbers=True),
            title=title,
            border_style="cyan",
        )
    )


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

    _render_plan(execution_plan)


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
    history_file: Optional[Path] = typer.Option(
        None,
        "--history-file",
        "-f",
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="실행 히스토리를 저장/불러올 JSON 파일",
    ),
    history_limit: int = typer.Option(
        20,
        "--history-limit",
        min=1,
        max=200,
        help="히스토리에 보관할 최대 셀 개수",
    ),
    splash: bool = typer.Option(
        False,
        "--splash/--no-splash",
        help="ASCII 아트를 출력할지 여부",
    ),
    suggest: bool = typer.Option(
        True,
        "--suggest/--no-suggest",
        help="오류 발생 시 LLM 기반 수정 제안을 출력",
    ),
    debug_provider: Optional[str] = typer.Option(
        None,
        "--debug-provider",
        help="디버깅 제안에 사용할 LLM 제공자",
    ),
    debug_model: Optional[str] = typer.Option(
        None,
        "--debug-model",
        help="디버깅 제안에 사용할 모델 이름",
    ),
    debug_dummy: bool = typer.Option(
        False,
        "--debug-dummy",
        help="LLM 대신 더미 디버깅 제안을 사용",
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

    history = _load_history(history_file, history_limit)

    _render_code_panel(code)

    try:
        with KernelSession(kernel_name=kernel) as session:
            result = session.execute(code, timeout=timeout)
    except KernelExecutionError as exc:
        console.print(Panel(str(exc), title="실행 실패", style="bold red"))
        raise typer.Exit(code=1) from exc

    executed_cell = build_executed_cell(code, result)
    history.add(executed_cell)
    if history_file is not None:
        history.save(history_file)

    _render_execution_result(result)

    if not result.succeeded:
        if suggest:
            agent = DebuggingAgent.from_env(
                provider_override=debug_provider,
                model_override=debug_model,
                use_dummy=True if debug_dummy else None,
            )
            suggestion = agent.suggest_fix(
                failing_code=code,
                error_name=result.error.name if result.error else "UnknownError",
                error_value=result.error.value if result.error else "",
                traceback=result.error.traceback if result.error else [],
                history=history,
            )
            _render_debug_suggestion(suggestion)
        raise typer.Exit(code=1)


@workflow_app.command("list", short_help="저장된 워크플로우 나열")
def workflow_list() -> None:
    repo = WorkflowRepository()
    workflows = repo.list()
    if not workflows:
        console.print("저장된 워크플로우가 없습니다.", style="yellow")
        return

    table = Table(title="워크플로우 목록")
    table.add_column("이름", style="bold")
    table.add_column("단계 수", justify="right")
    table.add_column("설명")

    for workflow in workflows:
        table.add_row(workflow.name, str(len(workflow.steps)), workflow.description or "-")

    console.print(table)


@workflow_app.command("show", short_help="워크플로우 상세 보기")
def workflow_show(name: str) -> None:
    repo = WorkflowRepository()
    try:
        workflow = repo.load(name)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"워크플로우 '{name}'을(를) 찾을 수 없습니다.") from exc

    console.print(
        Panel(
            workflow.description or "설명 없음",
            title=f"Workflow: {workflow.name}",
            border_style="cyan",
        )
    )

    if not workflow.steps:
        console.print("등록된 단계가 없습니다.", style="yellow")
        return

    for index, step in enumerate(workflow.steps, start=1):
        header = f"[{index}] {step.name} ({step.step_type})"
        body_lines = []
        if step.description:
            body_lines.append(step.description)
        if step.step_type == "plan":
            if step.goal:
                body_lines.append(f"goal: {step.goal}")
            if step.context:
                body_lines.append(f"context: {step.context}")
        body = "\n".join(line for line in body_lines if line) or "설명 없음"
        console.print(Panel(body, title=header, border_style="blue"))

        if step.step_type == "execute" and step.code:
            _render_code_panel(step.code, title="코드")


@workflow_app.command("delete", short_help="워크플로우 삭제")
def workflow_delete(
    name: str,
    force: bool = typer.Option(False, "--force", "-f", help="확인 없이 삭제"),
) -> None:
    repo = WorkflowRepository()
    try:
        repo.load(name)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"워크플로우 '{name}'을(를) 찾을 수 없습니다.") from exc

    if not force and not typer.confirm(f"워크플로우 '{name}'을(를) 삭제할까요?", default=False):
        console.print("삭제를 취소했습니다.", style="dim")
        return

    repo.delete(name)
    console.print(f"워크플로우 '{name}'을(를) 삭제했습니다.", style="bold red")


@workflow_app.command("add-plan", short_help="plan 단계 추가")
def workflow_add_plan(
    name: str,
    goal: str = typer.Option(..., "--goal", help="계획 단계에서 사용할 목표"),
    context: Optional[str] = typer.Option(None, "--context", help="추가 컨텍스트"),
    title: Optional[str] = typer.Option(None, "--title", help="단계 제목"),
    description: str = typer.Option("", "--description", "-d", help="단계 설명"),
    workflow_description: Optional[str] = typer.Option(
        None,
        "--workflow-description",
        help="워크플로우 자체 설명 (신규 또는 업데이트)",
    ),
) -> None:
    repo = WorkflowRepository()
    created = False
    try:
        workflow = repo.load(name)
    except FileNotFoundError:
        workflow = Workflow(name=name, description=workflow_description or "")
        created = True
    else:
        if workflow_description is not None:
            workflow.description = workflow_description

    step = WorkflowStep(
        step_type="plan",
        name=title,
        description=description,
        goal=goal,
        context=context,
    )
    workflow.add_step(step)
    repo.save(workflow)

    console.print(
        f"워크플로우 '{workflow.name}'에 plan 단계를 추가했습니다. (총 {len(workflow.steps)}단계)",
        style="green",
    )
    if created:
        console.print("새 워크플로우가 생성되었습니다.", style="dim")


@workflow_app.command("add-exec", short_help="execute 단계 추가")
def workflow_add_execute(
    name: str,
    code: Optional[str] = typer.Option(
        None,
        "--code",
        "-c",
        help="실행할 파이썬 코드",
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
        help="코드가 담긴 파일 경로",
    ),
    title: Optional[str] = typer.Option(None, "--title", help="단계 제목"),
    description: str = typer.Option("", "--description", "-d", help="단계 설명"),
    workflow_description: Optional[str] = typer.Option(
        None,
        "--workflow-description",
        help="워크플로우 자체 설명 (신규 또는 업데이트)",
    ),
) -> None:
    if bool(code) == bool(path):
        raise typer.BadParameter("--code 또는 --path 중 하나만 지정해주세요.")

    if path is not None:
        code = path.read_text()

    assert code is not None

    repo = WorkflowRepository()
    created = False
    try:
        workflow = repo.load(name)
    except FileNotFoundError:
        workflow = Workflow(name=name, description=workflow_description or "")
        created = True
    else:
        if workflow_description is not None:
            workflow.description = workflow_description

    step = WorkflowStep(
        step_type="execute",
        name=title,
        description=description,
        code=code,
    )
    workflow.add_step(step)
    repo.save(workflow)

    console.print(
        f"워크플로우 '{workflow.name}'에 execute 단계를 추가했습니다. (총 {len(workflow.steps)}단계)",
        style="green",
    )
    if created:
        console.print("새 워크플로우가 생성되었습니다.", style="dim")


@workflow_app.command("run", short_help="워크플로우 실행")
def workflow_run(
    name: str,
    kernel: str = typer.Option("python3", "--kernel", help="사용할 커널 이름"),
    timeout: float = typer.Option(
        30.0,
        "--timeout",
        min=1.0,
        max=300.0,
        help="커널 응답 대기 시간(초)",
    ),
    history_file: Optional[Path] = typer.Option(
        None,
        "--history-file",
        "-f",
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="실행 히스토리를 저장/불러올 JSON 파일",
    ),
    history_limit: int = typer.Option(
        50,
        "--history-limit",
        min=1,
        max=500,
        help="히스토리에 보관할 최대 셀 개수",
    ),
    splash: bool = typer.Option(
        False,
        "--splash/--no-splash",
        help="ASCII 아트를 출력할지 여부",
    ),
    suggest: bool = typer.Option(
        True,
        "--suggest/--no-suggest",
        help="오류 발생 시 디버깅 제안을 사용할지 여부",
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="Planning LLM 제공자",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="Planning LLM 모델",
    ),
    dummy: bool = typer.Option(
        False,
        "--dummy",
        help="Planning LLM 더미 사용",
    ),
    debug_provider: Optional[str] = typer.Option(
        None,
        "--debug-provider",
        help="디버깅 LLM 제공자",
    ),
    debug_model: Optional[str] = typer.Option(
        None,
        "--debug-model",
        help="디버깅 LLM 모델",
    ),
    debug_dummy: bool = typer.Option(
        False,
        "--debug-dummy",
        help="디버깅용 더미 LLM 사용",
    ),
) -> None:
    repo = WorkflowRepository()
    try:
        workflow = repo.load(name)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"워크플로우 '{name}'을(를) 찾을 수 없습니다.") from exc

    if splash:
        console.print(render_splash(), style="bold cyan")

    history = _load_history(history_file, history_limit)

    planning_agent = PlanningAgent.from_env(
        provider_override=provider,
        model_override=model,
        use_dummy=True if dummy else None,
    )

    debugging_agent = None
    if suggest:
        debugging_agent = DebuggingAgent.from_env(
            provider_override=debug_provider,
            model_override=debug_model,
            use_dummy=True if debug_dummy else None,
        )

    runner = WorkflowRunner(
        planning_agent=planning_agent,
        debugging_agent=debugging_agent,
        history=history,
    )

    run_result = runner.run(
        workflow,
        kernel_name=kernel,
        timeout=timeout,
        suggest=suggest and debugging_agent is not None,
        history_file=history_file,
    )

    console.print(
        Panel(
            workflow.description or "설명 없음",
            title=f"Workflow: {workflow.name}",
            border_style="cyan",
        )
    )

    for index, outcome in enumerate(run_result.outcomes, start=1):
        step = outcome.step
        header = f"[{index}] {step.name} ({step.step_type})"
        body_lines = []
        if step.description:
            body_lines.append(step.description)
        if step.step_type == "plan":
            if step.goal:
                body_lines.append(f"goal: {step.goal}")
            if step.context:
                body_lines.append(f"context: {step.context}")
        body = "\n".join(line for line in body_lines if line) or "설명 없음"
        console.print(Panel(body, title=header, border_style="blue"))

        if step.step_type == "execute" and step.code:
            _render_code_panel(step.code, title="코드")
        if outcome.plan:
            _render_plan(outcome.plan)
        if outcome.execution:
            _render_execution_result(outcome.execution)
        if outcome.suggestion:
            _render_debug_suggestion(outcome.suggestion)

    if run_result.success:
        console.print("워크플로우가 성공적으로 완료되었습니다.", style="bold green")
    else:
        failed_idx = (run_result.failed_step_index or 0) + 1
        console.print(f"{failed_idx}번째 단계에서 실패했습니다.", style="bold red")
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


def _render_debug_suggestion(suggestion) -> None:
    from rich.markdown import Markdown

    console.print(Panel(suggestion.summary, title="디버깅 요약", border_style="magenta"))
    console.print(Panel(suggestion.root_cause or "원인 정보를 제공하지 않았습니다.", title="가능한 원인", border_style="yellow"))
    console.print(Panel(suggestion.recommendation, title="권장 조치", border_style="green"))

    if suggestion.patch:
        console.print(Panel(Markdown(f"```\n{suggestion.patch}\n```"), title="제안된 패치", border_style="cyan"))


def run() -> None:  # pragma: no cover - Typer 실행 래퍼
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
