import json
from pathlib import Path

from jupythunder2.store.session import SessionStore


def test_session_store_creates_directory(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "runs")

    session_dir = store.start_session()
    assert session_dir.exists()
    assert (session_dir / "events.jsonl").exists()

    store.append_event("user", {"message": "hello"})

    events = (session_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(events) == 1

    store.finish_session()
    metadata_path = session_dir / "session.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["event_count"] == 1
