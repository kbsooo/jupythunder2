"""jupythunder2 package metadata."""

from importlib import metadata

try:
    __version__ = metadata.version("jupythunder2")
except metadata.PackageNotFoundError:  # pragma: no cover - during development
    __version__ = "0.0.0"

__all__ = ["__version__"]
