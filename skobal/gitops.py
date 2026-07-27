"""Small injectable abstraction for safe git operations."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from skobal.errors import GitError


class CompletedProcessLike(Protocol):
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[..., CompletedProcessLike]


class GitRepository:
    """Only the non-destructive git operations used by ``update``."""

    def __init__(self, root: Path, runner: Runner | None = None) -> None:
        self.root = root
        self._runner = runner if runner is not None else subprocess.run

    def ensure_repository(self) -> None:
        result = self._run(["rev-parse", "--is-inside-work-tree"])
        if result.returncode != 0 or result.stdout.strip() != "true":
            detail = result.stderr.strip() or "not inside a git working tree"
            raise GitError(f"{self.root}: {detail}")

    def ensure_clean(self) -> None:
        result = self._run(["status", "--porcelain"])
        if result.returncode != 0:
            detail = result.stderr.strip() or "git status failed"
            raise GitError(f"cannot inspect working tree: {detail}")
        if result.stdout.strip():
            raise GitError(
                "working tree is dirty; commit or stash local changes before update"
            )

    def pull_ff_only(self) -> None:
        result = self._run(["pull", "--ff-only"])
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "git pull failed"
            raise GitError(f"git pull --ff-only failed: {detail}")

    def _run(self, arguments: Sequence[str]) -> CompletedProcessLike:
        try:
            return self._runner(
                ["git", *arguments],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise GitError(f"cannot run git: {exc}") from exc

