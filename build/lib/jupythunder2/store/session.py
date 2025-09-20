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

    def start_session(self) -> Path:
        if self._session_dir is not None:
            return self._session_dir

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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

    def finish_session(self) -> None:
        # Placeholder for future resource management
        self._session_dir = None
        self._events_file = None


__all__ = ["SessionStore"]
