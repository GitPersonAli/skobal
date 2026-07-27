"""Collision-safe, per-install atomic synchronization."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from adapters import FilesystemAdapter, present, remove_path, tree_digest
from skobal.errors import ConflictError, SyncError
from skobal.schema import Repository
from skobal.state import InstallRecord, StateStore


@dataclass(frozen=True)
class InstallPlan:
    """One classified install operation."""

    action: str
    destination: Path
    mode: str
    classification: str
    backup_required: bool = False


@dataclass(frozen=True)
class InstallResult:
    """Result of one completed or skipped install."""

    action: str
    destination: Path
    mode: str
    backup: Path | None = None


def plan_install(
    adapter: FilesystemAdapter,
    source: Path,
    skill: str,
    *,
    version: str,
    copy: bool,
    force: bool,
    store: StateStore,
) -> InstallPlan:
    """Classify a destination without changing it."""
    source = source.resolve()
    if not source.is_dir():
        raise SyncError(f"skill directory does not exist: {source}")
    destination = adapter.target(skill).absolute()
    mode = "copy" if copy else "symlink"
    record = store.find(
        target=adapter.name, skill=skill, destination=destination
    )
    destination_record = store.find_destination(destination)

    if destination.is_symlink() and not destination.exists():
        raise ConflictError(
            f"dangling symlink at {destination}; remove or repair it manually"
        )
    if not present(destination):
        if destination_record is not None and destination_record != record:
            raise ConflictError(
                f"{destination} is recorded for skill "
                f"{destination_record.skill!r}, not {skill!r}"
            )
        return InstallPlan("installed", destination, mode, "absent")
    if record is None:
        if destination_record is not None:
            raise ConflictError(
                f"{destination} is managed as skill "
                f"{destination_record.skill!r}, not {skill!r}"
            )
        if not force:
            raise ConflictError(
                f"refusing to replace unmanaged destination: {destination}; "
                "rerun with --force to back it up first"
            )
        return InstallPlan(
            "installed",
            destination,
            mode,
            "unmanaged",
            backup_required=True,
        )

    recorded_source = Path(record.source).resolve(strict=False)
    if recorded_source != source:
        raise ConflictError(
            f"{destination} is managed from another source "
            f"({record.source}); expected {source}"
        )
    if record.mode == "symlink":
        if not destination.is_symlink():
            raise ConflictError(
                f"managed symlink destination changed type: {destination}"
            )
        actual_source = destination.resolve(strict=False)
        if actual_source != recorded_source:
            raise ConflictError(
                f"managed symlink points at wrong source: {destination} -> "
                f"{actual_source}; expected {recorded_source}"
            )
    else:
        if not destination.is_dir() or destination.is_symlink():
            raise ConflictError(
                f"managed copy destination changed type: {destination}"
            )
        installed_digest = tree_digest(destination)
        if record.digest is None or installed_digest != record.digest:
            raise ConflictError(
                f"managed copy was modified: {destination}; refusing to "
                "overwrite user changes"
            )

    if record.mode == mode and record.version == version:
        if mode == "symlink":
            return InstallPlan("skipped", destination, mode, "managed-expected")
        if tree_digest(source) == tree_digest(destination):
            return InstallPlan("skipped", destination, mode, "managed-expected")
    return InstallPlan("updated", destination, mode, "managed-expected")


def install_one(
    adapter: FilesystemAdapter,
    source: Path,
    skill: str,
    *,
    version: str,
    copy: bool,
    force: bool,
    store: StateStore,
) -> InstallResult:
    """Install one skill with rollback around destination and state changes."""
    plan = plan_install(
        adapter,
        source,
        skill,
        version=version,
        copy=copy,
        force=force,
        store=store,
    )
    if plan.action == "skipped":
        return InstallResult(
            plan.action, plan.destination, plan.mode, backup=None
        )

    source = source.resolve()
    destination_root = plan.destination.parent
    try:
        destination_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SyncError(
            f"cannot create destination directory {destination_root}: {exc}"
        ) from exc

    transaction_dir = Path(
        tempfile.mkdtemp(
            prefix=f".skobal-txn-{skill}-",
            dir=destination_root,
        )
    )
    prepared = transaction_dir / "prepared"
    rollback_path = transaction_dir / "previous"
    persistent_backup: Path | None = None
    previous_moved = False
    installed_new = False
    try:
        try:
            adapter.prepare(source, prepared, copy=copy)
        except OSError as exc:
            if not copy and isinstance(exc, PermissionError):
                raise SyncError(
                    f"cannot create symlink for {adapter.name}/{skill}: {exc}. "
                    "On Windows, enable Developer Mode/run with symlink "
                    "permission or use --copy."
                ) from exc
            raise SyncError(
                f"failed to prepare {adapter.name}/{skill}: {exc}"
            ) from exc
        adapter.verify_prepared(source, prepared, copy=copy)

        if present(plan.destination):
            if not plan.backup_required:
                store.verify_unchanged()
            if plan.backup_required:
                persistent_backup = _backup_path(
                    destination_root, adapter.name, skill
                )
                persistent_backup.parent.mkdir(parents=True, exist_ok=False)
                os.replace(plan.destination, persistent_backup)
                previous_moved = True
            else:
                os.replace(plan.destination, rollback_path)
                previous_moved = True

        os.replace(prepared, plan.destination)
        installed_new = True
        digest = tree_digest(source) if copy else None
        store.replace(
            InstallRecord(
                skill=skill,
                target=adapter.name,
                source=str(source),
                destination=str(plan.destination),
                mode=plan.mode,
                version=version,
                digest=digest,
            )
        )
    except Exception as exc:
        rollback_error = _restore_previous(
            plan.destination,
            rollback_path,
            persistent_backup,
            previous_moved=previous_moved,
            installed_new=installed_new,
        )
        _cleanup_transaction(transaction_dir)
        if persistent_backup is not None:
            _cleanup_empty_backup_parents(persistent_backup, destination_root)
        if rollback_error is not None:
            raise SyncError(
                f"{adapter.name}/{skill} failed ({exc}); rollback also failed: "
                f"{rollback_error}. Recover the previous install from "
                f"{rollback_path if rollback_path.exists() else persistent_backup}"
            ) from exc
        if isinstance(exc, (ConflictError, SyncError)):
            raise
        raise SyncError(
            f"{adapter.name}/{skill} failed; previous install restored: {exc}"
        ) from exc

    _cleanup_transaction(transaction_dir)
    return InstallResult(
        plan.action,
        plan.destination,
        plan.mode,
        backup=persistent_backup,
    )


def uninstall_one(
    adapter: FilesystemAdapter,
    record: InstallRecord,
    store: StateStore,
    *,
    dry_run: bool = False,
) -> str:
    """Prune one exact, intact manifest record with rollback."""
    destination = Path(record.destination)
    expected_root = adapter.default_dest().absolute()
    if record.target != adapter.name or destination.parent != expected_root:
        raise ConflictError(
            f"managed record does not match {adapter.name} destination: {destination}"
        )
    if not present(destination):
        if not dry_run:
            store.remove(record)
        return "removed"
    if not record_is_intact(record):
        raise ConflictError(
            f"refusing to prune changed or wrong-source managed install: "
            f"{destination}"
        )
    if dry_run:
        return "removed"
    store.verify_unchanged()

    root = destination.parent
    transaction_dir = Path(
        tempfile.mkdtemp(
            prefix=f".skobal-prune-{record.skill}-",
            dir=root,
        )
    )
    rollback_path = transaction_dir / "previous"
    try:
        os.replace(destination, rollback_path)
        try:
            store.remove(record)
        except Exception:
            os.replace(rollback_path, destination)
            raise
    except Exception as exc:
        _cleanup_transaction(transaction_dir)
        if isinstance(exc, ConflictError):
            raise
        raise SyncError(
            f"failed to prune {adapter.name}/{record.skill}: {exc}"
        ) from exc
    _cleanup_transaction(transaction_dir)
    return "removed"


def record_is_intact(record: InstallRecord) -> bool:
    """Return whether disk still exactly matches a manifest record."""
    destination = Path(record.destination)
    if not present(destination):
        return False
    source = Path(record.source).resolve(strict=False)
    if record.mode == "symlink":
        return (
            destination.is_symlink()
            and destination.exists()
            and destination.resolve(strict=False) == source
        )
    return (
        destination.is_dir()
        and not destination.is_symlink()
        and record.digest is not None
        and tree_digest(destination) == record.digest
    )


def sync_profile(
    repository: Repository,
    profile_name: str,
    *,
    target_name: str | None,
    copy: bool,
    dry_run: bool,
    prune: bool,
    force: bool,
    store: StateStore,
) -> list[str]:
    """Synchronize a profile and return deterministic human-readable lines."""
    from adapters import get_adapter

    profile = repository.load_profile(profile_name)
    targets = list(profile["targets"])
    if target_name is not None:
        if target_name not in targets:
            raise SyncError(
                f"target {target_name!r} is not enabled by profile "
                f"{profile_name!r}"
            )
        targets = [target_name]
    # Load before changing anything so corrupt state always fails closed.
    _records = store.records
    lines: list[str] = []
    desired = set(profile["skills"])
    mode = "copy" if copy else "symlink"
    for selected_target in targets:
        adapter = get_adapter(selected_target)
        if not isinstance(adapter, FilesystemAdapter):
            raise SyncError(
                f"{selected_target}: adapter does not support filesystem sync"
            )
        for skill_name in profile["skills"]:
            skill = repository.skill(
                repository.skill_directory(skill_name)
            )
            if selected_target not in skill.targets:
                raise SyncError(
                    f"{selected_target}/{skill_name}: target is not enabled "
                    "in skill.yaml"
                )
            if dry_run:
                plan = plan_install(
                    adapter,
                    skill.path,
                    skill.name,
                    version=skill.version,
                    copy=copy,
                    force=force,
                    store=store,
                )
                verb = {
                    "installed": "would install",
                    "updated": "would update",
                    "skipped": "would skip",
                }[plan.action]
                line = f"{selected_target}/{skill.name}: {verb} ({mode})"
                if plan.backup_required:
                    line += (
                        f"; would back up {plan.destination} under "
                        f"{plan.destination.parent / '.skobal-backups'}"
                    )
                lines.append(line)
            else:
                result = install_one(
                    adapter,
                    skill.path,
                    skill.name,
                    version=skill.version,
                    copy=copy,
                    force=force,
                    store=store,
                )
                line = (
                    f"{selected_target}/{skill.name}: {result.action} "
                    f"({result.mode})"
                )
                if result.backup is not None:
                    line += f"; backup: {result.backup}"
                lines.append(line)

        if prune:
            records = store.for_target_root(
                selected_target, adapter.default_dest()
            )
            for record in records:
                if record.skill in desired:
                    continue
                uninstall_one(adapter, record, store, dry_run=dry_run)
                verb = "would remove" if dry_run else "removed"
                lines.append(
                    f"{selected_target}/{record.skill}: {verb} (prune)"
                )
    return lines


def _backup_path(root: Path, target: str, skill: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return root / ".skobal-backups" / timestamp / target / skill


def _restore_previous(
    destination: Path,
    rollback_path: Path,
    persistent_backup: Path | None,
    *,
    previous_moved: bool,
    installed_new: bool,
) -> OSError | None:
    try:
        if installed_new and present(destination):
            remove_path(destination)
        if previous_moved:
            source = (
                persistent_backup
                if persistent_backup is not None
                else rollback_path
            )
            if source is not None and present(source):
                os.replace(source, destination)
        return None
    except OSError as exc:
        return exc


def _cleanup_transaction(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)


def _cleanup_empty_backup_parents(path: Path, stop: Path) -> None:
    parent = path.parent
    while parent != stop and parent.is_dir():
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
