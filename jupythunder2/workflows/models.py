"""워크플로우 데이터 모델 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional


_ALLOWED_TYPES = {"plan", "execute"}


@dataclass(slots=True)
class WorkflowStep:
    """단일 워크플로우 단계."""

    step_type: Literal["plan", "execute"]
    name: Optional[str] = None
    description: str = ""
    goal: Optional[str] = None
    context: Optional[str] = None
    code: Optional[str] = None

    def __post_init__(self) -> None:
        self.step_type = self.step_type.lower()
        if self.step_type not in _ALLOWED_TYPES:
            raise ValueError(f"지원되지 않는 워크플로우 단계 타입입니다: {self.step_type}")
        if not self.name:
            self.name = "Plan" if self.step_type == "plan" else "Execute"
        self.validate()

    def validate(self) -> None:
        if self.step_type == "plan" and not self.goal:
            raise ValueError("plan 단계에는 goal이 필요합니다.")
        if self.step_type == "execute" and not self.code:
            raise ValueError("execute 단계에는 code가 필요합니다.")

    def to_dict(self) -> dict:
        return {
            "step_type": self.step_type,
            "name": self.name,
            "description": self.description,
            "goal": self.goal,
            "context": self.context,
            "code": self.code,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowStep":
        return cls(
            step_type=data.get("step_type", "execute"),
            name=data.get("name"),
            description=data.get("description", ""),
            goal=data.get("goal"),
            context=data.get("context"),
            code=data.get("code"),
        )


@dataclass(slots=True)
class Workflow:
    """여러 단계로 구성된 워크플로우."""

    name: str
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)

    def add_step(self, step: WorkflowStep) -> None:
        step.validate()
        self.steps.append(step)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        steps_data = data.get("steps", [])
        steps = [WorkflowStep.from_dict(item) for item in steps_data]
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            steps=steps,
        )

    def copy(self) -> "Workflow":
        return Workflow.from_dict(self.to_dict())
