from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run_skillctl(
    repo: Path,
    arguments: Sequence[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    return subprocess.run(
        [str(repo / "skillctl"), *arguments],
        cwd=repo,
        env=command_env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    destination = tmp_path / "skobal"
    destination.mkdir()
    for name in ("adapters", "profiles", "skills", "tests"):
        shutil.copytree(REPO_ROOT / name, destination / name)
    for name in ("skillctl", "registry.yaml"):
        shutil.copy2(REPO_ROOT / name, destination / name)
    return destination


@pytest.fixture
def adapter_env(tmp_path: Path) -> dict[str, str]:
    return {
        "SKOBAL_CLAUDE_DIR": str(tmp_path / "claude"),
        "SKOBAL_CURSOR_DIR": str(tmp_path / "cursor"),
        "SKOBAL_OPENCODE_DIR": str(tmp_path / "opencode"),
    }
