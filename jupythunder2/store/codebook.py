"""Notebook + Markdown logger for jt2 sessions."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import nbformat
from nbformat import NotebookNode
from nbformat import v4 as nbf

from ..agent.orchestrator import AgentResponse
from ..runtime.kernel import ExecutionError, ExecutionResult


@dataclass
class CodebookEntry:
    stem: str
    summary: str
    notebook_path: Path
    markdown_path: Path


class CodebookLogger:
    """Persist executed code and narrative context into *.ipynb/*.md pairs."""

    def __init__(
        self,
        *,
        root: Path,
        stem: str,
        summary: str,
        notebook: NotebookNode,
        markdown_path: Path,
    ) -> None:
        self.root = root.expanduser()
        self.stem = stem
        self.summary = summary.strip() or "요약 없음"
        self.notebook_path = notebook_path = self.root / f"{stem}.ipynb"
        self.markdown_path = markdown_path
        self.nb = notebook
        self._cell_indices: Dict[str, int] = {}
        self._exec_counter = self._initial_exec_counter()
        self._synchronise_cell_indices()

        # Ensure summary is the first line in markdown.
        if not self.markdown_path.exists():
            self._initialise_markdown()
        else:
            existing = self.markdown_path.read_text(encoding="utf-8").splitlines()
            if not existing:
                self._initialise_markdown()
            elif existing[0].strip() != self.summary:
                self.markdown_path.write_text("\n".join([self.summary, ""] + existing), encoding="utf-8")

        self._flush_notebook()

    # ------------------------------------------------------------------
    # factory helpers
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, root: Path, summary: str) -> "CodebookLogger":
        root = root.expanduser()
        root.mkdir(parents=True, exist_ok=True)

        base_stem = datetime.now().strftime("%m%d%H%M")
        stem = base_stem
        suffix = 1
        while any((root / f"{stem}.{ext}").exists() for ext in ("ipynb", "md")):
            suffix += 1
            stem = f"{base_stem}-{suffix:02d}"

        notebook = nbf.new_notebook()
        notebook.cells = []
        markdown_path = root / f"{stem}.md"
        return cls(root=root, stem=stem, summary=summary, notebook=notebook, markdown_path=markdown_path)

    @classmethod
    def open_existing(cls, root: Path, stem: str) -> "CodebookLogger":
        root = root.expanduser()
        notebook_path = root / f"{stem}.ipynb"
        markdown_path = root / f"{stem}.md"
        if not notebook_path.is_file() or not markdown_path.is_file():
            raise FileNotFoundError(f"코드북 '{stem}'을 찾을 수 없습니다.")

        notebook = nbformat.read(notebook_path, as_version=4)
        summary = _read_summary(markdown_path)
        return cls(root=root, stem=stem, summary=summary, notebook=notebook, markdown_path=markdown_path)

    # ------------------------------------------------------------------
    def log_user(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        section = [
            f"## {timestamp} · 사용자",
            "",
            message,
            "",
        ]
        self._append_markdown(section)

    def log_agent_response(self, response: AgentResponse) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        section: List[str] = [f"### {timestamp} · 에이전트", "", response.message, ""]
        if response.plan_items:
            section.extend(["#### 계획", ""])
            section.extend(f"- {item}" for item in response.plan_items)
            section.append("")
        self._append_markdown(section)

    def log_system_message(self, title: str, body: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = body.strip()
        section = [f"### {timestamp} · 시스템 · {title}", "", message, ""]
        self._append_markdown(section)

    # ------------------------------------------------------------------
    def register_code_cell(
        self,
        cell_id: str,
        code: str,
        *,
        description: Optional[str] = None,
        origin: str = "agent",
    ) -> None:
        if cell_id in self._cell_indices:
            return

        title = f"#### 코드 셀 {cell_id}"
        if description:
            title += f" · {description}"
        self._append_markdown([title, "", "```python", code, "```", ""])

        nb_cell = nbf.new_code_cell(
            source=code,
            metadata={"origin": origin, "cell_id": cell_id, "description": description},
        )
        self.nb.cells.append(nb_cell)
        self._cell_indices[cell_id] = len(self.nb.cells) - 1
        self._flush_notebook()

    def record_execution(self, cell_id: str, result: ExecutionResult) -> None:
        idx = self._cell_indices.get(cell_id)
        if idx is None:
            return

        cell = self.nb.cells[idx]
        outputs = list(self._build_outputs(result))
        cell["execution_count"] = self._exec_counter
        cell["outputs"] = outputs
        self._exec_counter += 1
        self._flush_notebook()

        section: List[str] = [f"#### 실행 결과 · {cell_id}", ""]
        if result.stdout:
            section.extend(["```text", result.stdout.strip(), "```", ""])
        if result.stderr:
            section.extend(["```text", result.stderr.strip(), "```", ""])
        if result.result_text:
            section.extend([f"> {result.result_text.strip()}", ""])
        if result.error is not None:
            section.extend([f"⚠️ 오류: {result.error.ename}: {result.error.evalue}", ""])
            if result.error.traceback:
                excerpt = "\n".join(result.error.traceback[:20]).strip()
                if excerpt:
                    section.extend(["```text", excerpt, "```", ""])
        if result.images:
            section.append("#### 이미지")
            section.append("")
            for idx, image_path in enumerate(result.images, start=1):
                reference = self._relative_image_path(image_path)
                section.append(f"![{cell_id} · 이미지 {idx}]({reference})")
            section.append("")
        self._append_markdown(section)

    # ------------------------------------------------------------------
    def _initialise_markdown(self) -> None:
        lines = [
            self.summary,
            "",
            f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 노트북 파일: `{self.stem}.ipynb`",
            "",
        ]
        self.markdown_path.write_text("\n".join(lines), encoding="utf-8")

    def _append_markdown(self, lines: List[str]) -> None:
        with self.markdown_path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def _flush_notebook(self) -> None:
        nbformat.write(self.nb, self.notebook_path)

    def _initial_exec_counter(self) -> int:
        counters = [cell.get("execution_count") for cell in self.nb.cells if cell.get("execution_count")]
        return (max(counters) + 1) if counters else 1

    def _synchronise_cell_indices(self) -> None:
        self._cell_indices.clear()
        for idx, cell in enumerate(self.nb.cells):
            cell_id = cell.metadata.get("cell_id") if hasattr(cell, "metadata") else None
            if cell_id:
                self._cell_indices[cell_id] = idx

    def _build_outputs(self, result: ExecutionResult) -> Iterable[NotebookNode]:
        if result.stdout:
            yield nbf.new_output("stream", name="stdout", text=result.stdout)
        if result.stderr:
            yield nbf.new_output("stream", name="stderr", text=result.stderr)
        if result.result_text:
            yield nbf.new_output(
                "execute_result",
                data={"text/plain": result.result_text},
                metadata={},
                execution_count=self._exec_counter,
            )
        for image_path in result.images:
            try:
                payload = image_path.read_bytes()
            except OSError:
                continue
            yield nbf.new_output(
                "display_data",
                data={"image/png": base64.b64encode(payload).decode("ascii")},
                metadata={},
            )
        if result.error is not None:
            yield self._error_output(result.error)

    def _relative_image_path(self, path: Path) -> str:
        base = self.markdown_path.parent
        try:
            rel = os.path.relpath(path, base)
        except ValueError:
            rel = str(path)
        return Path(rel).as_posix()

    def _error_output(self, error: ExecutionError) -> NotebookNode:
        return nbf.new_output(
            "error",
            ename=error.ename,
            evalue=error.evalue,
            traceback=error.traceback,
        )


# ---------------------------------------------------------------------------
# discovery helpers
# ---------------------------------------------------------------------------

def discover_codebooks(root: Path) -> List[CodebookEntry]:
    root = root.expanduser()
    if not root.is_dir():
        return []

    entries: List[CodebookEntry] = []
    for md_path in sorted(root.glob("*.md"), reverse=True):
        stem = md_path.stem
        notebook_path = root / f"{stem}.ipynb"
        if not notebook_path.exists():
            continue
        summary = _read_summary(md_path)
        entries.append(CodebookEntry(stem=stem, summary=summary, notebook_path=notebook_path, markdown_path=md_path))
    return entries


def _read_summary(markdown_path: Path) -> str:
    try:
        first_line = markdown_path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return "요약 없음"
    return first_line.strip() or "요약 없음"


__all__ = ["CodebookLogger", "CodebookEntry", "discover_codebooks"]
