from __future__ import annotations

from pathlib import Path

import pytest

from skobal.errors import StateError
from skobal.state import InstallRecord, StateStore


def _record(skill: str) -> InstallRecord:
    return InstallRecord(
        skill=skill,
        target="claude",
        source=f"/source/{skill}",
        destination=f"/destination/{skill}",
        mode="symlink",
        version="1.0.0",
    )


def test_state_output_is_sorted_deterministic_and_has_no_temp_files(
    tmp_path: Path,
) -> None:
    first = StateStore(tmp_path / "first")
    first.replace(_record("zeta"))
    first.replace(_record("alpha"))
    second = StateStore(tmp_path / "second")
    second.replace(_record("alpha"))
    second.replace(_record("zeta"))

    assert first.path.read_bytes() == second.path.read_bytes()
    assert first.path.read_text(encoding="utf-8").index("skill: alpha") < (
        first.path.read_text(encoding="utf-8").index("skill: zeta")
    )
    assert not list(first.directory.glob(".installs-*.tmp"))
    assert not list(second.directory.glob(".installs-*.tmp"))


def test_failed_atomic_state_replace_preserves_previous_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = StateStore(tmp_path / "state")
    store.replace(_record("alpha"))
    before = store.path.read_bytes()

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr("skobal.state.os.replace", fail_replace)
    with pytest.raises(StateError, match="atomically write"):
        store.replace(_record("zeta"))

    assert store.path.read_bytes() == before
    assert store.records == [_record("alpha")]
    assert not list(store.directory.glob(".installs-*.tmp"))
