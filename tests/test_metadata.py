from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from conftest import run_skillctl


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("version", "01.2.3", "semantic version"),
        ("schema_version", 2, "unsupported schema_version"),
        ("targets", ["claude", "made-up"], "unsupported targets"),
    ],
)
def test_invalid_metadata_is_rejected_with_path(
    repo_copy: Path,
    key: str,
    value: object,
    message: str,
) -> None:
    metadata_path = repo_copy / "skills" / "documentation" / "skill.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    metadata[key] = value
    metadata_path.write_text(
        yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8"
    )

    result = run_skillctl(repo_copy, ["validate", "documentation"])
    assert result.returncode == 1
    assert message in result.stderr
    assert "skills/documentation/skill.yaml" in result.stderr


def test_directory_name_mismatch_is_rejected_with_path(repo_copy: Path) -> None:
    metadata_path = repo_copy / "skills" / "documentation" / "skill.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    metadata["name"] = "wrong-name"
    metadata_path.write_text(
        yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8"
    )

    result = run_skillctl(repo_copy, ["validate", "documentation"])
    assert result.returncode == 1
    assert "name must match directory" in result.stderr
    assert "skills/documentation/skill.yaml" in result.stderr


def test_duplicate_skill_metadata_names_are_rejected(repo_copy: Path) -> None:
    duplicate = repo_copy / "skills" / "duplicate"
    shutil.copytree(repo_copy / "skills" / "documentation", duplicate)
    skill_md = duplicate / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8").replace(
            "name: documentation", "name: duplicate"
        ),
        encoding="utf-8",
    )
    # Deliberately retain the original metadata name to create a duplicate.
    result = run_skillctl(repo_copy, ["registry"])

    assert result.returncode == 1
    assert "duplicate skill name 'documentation'" in result.stderr
    assert "skills/documentation/skill.yaml" in result.stderr
    assert "skills/duplicate/skill.yaml" in result.stderr
