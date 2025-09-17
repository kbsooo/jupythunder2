"""jupythunder2 CLI agent package."""

from importlib import metadata

try:
    __version__ = metadata.version("dl-h1")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__"]
