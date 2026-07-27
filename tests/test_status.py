from __future__ import annotations

import json
from pathlib import Path

import yaml
from conftest import run_skillctl


def test_status_after_sync_is_synced_and_json_is_deterministic(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    synced = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy"],
        env=adapter_env,
    )
    assert synced.returncode == 0, synced.stderr

    human = run_skillctl(
        repo_copy, ["status", "--profile", "personal"], env=adapter_env
    )
    first_json = run_skillctl(
        repo_copy,
        ["status", "--profile", "personal", "--json"],
        env=adapter_env,
    )
    second_json = run_skillctl(
        repo_copy,
        ["status", "--profile", "personal", "--json"],
        env=adapter_env,
    )
    assert human.returncode == first_json.returncode == second_json.returncode == 0
    assert "synced" in human.stdout
    assert first_json.stdout == second_json.stdout
    assert {item["status"] for item in json.loads(first_json.stdout)} == {"synced"}


def test_status_reports_modified_outdated_unmanaged_and_dangling(
    repo_copy: Path, adapter_env: dict[str, str], can_symlink: bool
) -> None:
    copied = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy"],
        env=adapter_env,
    )
    assert copied.returncode == 0, copied.stderr
    destination = Path(adapter_env["SKOBAL_CLAUDE_DIR"])
    (destination / "documentation" / "SKILL.md").write_text(
        "locally modified\n", encoding="utf-8"
    )
    metadata_path = repo_copy / "skills" / "hello-world" / "skill.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    metadata["version"] = "0.2.0"
    metadata_path.write_text(
        yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8"
    )

    result = run_skillctl(
        repo_copy,
        ["status", "--profile", "personal", "--json"],
        env=adapter_env,
    )
    statuses = {
        item["skill"]: item["status"] for item in json.loads(result.stdout)
    }
    assert result.returncode == 1
    assert statuses == {
        "documentation": "modified",
        "hello-world": "outdated",
    }

    # Missing state makes an existing destination unmanaged, never managed.
    Path(adapter_env["SKOBAL_STATE_DIR"], "installs.yaml").unlink()
    unmanaged = run_skillctl(
        repo_copy,
        ["status", "--profile", "personal", "--json"],
        env=adapter_env,
    )
    unmanaged_statuses = {
        item["skill"]: item["status"] for item in json.loads(unmanaged.stdout)
    }
    assert set(unmanaged_statuses.values()) == {"unmanaged-conflict"}

    if not can_symlink:
        return
    hello = destination / "hello-world"
    if hello.is_dir() and not hello.is_symlink():
        import shutil

        shutil.rmtree(hello)
    hello.symlink_to(destination / "missing", target_is_directory=True)
    dangling = run_skillctl(
        repo_copy,
        ["status", "--profile", "personal", "--json"],
        env=adapter_env,
    )
    dangling_statuses = {
        item["skill"]: item["status"] for item in json.loads(dangling.stdout)
    }
    assert dangling_statuses["hello-world"] == "dangling-symlink"


def test_status_reports_unsupported_target(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    metadata_path = repo_copy / "skills" / "documentation" / "skill.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    metadata["targets"] = ["cursor"]
    metadata_path.write_text(
        yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8"
    )
    profile_path = repo_copy / "profiles" / "personal.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["skills"] = ["documentation"]
    profile_path.write_text(
        yaml.safe_dump(profile, sort_keys=False), encoding="utf-8"
    )

    result = run_skillctl(
        repo_copy,
        ["status", "--profile", "personal", "--json"],
        env=adapter_env,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)[0]["status"] == "unsupported"
