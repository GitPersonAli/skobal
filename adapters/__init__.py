"""Filesystem adapters and adapter discovery for Skobal."""

from __future__ import annotations

import hashlib
import importlib
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

ADAPTER_NAMES = ("claude", "cursor", "opencode")
_NAME_PATTERN = "Adapter skill names must be a single path component"
_COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__", ".pytest_cache", "*.pyc", "*.pyo"
)


class Adapter(ABC):
    """Contract implemented by every skill installation target."""

    name: ClassVar[str]

    @abstractmethod
    def default_dest(self) -> Path:
        """Return the adapter's installation directory."""

    @abstractmethod
    def prepare(self, source: Path, prepared: Path, *, copy: bool) -> None:
        """Prepare a complete install at a same-filesystem temporary path."""

    @abstractmethod
    def verify_prepared(self, source: Path, prepared: Path, *, copy: bool) -> None:
        """Raise if a prepared install is incomplete or points elsewhere."""


class FilesystemAdapter(Adapter):
    """Shared filesystem behavior; policy and transactions live in skobal.sync."""

    env_var: ClassVar[str]
    home_relative_dest: ClassVar[Path]

    def default_dest(self) -> Path:
        override = os.environ.get(self.env_var)
        if override:
            return Path(override).expanduser()
        return Path.home() / self.home_relative_dest

    def target(self, name: str) -> Path:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError(_NAME_PATTERN)
        return self.default_dest() / name

    def prepare(self, source: Path, prepared: Path, *, copy: bool) -> None:
        if copy:
            shutil.copytree(source, prepared, ignore=_COPY_IGNORE)
        else:
            prepared.symlink_to(source, target_is_directory=True)

    def verify_prepared(self, source: Path, prepared: Path, *, copy: bool) -> None:
        source = source.resolve()
        if copy:
            if (
                not prepared.is_dir()
                or prepared.is_symlink()
                or tree_digest(prepared) != tree_digest(source)
            ):
                raise OSError(f"prepared copy verification failed: {prepared}")
            return
        if (
            not prepared.is_symlink()
            or not prepared.exists()
            or prepared.resolve(strict=False) != source
        ):
            raise OSError(f"prepared symlink verification failed: {prepared}")

    # Compatibility wrappers for callers of the original adapter API.
    def plan_install(self, skill_dir: Path, name: str, copy: bool = False) -> str:
        from skobal.errors import ConflictError
        from skobal.state import StateStore
        from skobal.sync import plan_install

        try:
            return plan_install(
                self,
                skill_dir,
                name,
                version=_source_version(skill_dir),
                copy=copy,
                force=False,
                store=StateStore(),
            ).action
        except ConflictError as exc:
            raise FileExistsError(str(exc)) from exc

    def install(self, skill_dir: Path, name: str, copy: bool = False) -> str:
        from skobal.errors import ConflictError
        from skobal.state import StateStore
        from skobal.sync import install_one

        try:
            return install_one(
                self,
                skill_dir,
                name,
                version=_source_version(skill_dir),
                copy=copy,
                force=False,
                store=StateStore(),
            ).action
        except ConflictError as exc:
            raise FileExistsError(str(exc)) from exc

    def uninstall(self, name: str) -> str:
        from skobal.errors import ConflictError
        from skobal.state import StateStore
        from skobal.sync import uninstall_one

        store = StateStore()
        target = self.target(name)
        record = store.find(
            target=self.name, skill=name, destination=target.absolute()
        )
        if record is None:
            if present(target):
                raise PermissionError(
                    f"refusing to remove unmanaged destination: {target}"
                )
            return "skipped"
        try:
            uninstall_one(self, record, store)
        except ConflictError as exc:
            raise PermissionError(
                f"refusing to remove unmanaged/changed destination: {target}: {exc}"
            ) from exc
        return "removed"

    def installed(self) -> list[str]:
        from skobal.state import StateStore
        from skobal.sync import record_is_intact

        store = StateStore()
        return sorted(
            record.skill
            for record in store.for_target_root(self.name, self.default_dest())
            if record_is_intact(record)
        )


def present(path: Path) -> bool:
    """Return true for files, directories, and dangling symlinks."""
    return path.exists() or path.is_symlink()


def remove_path(path: Path) -> None:
    """Remove one known, explicit path without following symlinks."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def tree_digest(root: Path) -> str:
    """Hash a directory tree deterministically, excluding runtime caches."""
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
    adapter_class = module.ADAPTER_CLASS
    adapter = adapter_class()
    if not isinstance(adapter, Adapter):
        raise TypeError(f"{name} did not provide an Adapter implementation")
    return adapter


def discover_adapters() -> dict[str, Adapter]:
    """Return all available adapters keyed by target name."""
    return {name: get_adapter(name) for name in ADAPTER_NAMES}


def _source_version(skill_dir: Path) -> str:
    try:
        import yaml

        payload = yaml.safe_load(
            (skill_dir / "skill.yaml").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return "0.0.0"
    if isinstance(payload, dict) and isinstance(payload.get("version"), str):
        return payload["version"]
    return "0.0.0"


__all__ = [
    "ADAPTER_NAMES",
    "Adapter",
    "FilesystemAdapter",
    "discover_adapters",
    "get_adapter",
    "present",
    "remove_path",
    "tree_digest",
]
