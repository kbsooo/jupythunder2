"""개발 계획 생성 에이전트 구현."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Sequence

from ..config import AgentSettings, load_agent_settings
from .llm import DummyLLMClient, LLMClient, LLMGenerationError, OllamaLLMClient


class PlanParsingError(ValueError):
    """LLM 응답을 파싱하지 못했을 때 사용."""


@dataclass(slots=True)
class PlanStep:
    """생성된 실행 계획의 단일 단계."""

    id: int
    name: str
    description: str
    rationale: str | None = None
    dependencies: List[int] | None = None

    def dependency_label(self) -> str:
        if not self.dependencies:
            return "-"
        return ", ".join(str(dep) for dep in self.dependencies)


@dataclass(slots=True)
class ExecutionPlan:
    """LLM이 제안한 전체 실행 계획."""

    title: str
    summary: str
    steps: Sequence[PlanStep]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "steps": [
                {
                    "id": step.id,
                    "name": step.name,
                    "description": step.description,
                    "rationale": step.rationale,
                    "dependencies": step.dependencies,
                }
                for step in self.steps
            ],
        }

    def to_rich_table(self):  # pragma: no cover - 시각화는 테스트 생략
        from rich.table import Table

        table = Table(title=self.title, show_lines=False)
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("단계", style="bold")
        table.add_column("설명", overflow="fold")
        table.add_column("선행", justify="center")

        for step in self.steps:
            table.add_row(
                str(step.id),
                step.name,
                step.description,
                step.dependency_label(),
            )
        return table


class PlanningAgent:
    """LLM 기반 실행 계획 생성기."""

    def __init__(self, llm_client: LLMClient, settings: AgentSettings):
        self._llm = llm_client
        self._settings = settings

    @classmethod
    def from_env(
        cls,
        *,
        provider_override: str | None = None,
        model_override: str | None = None,
        use_dummy: bool | None = None,
    ) -> "PlanningAgent":
        settings = load_agent_settings()

        if provider_override:
            settings.provider = provider_override
        if model_override:
            settings.model = model_override

        if use_dummy is None:
            use_dummy = settings.provider.lower() == "dummy"

        if use_dummy:
            llm_client: LLMClient = DummyLLMClient()
        else:
            provider = settings.provider.lower()
            if provider != "ollama":
                raise LLMGenerationError(
                    f"지원되지 않는 LLM 제공자입니다: {settings.provider}. 현재는 'ollama' 또는 'dummy'만 지원합니다."
                )
            llm_client = OllamaLLMClient(
                model=settings.model,
                temperature=settings.temperature,
                base_url=settings.base_url,
            )

        return cls(llm_client=llm_client, settings=settings)

    def draft_plan(self, goal: str, context: str | None = None) -> ExecutionPlan:
        if not goal.strip():
            raise ValueError("goal은 비어 있을 수 없습니다.")

        prompt = self._build_prompt(goal=goal, context=context)
        response = self._safe_generate(prompt)

        try:
            plan = self._parse_response(response)
        except PlanParsingError as exc:
            if not self._settings.allow_fallback:
                raise
            fallback_response = DummyLLMClient().generate(prompt)
            plan = self._parse_response(fallback_response)
            plan.summary += "\n(LLM 응답 파싱 실패로 더미 계획을 사용했습니다.)"
            plan.title += " [Fallback]"
            from rich.console import Console  # pragma: no cover - 경고 출력

            Console().print(
                "[yellow]LLM 응답 파싱에 실패해 더미 계획으로 대체했습니다.[/yellow]"
            )
        return plan

    def _safe_generate(self, prompt: str) -> str:
        try:
            return self._llm.generate(prompt)
        except LLMGenerationError:
            if not self._settings.allow_fallback:
                raise
            return DummyLLMClient().generate(prompt)

    def _build_prompt(self, goal: str, context: str | None) -> str:
        context_block = context.strip() if context else "추가 컨텍스트 없음"
        return f"""
You are an experienced senior software engineer helping to plan work for a CLI-based Jupyter notebook agent called jupythunder2.
Always respond **only** with strict JSON using the schema below and never include extra text.

Requested goal: "{goal.strip()}"
Additional context: "{context_block}"

JSON schema:
{{
  "title": string,
  "summary": string,
  "steps": [
    {{
      "id": integer (1-based ordering),
      "name": string,
      "description": string,
      "rationale": string,
      "dependencies": array of integers (ids of prerequisite steps)
    }}
  ]
}}

Guidelines:
- Create between 4 and 7 steps.
- Each description should be concise (<= 160 chars) but actionable.
- Use dependencies to encode execution order when appropriate.
- Ensure JSON is valid and uses only double quotes.
""".strip()

    def _parse_response(self, response: str) -> ExecutionPlan:
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            raise PlanParsingError("LLM 응답이 JSON 형식이 아닙니다.") from exc

        title = str(payload.get("title", "Execution Plan")).strip()
        summary = str(payload.get("summary", "")).strip()
        steps_payload = payload.get("steps")
        if not isinstance(steps_payload, list) or not steps_payload:
            raise PlanParsingError("steps 항목이 올바르지 않습니다.")

        steps = [self._parse_step(step_data) for step_data in steps_payload]
        steps.sort(key=lambda s: s.id)
        return ExecutionPlan(title=title or "Execution Plan", summary=summary, steps=steps)

    def _parse_step(self, data: dict) -> PlanStep:
        if not isinstance(data, dict):
            raise PlanParsingError("단계 정보가 객체가 아닙니다.")

        try:
            step_id = int(data.get("id"))
        except (TypeError, ValueError) as exc:
            raise PlanParsingError("id는 정수여야 합니다.") from exc

        name = str(data.get("name", "Unnamed Step")).strip() or "Unnamed Step"
        description = str(data.get("description", "설명이 제공되지 않았습니다.")).strip()
        rationale = data.get("rationale")
        if rationale is not None:
            rationale = str(rationale).strip()
        deps_raw = data.get("dependencies")
        dependencies = self._parse_dependencies(deps_raw)
        return PlanStep(
            id=step_id,
            name=name,
            description=description,
            rationale=rationale or None,
            dependencies=dependencies,
        )

    def _parse_dependencies(self, deps: object) -> List[int] | None:
        if deps is None:
            return None
        if isinstance(deps, (list, tuple)):
            cleaned: List[int] = []
            for item in deps:
                try:
                    cleaned.append(int(item))
                except (TypeError, ValueError):
                    continue
            return cleaned or None
        try:
            value = int(deps)
            return [value]
        except (TypeError, ValueError):
            return None
