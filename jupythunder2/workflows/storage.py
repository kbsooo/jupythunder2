"""워크플로우 저장소 구현."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from ..config import load_runtime_settings
from .models import Workflow


def _default_directory() -> Path:
    runtime = load_runtime_settings()
    base = runtime.workflows_dir or os.getenv("JUPYTHUNDER2_WORKFLOWS_DIR")
    if base:
        return Path(base).expanduser().resolve()
    return Path.home() / ".config" / "jupythunder2" / "workflows"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip())
    slug = slug.strip("-") or "workflow"
    return slug.lower()


@dataclass(slots=True)
class WorkflowRepository:
    """워크플로우의 저장/불러오기/삭제를 담당."""

    directory: Path = None

    def __post_init__(self) -> None:
        if self.directory is None:
            self.directory = _default_directory()
        self.directory.mkdir(parents=True, exist_ok=True)

    def list(self) -> List[Workflow]:
        return [self.load_from_path(path) for path in self._iter_files()]

    def list_names(self) -> List[str]:
        return sorted(workflow.name for workflow in self.list())

    def load(self, name: str) -> Workflow:
        path = self._path_for(name)
        if not path.exists():
            raise FileNotFoundError(f"워크플로우 '{name}'을(를) 찾을 수 없습니다.")
        return self.load_from_path(path)

    def load_or_create(self, name: str, description: str = "") -> Workflow:
        try:
            return self.load(name)
        except FileNotFoundError:
            return Workflow(name=name, description=description)

    def save(self, workflow: Workflow) -> None:
        path = self._path_for(workflow.name)
        path.write_text(json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2))

    def delete(self, name: str) -> None:
        path = self._path_for(name)
        if not path.exists():
            raise FileNotFoundError(f"워크플로우 '{name}'을(를) 찾을 수 없습니다.")
        path.unlink()

    def load_from_path(self, path: Path) -> Workflow:
        data = json.loads(path.read_text())
        return Workflow.from_dict(data)

    def _iter_files(self) -> Iterable[Path]:
        if not self.directory.exists():
            return []
        return sorted(p for p in self.directory.iterdir() if p.suffix == ".json" and p.is_file())

    def _path_for(self, name: str) -> Path:
        slug = _slugify(name)
        return self.directory / f"{slug}.json"
