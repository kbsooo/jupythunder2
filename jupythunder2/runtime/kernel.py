"""Wrapper around jupyter_client to execute code cells."""
from __future__ import annotations

import base64
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from jupyter_client import KernelManager
from jupyter_client.blocking import BlockingKernelClient
from jupyter_client.kernelspec import NoSuchKernel


@dataclass
class ExecutionError:
    ename: str
    evalue: str
    traceback: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {"ename": self.ename, "evalue": self.evalue, "traceback": self.traceback}


@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    result_text: str = ""
    images: List[Path] = field(default_factory=list)
    error: Optional[ExecutionError] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "result_text": self.result_text,
            "images": [str(path) for path in self.images],
            "error": self.error.to_dict() if self.error else None,
        }


class KernelRunner:
    """Manage a Jupyter kernel lifecycle and execute code within it."""

    def __init__(self, kernel_name: str = "python3") -> None:
        self.kernel_name = kernel_name
        self._manager = KernelManager(kernel_name=kernel_name)
        self._client: Optional[BlockingKernelClient] = None

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._client is not None:
            return
        try:
            self._manager.start_kernel()
        except NoSuchKernel:
            fallback_cmd = self._default_kernel_cmd()
            try:
                self._manager.start_kernel(kernel_cmd=fallback_cmd)
            except Exception as exc:  # pragma: no cover - depends on env setup
                raise RuntimeError(
                    "Python 커널을 시작할 수 없습니다. ipykernel 패키지가 설치되어 있고 `python -m ipykernel install --user`가 실행되었는지 확인하세요."
                ) from exc
        client = self._manager.blocking_client()
        client.start_channels()
        self._client = client

    def restart(self) -> None:
        self.shutdown()
        self.start()

    def shutdown(self) -> None:
        if self._client is None:
            return
        try:
            self._client.stop_channels()
        finally:
            self._manager.shutdown_kernel(now=True)
            self._client = None

    # ------------------------------------------------------------------
    def execute(self, code: str, timeout: float, artifact_dir: Path) -> ExecutionResult:
        self.start()
        assert self._client is not None

        artifact_dir.mkdir(parents=True, exist_ok=True)
        msg_id = self._client.execute(code)
        result = ExecutionResult()

        while True:
            msg = self._client.get_iopub_msg(timeout=timeout)
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue

            msg_type = msg["header"]["msg_type"]
            content = msg.get("content", {})

            if msg_type == "stream":
                text = content.get("text", "")
                if content.get("name") == "stdout":
                    result.stdout += text
                else:
                    result.stderr += text
            elif msg_type in {"display_data", "execute_result"}:
                data = content.get("data", {})
                text_output = data.get("text/plain")
                if text_output:
                    result.result_text = text_output
                image_png = data.get("image/png")
                if image_png:
                    image_path = self._write_image(artifact_dir, image_png)
                    result.images.append(image_path)
            elif msg_type == "error":
                result.error = ExecutionError(
                    ename=content.get("ename", "Error"),
                    evalue=content.get("evalue", ""),
                    traceback=content.get("traceback", []),
                )
            elif msg_type == "status" and content.get("execution_state") == "idle":
                break

        # Drain the shell channel to keep the client in sync.
        try:
            self._client.get_shell_msg(timeout=timeout)
        except Exception:  # pragma: no cover - best effort cleanup
            pass

        return result

    # ------------------------------------------------------------------
    def _write_image(self, artifact_dir: Path, payload: str) -> Path:
        image_bytes = base64.b64decode(payload)
        image_path = artifact_dir / f"image-{uuid.uuid4().hex[:8]}.png"
        with image_path.open("wb") as fh:
            fh.write(image_bytes)
        return image_path

    def _default_kernel_cmd(self) -> List[str]:
        return [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]


__all__ = ["KernelRunner", "ExecutionResult", "ExecutionError"]
