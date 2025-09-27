from pathlib import Path

from jupythunder2.agent.orchestrator import AgentResponse, CodeCell
from jupythunder2.runtime.kernel import ExecutionError, ExecutionResult
from jupythunder2.store.codebook import CodebookLogger, discover_codebooks


def test_codebook_logger_writes_notebook_and_markdown(tmp_path: Path) -> None:
    logger = CodebookLogger.create(tmp_path, "데모 세션")

    logger.log_user("사용자 질문")
    response = AgentResponse(message="응답", plan_items=["단계"], code_cells=[], raw_text=None)
    logger.log_agent_response(response)

    cell = CodeCell(code="print('hello')", description="테스트" )
    logger.register_code_cell("cell-1", cell.code, description=cell.description)

    result = ExecutionResult(stdout="hello\n")
    logger.record_execution("cell-1", result)

    assert logger.notebook_path.exists()
    assert logger.markdown_path.exists()

    notebook_text = logger.notebook_path.read_text(encoding="utf-8")
    assert "print('hello')" in notebook_text

    md_text = logger.markdown_path.read_text(encoding="utf-8")
    assert md_text.splitlines()[0] == "데모 세션"
    assert "사용자 질문" in md_text
    assert "테스트" in md_text

    entries = discover_codebooks(tmp_path)
    assert entries and entries[0].stem == logger.stem


def test_codebook_logger_logs_rich_outputs(tmp_path: Path) -> None:
    logger = CodebookLogger.create(tmp_path, "풍부한 출력")
    logger.register_code_cell("cell-1", "print('x')")

    image_path = tmp_path / "image.png"
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x04\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    error = ExecutionError("TimeoutError", "timed out", ["line1", "line2", "line3"])
    result = ExecutionResult(images=[image_path], error=error)
    logger.record_execution("cell-1", result)

    logger.log_system_message("알림", "세부 내용")

    md_text = logger.markdown_path.read_text(encoding="utf-8")
    assert "이미지 1" in md_text
    assert "line1" in md_text
    assert "알림" in md_text
