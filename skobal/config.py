"""Repository and local state paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def repository_root() -> Path:
    """Return the checkout containing this package."""
    return Path(__file__).resolve().parents[1]


def state_directory() -> Path:
    """Return the user-overridable Skobal data directory."""
    override = os.environ.get("SKOBAL_STATE_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "skobal"
        return Path.home() / "AppData" / "Local" / "skobal"
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "skobal"
    return Path.home() / ".local" / "share" / "skobal"

