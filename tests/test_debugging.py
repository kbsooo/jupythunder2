from pathlib import Path

import pytest

from jupythunder2.config import AgentSettings
from jupythunder2.debugging import DebuggingAgent
from jupythunder2.history import ExecutedCell, ExecutionHistory


class BrokenLLM:
    def generate(self, prompt: str) -> str:  # pragma: no cover - 테스트용 더미
        return "not-json"


def test_execution_history_persistence(tmp_path: Path):
    history = ExecutionHistory(limit=2)
    history.add(
        ExecutedCell(
            code="print(1)",
            stdout="1\n",
            stderr="",
            result=None,
            error_name=None,
            error_value=None,
            traceback=[],
            execution_count=1,
        )
    )
    history.add(
        ExecutedCell(
            code="1/0",
            stdout="",
            stderr="",
            result=None,
            error_name="ZeroDivisionError",
            error_value="division by zero",
            traceback=["Traceback"],
            execution_count=2,
        )
    )
    history.add(
        ExecutedCell(
            code="sum(range(3))",
            stdout="",
            stderr="",
            result="3",
            error_name=None,
            error_value=None,
            traceback=[],
            execution_count=3,
        )
    )

    path = tmp_path / "history.json"
    history.save(path)

    loaded = ExecutionHistory.load(path, limit=2)
    recent = loaded.recent()

    assert len(recent) == 2
    assert recent[-1].result == "3"
    assert recent[-2].error_name == "ZeroDivisionError"


def test_debugging_agent_with_dummy_history():
    history = ExecutionHistory(limit=5)
    history.add(
        ExecutedCell(
            code="value = 0",
            stdout="",
            stderr="",
            result=None,
            error_name=None,
            error_value=None,
            traceback=[],
            execution_count=1,
        )
    )

    agent = DebuggingAgent.from_env(use_dummy=True)

    suggestion = agent.suggest_fix(
        failing_code="1 / value",
        error_name="ZeroDivisionError",
        error_value="division by zero",
        traceback=["ZeroDivisionError: division by zero"],
        history=history,
    )

    assert suggestion.summary
    assert suggestion.recommendation


def test_debugging_agent_fallback_on_bad_json():
    agent = DebuggingAgent(llm_client=BrokenLLM(), settings=AgentSettings())
    history = ExecutionHistory(limit=5)

    suggestion = agent.suggest_fix(
        failing_code="foo",
        error_name="NameError",
        error_value="name 'foo' is not defined",
        traceback=["NameError: name 'foo' is not defined"],
        history=history,
    )

    assert "NameError" in suggestion.summary
    assert "수정" in suggestion.recommendation or suggestion.recommendation
