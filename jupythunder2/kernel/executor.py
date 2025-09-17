"""Jupyter 커널과의 상호작용을 단순화한 실행기."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from jupyter_client import KernelManager


class KernelExecutionError(RuntimeError):
    """커널 실행 중 치명적인 오류가 발생했을 때 사용."""


@dataclass(slots=True)
class KernelError:
    """커널에서 발생한 예외 정보."""

    name: str
    value: str
    traceback: List[str]

    def format_traceback(self) -> str:
        return "\n".join(self.traceback)


@dataclass(slots=True)
class ExecutionDisplay:
    """display_data 메시지를 캡처."""

    data: Dict[str, object]
    metadata: Dict[str, object]

    def text(self) -> Optional[str]:
        text_data = self.data.get("text/plain")
        if isinstance(text_data, str):
            return text_data
        return None


@dataclass(slots=True)
class ExecutionResult:
    """단일 코드 셀 실행 결과."""

    stdout: str = ""
    stderr: str = ""
    result: Optional[str] = None
    execution_count: Optional[int] = None
    displays: List[ExecutionDisplay] = field(default_factory=list)
    error: Optional[KernelError] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class KernelSession:
    """Jupyter 커널 세션을 관리하고 코드를 실행한다."""

    def __init__(
        self,
        kernel_name: str = "python3",
    ) -> None:
        self._manager = KernelManager(kernel_name=kernel_name)
        self._client = None
        self._is_running = False

    def __enter__(self) -> "KernelSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown()

    def start(self) -> None:
        if self._is_running:
            return
        try:
            self._manager.start_kernel()
        except Exception as exc:  # pragma: no cover - 외부 I/O
            raise KernelExecutionError("커널을 시작하지 못했습니다.") from exc
        client = self._manager.blocking_client()
        client.start_channels()
        self._client = client
        self._is_running = True

    def shutdown(self) -> None:
        if not self._is_running:
            return
        assert self._client is not None
        try:
            self._client.stop_channels()
        finally:
            self._manager.shutdown_kernel(now=True)
        self._is_running = False
        self._client = None

    def execute(self, code: str, timeout: float = 30.0) -> ExecutionResult:
        if not self._is_running:
            self.start()
        assert self._client is not None

        msg_id = self._client.execute(code, allow_stdin=False)
        result = ExecutionResult()

        # Shell 응답을 먼저 기다려 상태를 확인한다.
        shell_reply = self._get_shell_reply(msg_id, timeout)
        result.execution_count = shell_reply.get("execution_count")
        status = shell_reply.get("status")

        # IOPub 메시지 스트림을 처리한다.
        self._consume_iopub(msg_id, timeout, result)

        if status == "error":
            result.error = KernelError(
                name=shell_reply.get("ename", "Error"),
                value=shell_reply.get("evalue", ""),
                traceback=list(shell_reply.get("traceback", [])),
            )
        return result

    def _get_shell_reply(self, msg_id: str, timeout: float) -> dict:
        assert self._client is not None
        while True:
            try:
                reply = self._client.get_shell_msg(timeout=timeout)
            except Exception as exc:  # pragma: no cover - 외부 I/O
                raise KernelExecutionError("커널 응답을 받는 데 실패했습니다.") from exc

            if reply.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            return reply.get("content", {})

    def _consume_iopub(self, msg_id: str, timeout: float, result: ExecutionResult) -> None:
        assert self._client is not None
        while True:
            try:
                msg = self._client.get_iopub_msg(timeout=timeout)
            except Exception as exc:  # pragma: no cover - 외부 I/O
                raise KernelExecutionError("커널 출력 수신 중 오류가 발생했습니다.") from exc

            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                # 다른 실행의 출력은 무시한다.
                continue

            msg_type = msg.get("msg_type")
            content = msg.get("content", {})

            if msg_type == "status" and content.get("execution_state") == "idle":
                break
            if msg_type == "stream":
                stream_name = content.get("name")
                text = content.get("text", "")
                if stream_name == "stdout":
                    result.stdout += text
                elif stream_name == "stderr":
                    result.stderr += text
            elif msg_type == "execute_result":
                data = content.get("data", {})
                text_output = self._extract_text(data)
                if text_output:
                    result.result = text_output
            elif msg_type == "display_data":
                display = ExecutionDisplay(
                    data=dict(content.get("data", {})),
                    metadata=dict(content.get("metadata", {})),
                )
                result.displays.append(display)
            elif msg_type == "error":
                result.error = KernelError(
                    name=content.get("ename", "Error"),
                    value=content.get("evalue", ""),
                    traceback=list(content.get("traceback", [])),
                )

    @staticmethod
    def _extract_text(data: Dict[str, object]) -> Optional[str]:
        text_plain = data.get("text/plain")
        if isinstance(text_plain, str):
            return text_plain
        return None
