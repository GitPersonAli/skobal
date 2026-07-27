"""OpenCode adapter.

Installs skills under ``~/.config/opencode/skills``. Set
``SKOBAL_OPENCODE_DIR`` to override that destination.
"""

from pathlib import Path

from adapters import FilesystemAdapter


class OpenCodeAdapter(FilesystemAdapter):
    name = "opencode"
    env_var = "SKOBAL_OPENCODE_DIR"
    home_relative_dest = Path(".config/opencode/skills")


ADAPTER_CLASS = OpenCodeAdapter
