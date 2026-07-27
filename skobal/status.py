"""Read-only synchronization status."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from adapters import FilesystemAdapter, get_adapter, present, tree_digest
from skobal.errors import SkobalError
from skobal.schema import Repository, Skill
from skobal.state import InstallRecord, StateStore


@dataclass(frozen=True)
class StatusItem:
    """Script-friendly status for one profile skill and target."""

    skill: str
    target: str
    status: str
    source: str
    destination: str
    mode: str | None
    version: str
    installed_version: str | None

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def profile_status(
    repository: Repository,
    profile_name: str,
    *,
    target_name: str | None,
    store: StateStore,
) -> list[StatusItem]:
    """Return deterministic status without creating any directories."""
    profile = repository.load_profile(profile_name)
    targets = list(profile["targets"])
    if target_name is not None:
        if target_name not in targets:
            raise SkobalError(
                f"target {target_name!r} is not enabled by profile "
                f"{profile_name!r}"
            )
        targets = [target_name]
    _records = store.records
    items: list[StatusItem] = []
    for selected_target in targets:
        adapter = get_adapter(selected_target)
        if not isinstance(adapter, FilesystemAdapter):
            raise SkobalError(
                f"{selected_target}: adapter does not support filesystem status"
            )
        for skill_name in profile["skills"]:
            skill = repository.skill(
                repository.skill_directory(skill_name)
            )
            items.append(_skill_status(adapter, skill, store))
    return sorted(items, key=lambda item: (item.target, item.skill))


def _skill_status(
    adapter: FilesystemAdapter,
    skill: Skill,
    store: StateStore,
) -> StatusItem:
    destination = adapter.target(skill.name).absolute()
    source = skill.path.resolve()
    record = store.find(
        target=adapter.name, skill=skill.name, destination=destination
    )
    base = {
        "skill": skill.name,
        "target": adapter.name,
        "source": str(source),
        "destination": str(destination),
        "mode": record.mode if record else None,
        "version": skill.version,
        "installed_version": record.version if record else None,
    }
    if adapter.name not in skill.targets:
        return StatusItem(status="unsupported", **base)
    if destination.is_symlink() and not destination.exists():
        return StatusItem(status="dangling-symlink", **base)
    if not present(destination):
        return StatusItem(status="missing", **base)
    if record is None:
        destination_record = store.find_destination(destination)
        status = "wrong-source" if destination_record else "unmanaged-conflict"
        return StatusItem(status=status, **base)
    if record.version != skill.version:
        return StatusItem(status="outdated", **base)
    if Path(record.source).resolve(strict=False) != source:
        return StatusItem(status="wrong-source", **base)
    if record.mode == "symlink":
        status = _symlink_status(destination, record)
    else:
        status = _copy_status(destination, source)
    return StatusItem(status=status, **base)


def _symlink_status(destination: Path, record: InstallRecord) -> str:
    if not destination.is_symlink():
        return "wrong-source"
    if destination.resolve(strict=False) != Path(record.source).resolve(strict=False):
        return "wrong-source"
    return "synced"


def _copy_status(destination: Path, source: Path) -> str:
    if not destination.is_dir() or destination.is_symlink():
        return "modified"
    if tree_digest(destination) != tree_digest(source):
        return "modified"
    return "synced"
