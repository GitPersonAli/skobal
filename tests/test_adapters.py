from __future__ import annotations

from pathlib import Path

import pytest

from adapters.claude import ClaudeAdapter
from adapters.cursor import CursorAdapter
from adapters.opencode import OpenCodeAdapter


ADAPTER_CASES = [
    (ClaudeAdapter, "SKOBAL_CLAUDE_DIR"),
    (CursorAdapter, "SKOBAL_CURSOR_DIR"),
    (OpenCodeAdapter, "SKOBAL_OPENCODE_DIR"),
]


@pytest.mark.parametrize(("adapter_class", "env_var"), ADAPTER_CASES)
def test_adapter_symlink_copy_and_uninstall(
    adapter_class: type[ClaudeAdapter],
    env_var: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / adapter_class.name
    monkeypatch.setenv(env_var, str(destination))
    skill = tmp_path / "source" / "sample"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("content\n", encoding="utf-8")
    adapter = adapter_class()

    assert adapter.default_dest() == destination
    assert adapter.install(skill, "sample") == "installed"
    assert (destination / "sample").is_symlink()
    assert adapter.install(skill, "sample") == "skipped"
    assert adapter.installed() == ["sample"]

    assert adapter.install(skill, "sample", copy=True) == "updated"
    assert (destination / "sample").is_dir()
    assert not (destination / "sample").is_symlink()
    assert adapter.install(skill, "sample", copy=True) == "skipped"

    (skill / "SKILL.md").write_text("changed\n", encoding="utf-8")
    assert adapter.install(skill, "sample", copy=True) == "updated"
    assert (destination / "sample" / "SKILL.md").read_text() == "changed\n"
    assert adapter.uninstall("sample") == "removed"
    assert not (destination / "sample").exists()
    assert adapter.installed() == []


@pytest.mark.parametrize(("adapter_class", "env_var"), ADAPTER_CASES)
def test_adapter_refuses_unmanaged_destination(
    adapter_class: type[ClaudeAdapter],
    env_var: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / adapter_class.name
    monkeypatch.setenv(env_var, str(destination))
    unmanaged = destination / "sample"
    unmanaged.mkdir(parents=True)
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(FileExistsError, match="unmanaged"):
        adapter_class().install(source, "sample")
    with pytest.raises(PermissionError, match="unmanaged"):
        adapter_class().uninstall("sample")
    assert unmanaged.is_dir()


def test_adapter_does_not_remove_modified_managed_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "claude"
    monkeypatch.setenv("SKOBAL_CLAUDE_DIR", str(destination))
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("original\n", encoding="utf-8")
    adapter = ClaudeAdapter()
    adapter.install(source, "sample", copy=True)

    installed_file = destination / "sample" / "SKILL.md"
    installed_file.write_text("user modification\n", encoding="utf-8")

    assert adapter.installed() == []
    with pytest.raises(PermissionError, match="unmanaged"):
        adapter.uninstall("sample")
    assert installed_file.read_text(encoding="utf-8") == "user modification\n"
