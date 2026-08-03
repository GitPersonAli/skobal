from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

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
        [sys.executable, str(repo / "skillctl"), *arguments],
        cwd=repo,
        env=command_env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """Fixture repository: real code, but the skill catalog and profiles come
    from tests/fixtures so tests never depend on the live catalog."""
    destination = tmp_path / "skobal"
    destination.mkdir()
    fixtures = REPO_ROOT / "tests" / "fixtures"
    for name in ("adapters", "skobal", "tests"):
        shutil.copytree(REPO_ROOT / name, destination / name)
    shutil.copytree(fixtures / "skills", destination / "skills")
    shutil.copytree(
        REPO_ROOT / "skills" / "_template", destination / "skills" / "_template"
    )
    shutil.copytree(fixtures / "profiles", destination / "profiles")
    for name in ("pyproject.toml", "skillctl"):
        shutil.copy2(REPO_ROOT / name, destination / name)
    generated = run_skillctl(destination, ["registry"])
    assert generated.returncode == 0, generated.stderr
    return destination


@pytest.fixture(autouse=True)
def isolated_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    state = tmp_path / "state"
    monkeypatch.setenv("SKOBAL_STATE_DIR", str(state))
    return state


@pytest.fixture
def adapter_env(tmp_path: Path) -> dict[str, str]:
    return {
        "SKOBAL_CLAUDE_DIR": str(tmp_path / "claude"),
        "SKOBAL_CURSOR_DIR": str(tmp_path / "cursor"),
        "SKOBAL_OPENCODE_DIR": str(tmp_path / "opencode"),
        "SKOBAL_STATE_DIR": str(tmp_path / "state"),
    }


@pytest.fixture(scope="session")
def can_symlink(tmp_path_factory: pytest.TempPathFactory) -> bool:
    root = tmp_path_factory.mktemp("symlink-probe")
    target = root / "target"
    link = root / "link"
    target.mkdir()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        return False
    return link.is_symlink() and link.exists()
