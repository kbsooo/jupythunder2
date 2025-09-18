from pathlib import Path

import pytest

from jupythunder2.agent import PlanningAgent
from jupythunder2.debugging import DebuggingAgent
from jupythunder2.history import ExecutionHistory
from jupythunder2.workflows import (
    Workflow,
    WorkflowRepository,
    WorkflowRunner,
    WorkflowStep,
)


def test_workflow_repository_roundtrip(tmp_path: Path):
    repo = WorkflowRepository(directory=tmp_path)
    workflow = Workflow(name="demo", description="테스트 워크플로우")
    workflow.add_step(
        WorkflowStep(step_type="plan", goal="테스트 목표", context="추가", name="계획"),
    )
    workflow.add_step(
        WorkflowStep(step_type="execute", code="print('hello')", name="실행"),
    )

    repo.save(workflow)

    names = repo.list_names()
    assert names == ["demo"]

    loaded = repo.load("demo")
    assert loaded.name == workflow.name
    assert len(loaded.steps) == 2
    assert loaded.steps[0].goal == "테스트 목표"
    assert "print" in loaded.steps[1].code

    repo.delete("demo")
    assert repo.list_names() == []


@pytest.mark.parametrize("code", ["sum(range(5))", "1/0"])
def test_workflow_runner_executes_steps(code: str, tmp_path: Path):
    workflow = Workflow(name="runner")
    workflow.add_step(WorkflowStep(step_type="plan", goal="테스트", name="계획"))
    workflow.add_step(WorkflowStep(step_type="execute", code=code, name="실행"))

    history_path = tmp_path / "history.json"
    history = ExecutionHistory(limit=5)

    runner = WorkflowRunner(
        planning_agent=PlanningAgent.from_env(use_dummy=True),
        debugging_agent=DebuggingAgent.from_env(use_dummy=True),
        history=history,
    )

    result = runner.run(
        workflow,
        kernel_name="python3",
        timeout=15.0,
        suggest=True,
        history_file=history_path,
    )

    assert result.outcomes
    assert history_path.exists()

    if code == "sum(range(5))":
        assert result.success
        assert len(history.recent()) == 1
        assert history.recent()[-1].result.strip("\n") == "10"
    else:
        assert not result.success
        assert result.failed_step_index == 1
        assert result.outcomes[-1].suggestion is not None


def test_workflow_runner_stops_after_failure(tmp_path: Path):
    workflow = Workflow(name="runner")
    workflow.add_step(WorkflowStep(step_type="execute", code="1/0", name="fail"))
    workflow.add_step(WorkflowStep(step_type="execute", code="print('after')", name="after"))

    history = ExecutionHistory(limit=5)
    runner = WorkflowRunner(
        planning_agent=PlanningAgent.from_env(use_dummy=True),
        debugging_agent=DebuggingAgent.from_env(use_dummy=True),
        history=history,
    )

    result = runner.run(workflow, kernel_name="python3", suggest=True)

    assert not result.success
    assert len(result.outcomes) == 1
    assert history.recent()[-1].error_name == "ZeroDivisionError"


def test_workflow_modification_commands(tmp_path):
    repo = WorkflowRepository(directory=tmp_path)
    workflow = Workflow(name="demo")
    workflow.add_step(WorkflowStep(step_type="plan", goal="a", name="1"))
    workflow.add_step(WorkflowStep(step_type="execute", code="print('2')", name="2"))
    workflow.add_step(WorkflowStep(step_type="execute", code="print('3')", name="3"))
    repo.save(workflow)

    loaded = repo.load("demo")
    loaded.move_step(0, 2)
    repo.save(loaded)
    assert [step.name for step in repo.load("demo").steps] == ["2", "3", "1"]

    removed = loaded.remove_step(1)
    assert removed.name == "3"
    repo.save(loaded)
    assert [step.name for step in repo.load("demo").steps] == ["2", "1"]
