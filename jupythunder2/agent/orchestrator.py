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
    plan_items: List[str] = field(default_factory=list)
    code_cells: List[CodeCell] = field(default_factory=list)
    raw_text: Optional[str] = None

    def to_dict(self) -> dict:
        data = {
            "message": self.message,
            "plan": self.plan_items,
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
        if self.raw_text is not None:
            data["raw"] = self.raw_text
        return data


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
            return AgentResponse(
                message="LLM 공급자가 초기화되지 않았습니다. `/code` 명령으로 직접 코드를 실행할 수 있습니다.",
                raw_text=None,
            )

        limited_history = history[-self.settings.history_limit :]
        history_text = "\n".join(f"{item['role']}: {item['content']}" for item in limited_history)
        prompt = PROMPT_TEMPLATE.format(history=history_text, message=message)
        try:
            raw = self.llm.complete(prompt)
        except LLMProviderError as exc:
            return AgentResponse(message=f"LLM 호출에 실패했습니다: {exc}", raw_text=None)

        return self._parse_response(raw)

    # ------------------------------------------------------------------
    def _parse_response(self, raw: str) -> AgentResponse:
        payload = raw.strip()
        payload = self._strip_code_fences(payload)

        data: Optional[dict] = None
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            brace_start = payload.find("{")
            brace_end = payload.rfind("}")
            if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                candidate = payload[brace_start : brace_end + 1]
                try:
                    data = json.loads(candidate)
                except json.JSONDecodeError:
                    data = None

        if data is None:
            return AgentResponse(message=raw, raw_text=raw)

        message = str(data.get("message") or raw)
        plan_value = data.get("plan")
        plan_items = self._normalise_plan(plan_value)

        code_cells: List[CodeCell] = []
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

        return AgentResponse(message=message, plan_items=plan_items, code_cells=code_cells, raw_text=raw)

    def _strip_code_fences(self, payload: str) -> str:
        text = payload.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines:
                first = lines[0].strip()
                if first.startswith("```"):
                    lines = lines[1:]
            while lines and not lines[-1].strip():
                lines.pop()
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def _normalise_plan(self, plan_value: object) -> List[str]:
        if plan_value is None:
            return []
        if isinstance(plan_value, str):
            cleaned = plan_value.strip()
            return [cleaned] if cleaned else []
        if isinstance(plan_value, list):
            items: List[str] = []
            for item in plan_value:
                if item is None:
                    continue
                text_item = str(item).strip()
                if text_item:
                    items.append(text_item)
            return items
        return [str(plan_value)]

    def _maybe_create_llm(self, settings: JT2Settings) -> Optional[LLMProvider]:
        try:
            return LLMProvider(
                model=settings.model,
                host=settings.llm_host,
                request_timeout=settings.llm_request_timeout,
            )
        except LLMProviderError:
            return None


__all__ = ["AgentOrchestrator", "AgentResponse", "CodeCell"]
