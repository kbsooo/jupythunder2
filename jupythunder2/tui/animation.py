"""Lightweight notification helper for long running operations."""
from __future__ import annotations

from typing import Optional

from rich.console import Console


class AsciiAnimator:
    """Prints a single-line status message during long operations."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._active = False
        self._message: Optional[str] = None

    def start(self, message: str) -> None:
        if self._active:
            return
        self._active = True
        self._message = message
        self.console.print(message, highlight=False, markup=False)

    def stop(self) -> None:
        self._active = False
        self._message = None


__all__ = ["AsciiAnimator"]
