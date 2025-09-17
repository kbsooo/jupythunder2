"""코드 실행 히스토리를 관리하는 모듈."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from .kernel import ExecutionResult


@dataclass(slots=True)
class ExecutedCell:
    """단일 코드 셀 실행 기록."""

    code: str
    stdout: str
    stderr: str
    result: Optional[str]
    error_name: Optional[str]
    error_value: Optional[str]
    traceback: List[str] = field(default_factory=list)
    execution_count: Optional[int] = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["traceback"] = list(self.traceback)
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutedCell":
        return cls(
            code=str(data.get("code", "")),
            stdout=str(data.get("stdout", "")),
            stderr=str(data.get("stderr", "")),
            result=data.get("result"),
            error_name=data.get("error_name"),
            error_value=data.get("error_value"),
            traceback=list(data.get("traceback", [])),
            execution_count=data.get("execution_count"),
        )


class ExecutionHistory:
    """최근 코드 실행 기록을 메모리/파일로 관리한다."""

    def __init__(self, *, limit: int = 20, entries: Optional[List[ExecutedCell]] = None) -> None:
        self._limit = limit
        self._entries: List[ExecutedCell] = list(entries or [])[-limit:]

    def add(self, cell: ExecutedCell) -> None:
        self._entries.append(cell)
        if len(self._entries) > self._limit:
            self._entries = self._entries[-self._limit :]

    def recent(self, count: Optional[int] = None) -> List[ExecutedCell]:
        if count is None:
            return list(self._entries)
        return list(self._entries)[-count:]

    def to_json(self) -> str:
        return json.dumps([entry.to_dict() for entry in self._entries], ensure_ascii=False, indent=2)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    @classmethod
    def load(cls, path: Path, *, limit: int = 20) -> "ExecutionHistory":
        if not path.exists():
            return cls(limit=limit)
        entries_json = json.loads(path.read_text() or "[]")
        entries = [ExecutedCell.from_dict(item) for item in entries_json]
        return cls(limit=limit, entries=entries)


def build_executed_cell(code: str, result: ExecutionResult) -> ExecutedCell:
    """ExecutionResult를 히스토리 엔트리로 변환한다."""

    error = result.error
    return ExecutedCell(
        code=code,
        stdout=result.stdout,
        stderr=result.stderr,
        result=result.result,
        error_name=error.name if error else None,
        error_value=error.value if error else None,
        traceback=error.traceback if error else [],
        execution_count=result.execution_count,
    )
