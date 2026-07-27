"""Claude Code adapter.

Installs skills under ``~/.claude/skills`` unless ``SKOBAL_CLAUDE_DIR`` is set.
"""

from pathlib import Path

from adapters import FilesystemAdapter


class ClaudeAdapter(FilesystemAdapter):
    name = "claude"
    env_var = "SKOBAL_CLAUDE_DIR"
    home_relative_dest = Path(".claude/skills")


ADAPTER_CLASS = ClaudeAdapter
