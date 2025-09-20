from jupythunder2.agent.orchestrator import AgentOrchestrator
from jupythunder2.config import JT2Settings


def test_parse_response_extracts_plan_and_cells() -> None:
    settings = JT2Settings()
    orchestrator = AgentOrchestrator(settings=settings, llm=None)

    raw = """
    {
      "message": "done",
      "plan": ["step one", "step two"],
      "cells": [
        {"id": "cell-1", "description": "demo", "language": "python", "code": "print('ok')"}
      ]
    }
    """

    response = orchestrator._parse_response(raw)

    assert response.message == "done"
    assert response.plan_items == ["step one", "step two"]
    assert len(response.code_cells) == 1
    assert response.code_cells[0].code.strip() == "print('ok')"


def test_parse_response_handles_code_fences() -> None:
    settings = JT2Settings()
    orchestrator = AgentOrchestrator(settings=settings, llm=None)

    raw = """```json
    {
      "message": "fenced",
      "plan": "single step",
      "cells": []
    }
    ```"""

    response = orchestrator._parse_response(raw)

    assert response.message == "fenced"
    assert response.plan_items == ["single step"]
    assert response.code_cells == []
