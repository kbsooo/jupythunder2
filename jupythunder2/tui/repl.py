"""Interactive REPL loop for jupythunder2."""
from __future__ import annotations

import shlex
import uuid
from dataclasses import dataclass
from typing import Dict, List

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ..agent.orchestrator import AgentOrchestrator, AgentResponse, CodeCell
from ..config import JT2Settings
from ..debug.diagnostics import Debugger
from ..runtime.kernel import ExecutionResult, KernelRunner
from ..store.session import SessionStore


@dataclass
class PendingCell:
    cell: CodeCell
    origin: str = "agent"


class JT2Repl:
    """High-level orchestration for interactive jt2 sessions."""

    def __init__(self, settings: JT2Settings) -> None:
        self.settings = settings
        self.console = Console()
        self.session = PromptSession(history=InMemoryHistory(), auto_suggest=AutoSuggestFromHistory())
        self.store = SessionStore(settings.run_root)
        self.session_dir = self.store.start_session()
        self.kernel = KernelRunner()
        self.debugger = Debugger()
        self.orchestrator = AgentOrchestrator(settings=settings)
        self.pending_cells: Dict[str, PendingCell] = {}
        self.history: List[dict[str, str]] = []
        self.auto_execute = settings.auto_execute
        self.running = True

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Start the interactive prompt loop."""
        self.console.print("[bold green]인터랙티브 세션을 시작합니다. `/help` 로 명령어를 확인하세요.[/]")
        with patch_stdout():
            while self.running:
                try:
                    user_input = self.session.prompt("jt2> ")
                except EOFError:
                    self.console.print("\n[bold yellow]EOF 감지, 세션을 종료합니다.[/]")
                    break

                stripped = user_input.strip()
                if not stripped:
                    continue

                if stripped.startswith("/"):
                    if not self._handle_command(stripped):
                        break
                    continue

                self._handle_user_message(stripped)

    def shutdown(self) -> None:
        """Release resources gracefully."""
        self.kernel.shutdown()
        self.store.finish_session()

    # ------------------------------------------------------------------
    # user message processing
    # ------------------------------------------------------------------
    def _handle_user_message(self, message: str) -> None:
        self.history.append({"role": "user", "content": message})
        self.store.append_event("user", {"message": message})

        response = self.orchestrator.respond(message=message, history=self.history)
        self._render_agent_response(response)
        self.history.append({"role": "assistant", "content": response.message})
        self.store.append_event("assistant", response.to_dict())

        if response.code_cells:
            for cell in response.code_cells:
                cell_id = cell.id or self._make_cell_id(prefix="agent")
                if not cell.id:
                    cell.id = cell_id
                tracked = PendingCell(cell=cell, origin="agent")
                self.pending_cells[cell_id] = tracked
                self.console.print(Panel(cell.code, title=f"pending {cell_id}", subtitle=cell.description or "", highlight=True))
            if self.auto_execute:
                self._execute_cells(list(self.pending_cells.keys()))

    def _render_agent_response(self, response: AgentResponse) -> None:
        self.console.print(Panel(Markdown(response.message), title="에이전트"))
        if response.plan:
            self.console.print(Panel(Markdown(response.plan), title="계획"))

    # ------------------------------------------------------------------
    # commands
    # ------------------------------------------------------------------
    def _handle_command(self, raw: str) -> bool:
        parts = shlex.split(raw[1:])
        if not parts:
            return True
        command, *rest = parts

        if command in {"quit", "exit"}:
            self.console.print("[bold magenta]세션을 종료합니다.[/]")
            self.running = False
            return False
        if command == "help":
            self._command_help()
            return True
        if command == "auto" and rest:
            self._command_auto(rest[0])
            return True
        if command == "reset":
            self._command_reset()
            return True
        if command == "cells":
            self._command_cells()
            return True
        if command == "exec" and rest:
            self._command_exec(rest)
            return True
        if command == "code":
            self._command_code(rest)
            return True

        self.console.print(f"[bold red]알 수 없는 명령어:[/] {command}")
        return True

    def _command_help(self) -> None:
        self.console.print(
            Panel(
                "\n".join(
                    [
                        "/help : 명령어 목록 표시",
                        "/quit : 세션 종료",
                        "/auto on|off : 코드 자동 실행 토글",
                        "/reset : Jupyter 커널 재시작",
                        "/cells : 대기 중인 코드 셀 목록",
                        "/exec <cell-id|all> : 코드 셀 실행",
                        "/code <python> : 즉시 실행할 파이썬 코드 큐에 추가",
                    ]
                ),
                title="명령어",
            )
        )

    def _command_auto(self, value: str) -> None:
        normalized = value.lower()
        if normalized not in {"on", "off"}:
            self.console.print("[bold red]/auto 는 on 또는 off 중 하나를 필요로 합니다.[/]")
            return
        self.auto_execute = normalized == "on"
        self.console.print(f"자동 실행 모드가 {'ON' if self.auto_execute else 'OFF'} 로 설정되었습니다.")

    def _command_reset(self) -> None:
        self.console.print("[yellow]커널을 재시작합니다...[/]")
        self.kernel.restart()
        self.store.append_event("system", {"action": "reset_kernel"})

    def _command_cells(self) -> None:
        if not self.pending_cells:
            self.console.print("[dim]대기 중인 코드 셀이 없습니다.[/]")
            return
        lines = []
        for cell_id, tracked in self.pending_cells.items():
            desc = tracked.cell.description or ""
            lines.append(f"- [bold]{cell_id}[/]: {desc}")
        self.console.print(Panel("\n".join(lines), title="대기 셀"))

    def _command_exec(self, args: List[str]) -> None:
        target = args[0]
        if target == "all":
            ids = list(self.pending_cells.keys())
        else:
            ids = [target]
        self._execute_cells(ids)

    def _command_code(self, parts: List[str]) -> None:
        if not parts:
            self.console.print("[bold red]/code 명령은 파이썬 코드를 인라인으로 입력해야 합니다.[/]")
            return
        code = " ".join(parts)
        cell_id = self._make_cell_id(prefix="manual")
        cell = CodeCell(id=cell_id, description="manual input", language="python", code=code)
        tracked = PendingCell(cell=cell, origin="user")
        self.pending_cells[cell_id] = tracked
        self.console.print(Panel(code, title=f"pending {cell_id}", subtitle="manual input"))
        if self.auto_execute:
            self._execute_cells([cell_id])

    # ------------------------------------------------------------------
    # execution helpers
    # ------------------------------------------------------------------
    def _execute_cells(self, cell_ids: List[str]) -> None:
        for cell_id in cell_ids:
            tracked = self.pending_cells.pop(cell_id, None)
            if not tracked:
                self.console.print(f"[bold red]셀을 찾을 수 없습니다:[/] {cell_id}")
                continue
            self._execute_cell(cell_id, tracked)

    def _execute_cell(self, cell_id: str, tracked: PendingCell) -> None:
        self.console.print(f"[cyan]실행 중...[/] {cell_id}")
        result = self.kernel.execute(
            code=tracked.cell.code,
            timeout=self.settings.max_execution_seconds,
            artifact_dir=self.session_dir,
        )
        self.store.append_event(
            "execution",
            {
                "cell_id": cell_id,
                "origin": tracked.origin,
                "code": tracked.cell.code,
                "result": result.to_dict(),
            },
        )
        self._render_execution_result(result)

    def _render_execution_result(self, result: ExecutionResult) -> None:
        blocks = []
        if result.stdout:
            blocks.append(Panel(result.stdout, title="stdout"))
        if result.stderr:
            blocks.append(Panel(result.stderr, title="stderr", style="red"))
        if result.result_text:
            blocks.append(Panel(result.result_text, title="result"))
        for image_path in result.images:
            blocks.append(Panel(str(image_path), title="image"))
        if result.error is not None:
            summary = self.debugger.summarize(result.error)
            panel_text = summary.explanation
            if summary.suggestion:
                panel_text += f"\n\n제안: {summary.suggestion}"
            blocks.append(Panel(Markdown(panel_text), title="디버그", style="yellow"))

        if not blocks:
            blocks.append(Panel("(no output)", title="결과"))

        for block in blocks:
            self.console.print(block)

    # ------------------------------------------------------------------
    # utils
    # ------------------------------------------------------------------
    def _make_cell_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:6]}"


__all__ = ["JT2Repl"]
