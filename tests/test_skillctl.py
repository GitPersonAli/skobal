from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import yaml

from conftest import REPO_ROOT, run_skillctl


def test_list_and_validate() -> None:
    listed = run_skillctl(REPO_ROOT, ["list"])
    validated = run_skillctl(REPO_ROOT, ["validate"])

    assert listed.returncode == 0
    assert "documentation" in listed.stdout
    assert "hello-world" in listed.stdout
    assert validated.returncode == 0
    assert "Validation passed" in validated.stdout


def test_new_substitutes_templates_and_validates(repo_copy: Path) -> None:
    created = run_skillctl(repo_copy, ["new", "release-notes"])

    assert created.returncode == 0
    skill = repo_copy / "skills" / "release-notes"
    assert skill.is_dir()
    assert "{{" not in (skill / "SKILL.md").read_text(encoding="utf-8")
    assert date.today().isoformat() in (skill / "SKILL.md").read_text(encoding="utf-8")
    assert os.access(skill / "scripts" / "example.py", os.X_OK)

    regenerated = run_skillctl(repo_copy, ["registry"])
    validated = run_skillctl(repo_copy, ["validate", "release-notes"])
    assert regenerated.returncode == 0
    assert validated.returncode == 0, validated.stderr


def test_registry_is_deterministic(repo_copy: Path) -> None:
    first = run_skillctl(repo_copy, ["registry"])
    first_content = (repo_copy / "registry.yaml").read_text(encoding="utf-8")
    second = run_skillctl(repo_copy, ["registry"])

    assert first.returncode == second.returncode == 0
    assert (repo_copy / "registry.yaml").read_text(encoding="utf-8") == first_content
    registry = yaml.safe_load(first_content)
    names = [skill["name"] for skill in registry["skills"]]
    assert names == sorted(names)


def test_validate_reports_frontmatter_and_registry_errors(repo_copy: Path) -> None:
    skill_path = repo_copy / "skills" / "hello-world" / "SKILL.md"
    skill_path.write_text(
        skill_path.read_text(encoding="utf-8")
        .replace("name: hello-world", "name: Wrong_Name")
        .replace(
            "description: Greet a person",
            "description: Use an invalid modified greeting to greet a person",
        ),
        encoding="utf-8",
    )

    result = run_skillctl(repo_copy, ["validate", "hello-world"])

    assert result.returncode == 1
    assert "name must use lowercase-hyphen format" in result.stderr
    assert "registry.yaml is inconsistent" in result.stderr


def test_sync_dry_run_and_symlink_install(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    dry_run = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--dry-run"],
        env=adapter_env,
    )
    destination = Path(adapter_env["SKOBAL_CLAUDE_DIR"])
    assert dry_run.returncode == 0
    assert "claude/documentation: would install (symlink)" in dry_run.stdout
    assert not destination.exists()

    installed = run_skillctl(
        repo_copy, ["sync", "--profile", "personal"], env=adapter_env
    )
    assert installed.returncode == 0, installed.stderr
    assert (destination / "documentation").is_symlink()
    assert (destination / "hello-world").is_symlink()

    repeated = run_skillctl(
        repo_copy, ["sync", "--profile", "personal"], env=adapter_env
    )
    assert repeated.returncode == 0
    assert "claude/documentation: skipped (symlink)" in repeated.stdout


def test_sync_copy_and_prune_preserves_unmanaged(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    destination = Path(adapter_env["SKOBAL_CLAUDE_DIR"])
    installed = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy"],
        env=adapter_env,
    )
    assert installed.returncode == 0
    assert not (destination / "hello-world").is_symlink()

    unmanaged = destination / "keep-me"
    unmanaged.mkdir()
    profile_path = repo_copy / "profiles" / "personal.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    profile["skills"] = ["documentation"]
    profile_path.write_text(
        yaml.safe_dump(profile, sort_keys=False), encoding="utf-8"
    )

    pruned = run_skillctl(
        repo_copy,
        ["sync", "--profile", "personal", "--copy", "--prune"],
        env=adapter_env,
    )
    assert pruned.returncode == 0, pruned.stderr
    assert "claude/hello-world: removed (prune)" in pruned.stdout
    assert not (destination / "hello-world").exists()
    assert unmanaged.is_dir()


def test_doctor_uses_overrides_and_finds_dangling_symlink(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    clean = run_skillctl(repo_copy, ["doctor"], env=adapter_env)
    assert clean.returncode == 0, clean.stdout + clean.stderr

    claude_destination = Path(adapter_env["SKOBAL_CLAUDE_DIR"])
    claude_destination.mkdir()
    (claude_destination / "dangling").symlink_to(claude_destination / "missing")
    unhealthy = run_skillctl(repo_copy, ["doctor"], env=adapter_env)

    assert unhealthy.returncode == 1
    assert "dangling symlink: dangling" in unhealthy.stdout


def test_skillctl_test_runs_hello_world_suite(
    repo_copy: Path, adapter_env: dict[str, str]
) -> None:
    result = run_skillctl(
        repo_copy, ["test", "hello-world"], env=adapter_env
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout
