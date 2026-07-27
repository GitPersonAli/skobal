from __future__ import annotations

from pathlib import Path

import pytest

from skobal.errors import GitError, SkobalError
from skobal.schema import Repository
from skobal.state import StateStore
from skobal.update import run_update


class MockGit:
    def __init__(self, *, dirty: bool = False, pull_failure: bool = False) -> None:
        self.dirty = dirty
        self.pull_failure = pull_failure
        self.calls: list[str] = []

    def ensure_repository(self) -> None:
        self.calls.append("repository")

    def ensure_clean(self) -> None:
        self.calls.append("clean")
        if self.dirty:
            raise GitError("working tree is dirty")

    def pull_ff_only(self) -> None:
        self.calls.append("pull")
        if self.pull_failure:
            raise GitError("git pull --ff-only failed")


def _set_adapter_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SKOBAL_CLAUDE_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("SKOBAL_CURSOR_DIR", str(tmp_path / "cursor"))
    monkeypatch.setenv("SKOBAL_OPENCODE_DIR", str(tmp_path / "opencode"))


def test_update_rejects_dirty_tree_before_pull(
    repo_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_adapter_overrides(monkeypatch, tmp_path)
    git = MockGit(dirty=True)
    with pytest.raises(GitError, match="dirty"):
        run_update(
            Repository(repo_copy),
            "personal",
            dry_run=False,
            git=git,  # type: ignore[arg-type]
            store=StateStore(tmp_path / "state"),
        )
    assert git.calls == ["repository", "clean"]


def test_failed_fast_forward_pull_stops_pipeline(
    repo_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_adapter_overrides(monkeypatch, tmp_path)
    git = MockGit(pull_failure=True)
    registry_before = (repo_copy / "registry.yaml").read_bytes()
    with pytest.raises(GitError, match="ff-only"):
        run_update(
            Repository(repo_copy),
            "personal",
            dry_run=False,
            git=git,  # type: ignore[arg-type]
            store=StateStore(tmp_path / "state"),
        )
    assert git.calls == ["repository", "clean", "pull"]
    assert (repo_copy / "registry.yaml").read_bytes() == registry_before
    assert not (tmp_path / "claude").exists()


def test_validation_failure_after_pull_prevents_registry_and_sync(
    repo_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_adapter_overrides(monkeypatch, tmp_path)
    metadata = repo_copy / "skills" / "documentation" / "skill.yaml"
    metadata.write_text(
        metadata.read_text(encoding="utf-8").replace(
            "version: 0.1.0", "version: invalid"
        ),
        encoding="utf-8",
    )
    registry_before = (repo_copy / "registry.yaml").read_bytes()
    git = MockGit()
    with pytest.raises(SkobalError, match="validation failed"):
        run_update(
            Repository(repo_copy),
            "personal",
            dry_run=False,
            git=git,  # type: ignore[arg-type]
            store=StateStore(tmp_path / "state"),
        )
    assert git.calls == ["repository", "clean", "pull"]
    assert (repo_copy / "registry.yaml").read_bytes() == registry_before
    assert not (tmp_path / "claude").exists()


def test_update_dry_run_makes_no_changes_and_does_not_pull(
    repo_copy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_adapter_overrides(monkeypatch, tmp_path)
    registry_before = (repo_copy / "registry.yaml").read_bytes()
    git = MockGit()
    lines = run_update(
        Repository(repo_copy),
        "personal",
        dry_run=True,
        git=git,  # type: ignore[arg-type]
        store=StateStore(tmp_path / "state"),
    )
    assert git.calls == ["repository", "clean"]
    assert lines[0] == "git: would pull --ff-only"
    assert any("would install" in line for line in lines)
    assert (repo_copy / "registry.yaml").read_bytes() == registry_before
    assert not (tmp_path / "claude").exists()
    assert not (tmp_path / "state").exists()
