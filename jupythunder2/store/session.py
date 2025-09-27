"""Session logging utilities."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class SessionStore:
    """Persist session artefacts and structured logs."""

    def __init__(self, run_root: Path) -> None:
        self.run_root = run_root
        self.run_root.mkdir(parents=True, exist_ok=True)
        self._session_dir: Optional[Path] = None
        self._events_file: Optional[Path] = None
        self._start_time: Optional[datetime] = None
        self._event_count: int = 0

    def start_session(self) -> Path:
        if self._session_dir is not None:
            return self._session_dir

        started_at = datetime.now()
        timestamp = started_at.strftime("%Y%m%d-%H%M%S")
        session_dir = self.run_root / timestamp
        suffix = 1
        while session_dir.exists():
            suffix += 1
            session_dir = self.run_root / f"{timestamp}-{suffix}"
        session_dir.mkdir(parents=True, exist_ok=False)

        events_file = session_dir / "events.jsonl"
        events_file.touch()

        self._session_dir = session_dir
        self._events_file = events_file
        self._start_time = started_at
        self._event_count = 0
        return session_dir

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self._events_file is None:
            return
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "type": event_type,
            "payload": payload,
        }
        with self._events_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._event_count += 1

    def finish_session(self) -> None:
        if self._session_dir is not None:
            metadata = {
                "status": "completed",
                "started_at": self._start_time.isoformat(timespec="seconds") if self._start_time else None,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "event_count": self._event_count,
            }
            metadata_path = self._session_dir / "session.json"
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._session_dir = None
        self._events_file = None
        self._start_time = None
        self._event_count = 0

    def __enter__(self) -> "SessionStore":
        self.start_session()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.finish_session()


__all__ = ["SessionStore"]
