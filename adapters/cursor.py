"""Cursor adapter.

Cursor discovers agent skills under ``~/.cursor/skills``. Set
``SKOBAL_CURSOR_DIR`` to override that destination.
"""

from pathlib import Path

from adapters import FilesystemAdapter


class CursorAdapter(FilesystemAdapter):
    name = "cursor"
    env_var = "SKOBAL_CURSOR_DIR"
    home_relative_dest = Path(".cursor/skills")


ADAPTER_CLASS = CursorAdapter
