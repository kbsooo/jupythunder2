"""워크플로우 실행 로직."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..agent import ExecutionPlan, PlanningAgent
from ..debugging import DebugSuggestion, DebuggingAgent
from ..history import ExecutionHistory, build_executed_cell
from ..kernel import ExecutionResult, KernelSession
from .models import Workflow, WorkflowStep


@dataclass(slots=True)
class WorkflowStepOutcome:
    """워크플로우 각 단계의 실행 결과."""

    step: WorkflowStep
    plan: Optional[ExecutionPlan] = None
    execution: Optional[ExecutionResult] = None
    suggestion: Optional[DebugSuggestion] = None


@dataclass(slots=True)
class WorkflowRunResult:
    """워크플로우 전체 실행 결과."""

    workflow: Workflow
    outcomes: List[WorkflowStepOutcome] = field(default_factory=list)
    failed_step_index: Optional[int] = None

    @property
    def success(self) -> bool:
        return self.failed_step_index is None


class WorkflowRunner:
    """워크플로우 단계를 순차적으로 실행한다."""

    def __init__(
        self,
        *,
        planning_agent: PlanningAgent,
        debugging_agent: Optional[DebuggingAgent],
        history: ExecutionHistory,
    ) -> None:
        self._planning_agent = planning_agent
        self._debugging_agent = debugging_agent
        self._history = history

    def run(
        self,
        workflow: Workflow,
        *,
        kernel_name: str = "python3",
        timeout: float = 30.0,
        suggest: bool = True,
        history_file: Optional[Path] = None,
    ) -> WorkflowRunResult:
        result = WorkflowRunResult(workflow=workflow)
        history_updated = False

        with ExitStack() as stack:
            session: Optional[KernelSession] = None

            for index, step in enumerate(workflow.steps):
                outcome = WorkflowStepOutcome(step=step)

                if step.step_type == "plan":
                    outcome.plan = self._planning_agent.draft_plan(
                        goal=step.goal or "",
                        context=step.context,
                    )
                    result.outcomes.append(outcome)
                    continue

                if step.step_type == "execute":
                    if session is None:
                        session = stack.enter_context(KernelSession(kernel_name=kernel_name))

                    execution = session.execute(step.code or "", timeout=timeout)
                    outcome.execution = execution

                    executed_cell = build_executed_cell(step.code or "", execution)
                    self._history.add(executed_cell)
                    history_updated = True

                    if not execution.succeeded and suggest and self._debugging_agent:
                        outcome.suggestion = self._debugging_agent.suggest_fix(
                            failing_code=step.code or "",
                            error_name=execution.error.name if execution.error else "UnknownError",
                            error_value=execution.error.value if execution.error else "",
                            traceback=execution.error.traceback if execution.error else [],
                            history=self._history,
                        )
                        result.failed_step_index = index
                        result.outcomes.append(outcome)
                        break

                    result.outcomes.append(outcome)
                    if not execution.succeeded:
                        result.failed_step_index = index
                        break

            if history_updated and history_file is not None:
                self._history.save(history_file)

        return result
