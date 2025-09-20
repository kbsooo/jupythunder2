"""LLM-backed orchestration for planning and code generation."""
from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from typing import List, Optional

from ..config import JT2Settings
from ..llm.provider import LLMProvider, LLMProviderError


@dataclass
class CodeCell:
    code: str
    id: Optional[str] = None
    description: Optional[str] = None
    language: str = "python"


@dataclass
class AgentResponse:
    message: str
    plan: Optional[str] = None
    code_cells: List[CodeCell] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "plan": self.plan,
            "code_cells": [
                {
                    "id": cell.id,
                    "description": cell.description,
                    "language": cell.language,
                    "code": cell.code,
                }
                for cell in self.code_cells
            ],
        }


PROMPT_TEMPLATE = textwrap.dedent(
    """
    You are jupythunder2, a CLI-native coding agent that produces plans and Python code cells.
    Conversation history:
    {history}

    Latest user request:
    {message}

    Respond with a JSON object using the following schema:
    {{
      "message": "<markdown summary for the user>",
      "plan": "<concise markdown bullet plan or null>",
      "cells": [
        {{"id": "cell-1", "description": "<short text>", "language": "python", "code": "<python code>"}}
      ]
    }}

    Rules:
    - Keep code focused on the task.
    - Prefer small modular steps over monolithic scripts.
    - You may omit the plan or cells if they are unnecessary.
    - Ensure the JSON is valid and parsable.
    """
)


class AgentOrchestrator:
    """Coordinate LLM interactions to produce executable code cells."""

    def __init__(self, settings: JT2Settings, llm: Optional[LLMProvider] = None) -> None:
        self.settings = settings
        self.llm = llm or self._maybe_create_llm(settings)

    def respond(self, message: str, history: List[dict[str, str]]) -> AgentResponse:
        if self.llm is None:
            return AgentResponse(message="LLM 공급자가 초기화되지 않았습니다. `/code` 명령으로 직접 코드를 실행할 수 있습니다.")

        limited_history = history[-self.settings.history_limit :]
        history_text = "\n".join(f"{item['role']}: {item['content']}" for item in limited_history)
        prompt = PROMPT_TEMPLATE.format(history=history_text, message=message)
        try:
            raw = self.llm.complete(prompt)
        except LLMProviderError as exc:
            return AgentResponse(message=f"LLM 호출에 실패했습니다: {exc}")

        return self._parse_response(raw)

    # ------------------------------------------------------------------
    def _parse_response(self, raw: str) -> AgentResponse:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return AgentResponse(message=raw)

        message = data.get("message") or raw
        plan = data.get("plan")
        code_cells = []
        for entry in data.get("cells", []):
            code = entry.get("code")
            if not code:
                continue
            cell = CodeCell(
                id=entry.get("id"),
                description=entry.get("description"),
                language=entry.get("language", "python"),
                code=code,
            )
            code_cells.append(cell)

        return AgentResponse(message=message, plan=plan, code_cells=code_cells)

    def _maybe_create_llm(self, settings: JT2Settings) -> Optional[LLMProvider]:
        try:
            return LLMProvider(model=settings.model)
        except LLMProviderError:
            return None


__all__ = ["AgentOrchestrator", "AgentResponse", "CodeCell"]
