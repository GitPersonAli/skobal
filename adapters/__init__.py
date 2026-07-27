"""Filesystem adapters and adapter discovery for Skobal."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar


ADAPTER_NAMES = ("claude", "cursor", "opencode")
_NAME_PATTERN = "Adapter skill names must be a single path component"


class Adapter(ABC):
    """Contract implemented by every skill installation target."""

    name: ClassVar[str]

    @abstractmethod
    def default_dest(self) -> Path:
        """Return the adapter's installation directory."""

    @abstractmethod
    def install(self, skill_dir: Path, name: str, copy: bool = False) -> str:
        """Install a skill and return installed, updated, or skipped."""

    @abstractmethod
    def uninstall(self, name: str) -> str:
        """Remove a managed skill and return removed or skipped."""

    @abstractmethod
    def installed(self) -> list[str]:
        """Return sorted names of skills currently managed by Skobal."""


class FilesystemAdapter(Adapter):
    """Safe shared implementation for directory-based skill targets."""

    env_var: ClassVar[str]
    home_relative_dest: ClassVar[Path]
    marker_dir_name: ClassVar[str] = ".skobal-managed"

    def default_dest(self) -> Path:
        override = os.environ.get(self.env_var)
        if override:
            return Path(override).expanduser()
        return Path.home() / self.home_relative_dest

    def install(self, skill_dir: Path, name: str, copy: bool = False) -> str:
        skill_dir = skill_dir.resolve()
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"skill directory does not exist: {skill_dir}")

        action = self.plan_install(skill_dir, name, copy=copy)
        if action == "skipped":
            return action

        destination = self.default_dest()
        target = self._target(name)
        destination.mkdir(parents=True, exist_ok=True)

        if self._present(target):
            self._remove_path(target)

        if copy:
            shutil.copytree(
                skill_dir,
                target,
                ignore=shutil.ignore_patterns(
                    "__pycache__", ".pytest_cache", "*.pyc", "*.pyo"
                ),
            )
        else:
            target.symlink_to(skill_dir, target_is_directory=True)

        marker = self._marker(name)
        marker.parent.mkdir(parents=True, exist_ok=True)
        mode = "copy" if copy else "symlink"
        marker.write_text(
            json.dumps(
                {
                    "adapter": self.name,
                    "digest": self._tree_digest(target) if copy else None,
                    "mode": mode,
                    "name": name,
                    "source": str(skill_dir),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return action

    def plan_install(self, skill_dir: Path, name: str, copy: bool = False) -> str:
        """Return the action install would take without changing the filesystem."""
        skill_dir = skill_dir.resolve()
        target = self._target(name)
        if not self._present(target):
            return "installed"
        if not self._is_managed(name):
            raise FileExistsError(
                f"refusing to replace unmanaged destination: {target}"
            )

        if copy:
            if target.is_dir() and not target.is_symlink():
                if self._tree_digest(target) == self._tree_digest(skill_dir):
                    return "skipped"
        elif target.is_symlink() and target.resolve(strict=False) == skill_dir:
            return "skipped"
        return "updated"

    def uninstall(self, name: str) -> str:
        target = self._target(name)
        marker = self._marker(name)
        if not self._is_managed(name):
            if self._present(target):
                raise PermissionError(
                    f"refusing to remove unmanaged destination: {target}"
                )
            return "skipped"

        if self._present(target):
            self._remove_path(target)
        marker.unlink()
        marker_dir = marker.parent
        if marker_dir.is_dir() and not any(marker_dir.iterdir()):
            marker_dir.rmdir()
        return "removed"

    def installed(self) -> list[str]:
        marker_dir = self.default_dest() / self.marker_dir_name
        if not marker_dir.is_dir():
            return []
        names = []
        for marker in marker_dir.glob("*.json"):
            name = marker.stem
            if self._present(self._target(name)) and self._valid_marker(name):
                names.append(name)
        return sorted(names)

    def _target(self, name: str) -> Path:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError(_NAME_PATTERN)
        return self.default_dest() / name

    def _marker(self, name: str) -> Path:
        self._target(name)
        return self.default_dest() / self.marker_dir_name / f"{name}.json"

    def _is_managed(self, name: str) -> bool:
        return self._valid_marker(name)

    def _valid_marker(self, name: str) -> bool:
        try:
            payload = json.loads(self._marker(name).read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        if payload.get("adapter") != self.name or payload.get("name") != name:
            return False

        source_value = payload.get("source")
        if not isinstance(source_value, str):
            return False
        source = Path(source_value)
        target = self._target(name)
        if payload.get("mode") == "symlink":
            return (
                target.is_symlink()
                and target.resolve(strict=False) == source.resolve(strict=False)
            )
        if payload.get("mode") == "copy":
            return (
                target.is_dir()
                and not target.is_symlink()
                and payload.get("digest") == self._tree_digest(target)
            )
        return False

    @staticmethod
    def _present(path: Path) -> bool:
        return path.exists() or path.is_symlink()

    @staticmethod
    def _remove_path(path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

    @staticmethod
    def _tree_digest(root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if (
                any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)
                or path.suffix in {".pyc", ".pyo"}
            ):
                continue
            relative = path.relative_to(root).as_posix().encode()
            if path.is_symlink():
                digest.update(b"L")
                digest.update(relative)
                digest.update(os.readlink(path).encode())
            elif path.is_dir():
                digest.update(b"D")
                digest.update(relative)
            elif path.is_file():
                digest.update(b"F")
                digest.update(relative)
                digest.update(path.read_bytes())
        return digest.hexdigest()


def get_adapter(name: str) -> Adapter:
    """Discover and instantiate an adapter by name."""
    if name not in ADAPTER_NAMES:
        choices = ", ".join(ADAPTER_NAMES)
        raise KeyError(f"unknown adapter {name!r}; choose one of: {choices}")
    module = importlib.import_module(f"adapters.{name}")
    adapter_class = getattr(module, "ADAPTER_CLASS")
    adapter = adapter_class()
    if not isinstance(adapter, Adapter):
        raise TypeError(f"{name} did not provide an Adapter implementation")
    return adapter


def discover_adapters() -> dict[str, Adapter]:
    """Return all available adapters keyed by target name."""
    return {name: get_adapter(name) for name in ADAPTER_NAMES}


__all__ = [
    "ADAPTER_NAMES",
    "Adapter",
    "FilesystemAdapter",
    "discover_adapters",
    "get_adapter",
]
