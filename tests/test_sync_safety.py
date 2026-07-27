from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from conftest import run_skillctl

from adapters.claude import ClaudeAdapter
from skobal.errors import StateError, SyncError
from skobal.state import StateStore
from skobal.sync import install_one


def test_unmanaged_collision_fails_and_force_backs_up(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    destination = Path(adapter_env["SKOBAL_CLAUDE_DIR"])
    collision = destination / "documentation"
    collision.mkdir(parents=True)
    original = collision / "mine.txt"
    original.write_text("keep this\n", encoding="utf-8")

    refused = run_skillctl(
        repo_copy, ["sync", "--profile", "personal"], env=adapter_env
    )
    assert refused.returncode == 1
    assert "unmanaged destination" in refused.stderr
    assert original.read_text(encoding="utf-8") == "keep this\n"

    forced = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--force", "--copy"],
        env=adapter_env,
    )
    assert forced.returncode == 0, forced.stderr
    assert "backup:" in forced.stdout
    backups = list(
        (destination / ".skobal-backups").glob(
            "*/claude/documentation/mine.txt"
        )
    )
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "keep this\n"
    assert (destination / "documentation").is_dir()


def test_managed_copy_updates_without_partial_destination(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    first = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy"],
        env=adapter_env,
    )
    assert first.returncode == 0, first.stderr
    destination = (
        Path(adapter_env["SKOBAL_CLAUDE_DIR"])
        / "documentation"
        / "SKILL.md"
    )
    source = repo_copy / "skills" / "documentation" / "SKILL.md"
    source.write_text(
        source.read_text(encoding="utf-8") + "\nSafe update.\n",
        encoding="utf-8",
    )

    updated = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy"],
        env=adapter_env,
    )
    assert updated.returncode == 0, updated.stderr
    assert "claude/documentation: updated (copy)" in updated.stdout
    assert destination.read_text(encoding="utf-8").endswith("Safe update.\n")


def test_dangling_symlink_is_reported_and_never_overwritten(
    repo_copy: Path, adapter_env: dict[str, str], can_symlink: bool
) -> None:
    if not can_symlink:
        pytest.skip("symlink creation is not available; copy mode is covered")
    destination = Path(adapter_env["SKOBAL_CLAUDE_DIR"])
    destination.mkdir(parents=True)
    dangling = destination / "documentation"
    dangling.symlink_to(destination / "missing", target_is_directory=True)

    result = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--force"],
        env=adapter_env,
    )
    assert result.returncode == 1
    assert "dangling symlink" in result.stderr
    assert dangling.is_symlink()
    assert not dangling.exists()


def test_corrupt_or_missing_state_never_prunes_unmanaged(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    destination = Path(adapter_env["SKOBAL_CLAUDE_DIR"])
    unmanaged = destination / "keep-me"
    unmanaged.mkdir(parents=True)
    profile_path = repo_copy / "profiles" / "personal.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["skills"] = ["documentation"]
    profile_path.write_text(
        yaml.safe_dump(profile, sort_keys=False), encoding="utf-8"
    )

    missing = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--prune", "--dry-run"],
        env=adapter_env,
    )
    assert missing.returncode == 0, missing.stderr
    assert unmanaged.is_dir()

    state_path = Path(adapter_env["SKOBAL_STATE_DIR"]) / "installs.yaml"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("not: [valid\n", encoding="utf-8")
    corrupted = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--prune"],
        env=adapter_env,
    )
    assert corrupted.returncode == 1
    assert "corrupted managed state" in corrupted.stderr
    assert unmanaged.is_dir()


def test_repeated_prune_is_safe(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    installed = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy"],
        env=adapter_env,
    )
    assert installed.returncode == 0, installed.stderr
    profile_path = repo_copy / "profiles" / "personal.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["skills"] = ["documentation"]
    profile_path.write_text(
        yaml.safe_dump(profile, sort_keys=False), encoding="utf-8"
    )

    first = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy", "--prune"],
        env=adapter_env,
    )
    second = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy", "--prune"],
        env=adapter_env,
    )
    assert first.returncode == second.returncode == 0
    assert "hello-world: removed" in first.stdout
    assert "hello-world: removed" not in second.stdout


def test_failed_prepare_restores_previous_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination_root = tmp_path / "claude"
    state_root = tmp_path / "state"
    monkeypatch.setenv("SKOBAL_CLAUDE_DIR", str(destination_root))
    source = tmp_path / "source"
    source.mkdir()
    source_file = source / "content.txt"
    source_file.write_text("old\n", encoding="utf-8")
    adapter = ClaudeAdapter()
    store = StateStore(state_root)
    install_one(
        adapter,
        source,
        "sample",
        version="1.0.0",
        copy=True,
        force=False,
        store=store,
    )
    assert not list(destination_root.glob(".skobal-txn-*"))
    state_before = store.path.read_bytes()
    source_file.write_text("new\n", encoding="utf-8")

    def fail_after_partial(
        _source: Path, prepared: Path, *, copy: bool
    ) -> None:
        assert copy
        prepared.mkdir()
        (prepared / "partial.txt").write_text("partial\n", encoding="utf-8")
        raise OSError("injected adapter failure")

    monkeypatch.setattr(adapter, "prepare", fail_after_partial)
    with pytest.raises(SyncError, match="injected adapter failure"):
        install_one(
            adapter,
            source,
            "sample",
            version="1.0.0",
            copy=True,
            force=False,
            store=store,
        )

    installed = destination_root / "sample" / "content.txt"
    assert installed.read_text(encoding="utf-8") == "old\n"
    assert store.path.read_bytes() == state_before
    assert not list(destination_root.glob(".skobal-txn-*"))


def test_state_write_failure_rolls_back_new_destination_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination_root = tmp_path / "claude"
    monkeypatch.setenv("SKOBAL_CLAUDE_DIR", str(destination_root))
    source = tmp_path / "source"
    source.mkdir()
    source_file = source / "content.txt"
    source_file.write_text("old\n", encoding="utf-8")
    adapter = ClaudeAdapter()
    store = StateStore(tmp_path / "state")
    install_one(
        adapter,
        source,
        "sample",
        version="1.0.0",
        copy=True,
        force=False,
        store=store,
    )
    state_before = store.path.read_bytes()
    source_file.write_text("new\n", encoding="utf-8")

    def fail_state(_record: object) -> None:
        raise StateError("injected state failure")

    monkeypatch.setattr(store, "replace", fail_state)
    with pytest.raises(SyncError, match="previous install restored"):
        install_one(
            adapter,
            source,
            "sample",
            version="1.0.0",
            copy=True,
            force=False,
            store=store,
        )

    assert (
        destination_root / "sample" / "content.txt"
    ).read_text(encoding="utf-8") == "old\n"
    assert store.path.read_bytes() == state_before
    assert not list(destination_root.glob(".skobal-txn-*"))


def test_failed_first_copy_leaves_no_partial_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination_root = tmp_path / "claude"
    monkeypatch.setenv("SKOBAL_CLAUDE_DIR", str(destination_root))
    source = tmp_path / "source"
    source.mkdir()
    adapter = ClaudeAdapter()

    def fail_copy(_source: Path, prepared: Path, *, copy: bool) -> None:
        assert copy
        prepared.mkdir()
        (prepared / "partial.txt").write_text("partial\n", encoding="utf-8")
        raise OSError("copy interrupted")

    monkeypatch.setattr(adapter, "prepare", fail_copy)
    with pytest.raises(SyncError, match="copy interrupted"):
        install_one(
            adapter,
            source,
            "sample",
            version="1.0.0",
            copy=True,
            force=False,
            store=StateStore(tmp_path / "state"),
        )
    assert not (destination_root / "sample").exists()
    assert not list(destination_root.glob(".skobal-txn-*"))
