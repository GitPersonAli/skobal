"""Skill/profile schema validation and deterministic registry generation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from adapters import ADAPTER_NAMES
from skobal.errors import SkobalError

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
SKILL_SCHEMA_VERSION = 1
_REQUIRED_SKILL_KEYS = {
    "schema_version",
    "name",
    "version",
    "description",
    "targets",
}
_OPTIONAL_SKILL_KEYS = {"tags", "requires"}


@dataclass(frozen=True)
class Skill:
    """Validated metadata needed by commands."""

    name: str
    version: str
    schema_version: int
    description: str
    targets: tuple[str, ...]
    tags: tuple[str, ...]
    requires: tuple[str, ...]
    path: Path


class Repository:
    """Repository-scoped schema operations."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.skills_dir = self.root / "skills"
        self.profiles_dir = self.root / "profiles"
        self.registry_path = self.root / "registry.yaml"

    def display_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def load_yaml(self, path: Path) -> Any:
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SkobalError(f"missing file: {self.display_path(path)}") from exc
        except OSError as exc:
            raise SkobalError(
                f"cannot read {self.display_path(path)}: {exc}"
            ) from exc
        except yaml.YAMLError as exc:
            raise SkobalError(
                f"invalid YAML in {self.display_path(path)}: {exc}"
            ) from exc

    def parse_frontmatter(self, path: Path) -> dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SkobalError(f"missing file: {self.display_path(path)}") from exc
        except OSError as exc:
            raise SkobalError(
                f"cannot read {self.display_path(path)}: {exc}"
            ) from exc
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise SkobalError(
                f"{self.display_path(path)}: missing YAML frontmatter"
            )
        try:
            closing = next(
                index
                for index, line in enumerate(lines[1:], start=1)
                if line.strip() == "---"
            )
        except StopIteration as exc:
            raise SkobalError(
                f"{self.display_path(path)}: unclosed YAML frontmatter"
            ) from exc
        try:
            metadata = yaml.safe_load("\n".join(lines[1:closing]))
        except yaml.YAMLError as exc:
            raise SkobalError(
                f"{self.display_path(path)}: invalid frontmatter: {exc}"
            ) from exc
        if not isinstance(metadata, dict):
            raise SkobalError(
                f"{self.display_path(path)}: frontmatter must be a mapping"
            )
        return metadata

    def skill_directories(self) -> list[Path]:
        if not self.skills_dir.is_dir():
            raise SkobalError(
                f"missing directory: {self.display_path(self.skills_dir)}"
            )
        return sorted(
            (
                path
                for path in self.skills_dir.iterdir()
                if path.is_dir() and not path.name.startswith((".", "_"))
            ),
            key=lambda path: path.name,
        )

    def skill_directory(self, name: str) -> Path:
        if not valid_skill_name(name):
            raise SkobalError(
                "skill name must use lowercase-hyphen format and be under "
                "64 characters"
            )
        path = self.skills_dir / name
        if not path.is_dir():
            raise SkobalError(f"unknown skill: {name}")
        return path

    def validate_skill(self, path: Path) -> list[str]:
        errors: list[str] = []
        skill_md = path / "SKILL.md"
        metadata_path = path / "skill.yaml"
        try:
            frontmatter = self.parse_frontmatter(skill_md)
        except SkobalError as exc:
            errors.append(str(exc))
            frontmatter = {}

        extra_frontmatter = set(frontmatter) - {"name", "description"}
        if extra_frontmatter:
            errors.append(
                f"{self.display_path(skill_md)}: frontmatter supports only "
                "name and description"
            )
        frontmatter_name = frontmatter.get("name")
        frontmatter_description = frontmatter.get("description")
        if not valid_skill_name(frontmatter_name):
            errors.append(
                f"{self.display_path(skill_md)}: name must use lowercase-hyphen "
                "format and be under 64 characters"
            )
        elif frontmatter_name != path.name:
            errors.append(
                f"{self.display_path(skill_md)}: name {frontmatter_name!r} "
                "does not match directory"
            )
        if (
            not isinstance(frontmatter_description, str)
            or not frontmatter_description.strip()
        ):
            errors.append(f"{self.display_path(skill_md)}: description is required")
        elif len(frontmatter_description) >= 1024:
            errors.append(
                f"{self.display_path(skill_md)}: description must be under "
                "1024 characters"
            )
        elif "\n" in frontmatter_description:
            errors.append(
                f"{self.display_path(skill_md)}: description must be one line"
            )

        try:
            metadata = self.load_yaml(metadata_path)
        except SkobalError as exc:
            errors.append(str(exc))
            return errors
        if not isinstance(metadata, dict):
            errors.append(
                f"{self.display_path(metadata_path)}: expected a mapping"
            )
            return errors

        missing = _REQUIRED_SKILL_KEYS - set(metadata)
        extra = set(metadata) - _REQUIRED_SKILL_KEYS - _OPTIONAL_SKILL_KEYS
        if missing:
            errors.append(
                f"{self.display_path(metadata_path)}: missing keys: "
                f"{', '.join(sorted(missing))}"
            )
        if extra:
            errors.append(
                f"{self.display_path(metadata_path)}: unknown keys: "
                f"{', '.join(sorted(extra))}"
            )
        schema_version = metadata.get("schema_version")
        if schema_version != SKILL_SCHEMA_VERSION:
            errors.append(
                f"{self.display_path(metadata_path)}: unsupported schema_version "
                f"{schema_version!r}; expected {SKILL_SCHEMA_VERSION}"
            )
        if metadata.get("name") != path.name:
            errors.append(
                f"{self.display_path(metadata_path)}: name must match directory "
                f"{path.name!r}"
            )
        version = metadata.get("version")
        if not isinstance(version, str) or SEMVER_RE.fullmatch(version) is None:
            errors.append(
                f"{self.display_path(metadata_path)}: version must be valid "
                "semantic version X.Y.Z"
            )
        description = metadata.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append(
                f"{self.display_path(metadata_path)}: description must be a "
                "non-empty string"
            )
        errors.extend(
            _validate_string_list(
                metadata, "targets", self.display_path(metadata_path), non_empty=True
            )
        )
        for key in _OPTIONAL_SKILL_KEYS:
            if key in metadata:
                errors.extend(
                    _validate_string_list(
                        metadata, key, self.display_path(metadata_path)
                    )
                )
        targets = metadata.get("targets")
        if isinstance(targets, list):
            unsupported = sorted(
                target
                for target in targets
                if isinstance(target, str) and target not in ADAPTER_NAMES
            )
            if unsupported:
                errors.append(
                    f"{self.display_path(metadata_path)}: unsupported targets: "
                    f"{', '.join(unsupported)}"
                )
        return errors

    def validate_skills(
        self, paths: Iterable[Path] | None = None
    ) -> list[str]:
        selected = list(paths) if paths is not None else self.skill_directories()
        errors = [
            error
            for path in selected
            for error in self.validate_skill(path)
        ]
        names: dict[str, list[Path]] = {}
        for path in selected:
            metadata_path = path / "skill.yaml"
            try:
                metadata = self.load_yaml(metadata_path)
            except SkobalError:
                continue
            if isinstance(metadata, dict) and isinstance(metadata.get("name"), str):
                names.setdefault(metadata["name"], []).append(metadata_path)
        for name, metadata_paths in sorted(names.items()):
            if len(metadata_paths) > 1:
                joined = ", ".join(self.display_path(path) for path in metadata_paths)
                errors.append(f"duplicate skill name {name!r}: {joined}")
        return errors

    def skill(self, path: Path) -> Skill:
        errors = self.validate_skill(path)
        if errors:
            raise SkobalError("; ".join(errors))
        metadata = self.load_yaml(path / "skill.yaml")
        assert isinstance(metadata, dict)
        return Skill(
            name=metadata["name"],
            version=metadata["version"],
            schema_version=metadata["schema_version"],
            description=metadata["description"],
            targets=tuple(metadata["targets"]),
            tags=tuple(metadata.get("tags", [])),
            requires=tuple(metadata.get("requires", [])),
            path=path.resolve(),
        )

    def skills(self) -> list[Skill]:
        errors = self.validate_skills()
        if errors:
            raise SkobalError("; ".join(errors))
        return [self.skill(path) for path in self.skill_directories()]

    def registry_data(self) -> dict[str, list[dict[str, Any]]]:
        records = [
            {
                "name": skill.name,
                "version": skill.version,
                "schema_version": skill.schema_version,
                "description": skill.description,
                "path": self.display_path(skill.path),
                "tags": sorted(skill.tags),
                "targets": sorted(skill.targets),
            }
            for skill in self.skills()
        ]
        records.sort(key=lambda record: record["name"])
        return {"skills": records}

    def registry_text(self) -> str:
        return yaml.safe_dump(
            self.registry_data(),
            sort_keys=False,
            allow_unicode=True,
            width=1000,
        )

    def validate_registry(self) -> list[str]:
        try:
            actual = self.load_yaml(self.registry_path)
        except SkobalError as exc:
            return [str(exc)]
        try:
            expected = self.registry_data()
        except SkobalError:
            return [
                f"{self.display_path(self.registry_path)} is inconsistent with "
                "skills/; run './skillctl registry'"
            ]
        if actual != expected:
            return [
                f"{self.display_path(self.registry_path)} is inconsistent with "
                "skills/; run './skillctl registry'"
            ]
        return []

    def write_registry(self) -> None:
        try:
            self.registry_path.write_text(
                self.registry_text(), encoding="utf-8"
            )
        except OSError as exc:
            raise SkobalError(
                f"cannot write {self.display_path(self.registry_path)}: {exc}"
            ) from exc

    def load_profile(self, name: str) -> dict[str, Any]:
        if NAME_RE.fullmatch(name) is None:
            raise SkobalError("profile name must use lowercase-hyphen format")
        path = self.profiles_dir / f"{name}.yaml"
        data = self.load_yaml(path)
        if not isinstance(data, dict):
            raise SkobalError(f"{self.display_path(path)}: expected a mapping")
        if data.get("name") != name:
            raise SkobalError(
                f"{self.display_path(path)}: name must match filename"
            )
        for key in ("targets", "skills"):
            errors = _validate_string_list(
                data, key, self.display_path(path), non_empty=True
            )
            if errors:
                raise SkobalError(errors[0])
        unknown_targets = sorted(set(data["targets"]) - set(ADAPTER_NAMES))
        if unknown_targets:
            raise SkobalError(
                f"{self.display_path(path)}: unsupported targets: "
                f"{', '.join(unknown_targets)}"
            )
        for skill_name in data["skills"]:
            self.skill_directory(skill_name)
        return data


def valid_skill_name(name: object) -> bool:
    return (
        isinstance(name, str)
        and len(name) < 64
        and NAME_RE.fullmatch(name) is not None
    )


def _validate_string_list(
    metadata: dict[str, Any],
    key: str,
    path: str,
    *,
    non_empty: bool = False,
) -> list[str]:
    value = metadata.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        return [f"{path}: {key} must be a list of non-empty strings"]
    if non_empty and not value:
        return [f"{path}: {key} must be a non-empty list"]
    if len(value) != len(set(value)):
        return [f"{path}: {key} must not contain duplicates"]
    return []
