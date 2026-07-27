"""Atomic managed-install manifest storage."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from skobal.config import state_directory
from skobal.errors import StateError

STATE_SCHEMA_VERSION = 1
_REQUIRED_RECORD_KEYS = {
    "skill",
    "target",
    "source",
    "destination",
    "mode",
    "version",
}


@dataclass(frozen=True)
class InstallRecord:
    """One destination known to have been installed by Skobal."""

    skill: str
    target: str
    source: str
    destination: str
    mode: str
    version: str
    digest: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        """Return a deterministic YAML mapping."""
        return asdict(self)


class StateStore:
    """Read and atomically replace the central install manifest."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory if directory is not None else state_directory()
        self.path = self.directory / "installs.yaml"
        self._loaded = False
        self._records: list[InstallRecord] = []

    @property
    def records(self) -> list[InstallRecord]:
        self._load()
        return list(self._records)

    def find(
        self, *, target: str, skill: str, destination: Path
    ) -> InstallRecord | None:
        destination_text = str(destination.absolute())
        return next(
            (
                record
                for record in self.records
                if record.target == target
                and record.skill == skill
                and record.destination == destination_text
            ),
            None,
        )

    def find_destination(self, destination: Path) -> InstallRecord | None:
        destination_text = str(destination.absolute())
        return next(
            (
                record
                for record in self.records
                if record.destination == destination_text
            ),
            None,
        )

    def for_target_root(self, target: str, root: Path) -> list[InstallRecord]:
        root = root.absolute()
        return sorted(
            (
                record
                for record in self.records
                if record.target == target
                and Path(record.destination).parent == root
            ),
            key=lambda record: (record.skill, record.destination),
        )

    def verify_unchanged(self) -> None:
        """Fail closed if loaded state disappeared, corrupted, or changed."""
        expected = self.records
        if not self.path.exists():
            raise StateError(
                f"managed state disappeared: {self.path}; refusing a "
                "destructive operation"
            )
        current = StateStore(self.directory).records
        if current != expected:
            raise StateError(
                f"managed state changed during operation: {self.path}; retry"
            )

    def replace(self, record: InstallRecord) -> None:
        records = [
            existing
            for existing in self.records
            if existing.destination != record.destination
        ]
        records.append(record)
        self._save(records)

    def remove(self, record: InstallRecord) -> None:
        records = [
            existing
            for existing in self.records
            if existing != record
        ]
        self._save(records)

    def _load(self) -> None:
        if self._loaded:
            return
        if not self.path.exists():
            self._records = []
            self._loaded = True
            return
        try:
            payload = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise StateError(f"cannot read managed state {self.path}: {exc}") from exc
        except yaml.YAMLError as exc:
            raise StateError(f"corrupted managed state {self.path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise StateError(
                f"corrupted managed state {self.path}: expected a mapping"
            )
        if payload.get("schema_version") != STATE_SCHEMA_VERSION:
            raise StateError(
                f"unsupported managed state schema_version in {self.path}: "
                f"{payload.get('schema_version')!r}"
            )
        raw_records = payload.get("installs")
        if not isinstance(raw_records, list):
            raise StateError(
                f"corrupted managed state {self.path}: installs must be a list"
            )
        records: list[InstallRecord] = []
        destinations: set[str] = set()
        for index, item in enumerate(raw_records):
            if not isinstance(item, dict):
                raise StateError(
                    f"corrupted managed state {self.path}: "
                    f"installs[{index}] must be a mapping"
                )
            missing = _REQUIRED_RECORD_KEYS - set(item)
            if missing:
                raise StateError(
                    f"corrupted managed state {self.path}: installs[{index}] "
                    f"missing {', '.join(sorted(missing))}"
                )
            values = {key: item.get(key) for key in _REQUIRED_RECORD_KEYS}
            if any(not isinstance(value, str) for value in values.values()):
                raise StateError(
                    f"corrupted managed state {self.path}: installs[{index}] "
                    "fields must be strings"
                )
            digest = item.get("digest")
            if digest is not None and not isinstance(digest, str):
                raise StateError(
                    f"corrupted managed state {self.path}: installs[{index}] "
                    "digest must be a string or null"
                )
            if values["mode"] not in {"copy", "symlink"}:
                raise StateError(
                    f"corrupted managed state {self.path}: installs[{index}] "
                    f"has invalid mode {values['mode']!r}"
                )
            record = InstallRecord(
                skill=values["skill"],
                target=values["target"],
                source=values["source"],
                destination=values["destination"],
                mode=values["mode"],
                version=values["version"],
                digest=digest,
            )
            if record.destination in destinations:
                raise StateError(
                    f"corrupted managed state {self.path}: duplicate destination "
                    f"{record.destination}"
                )
            destinations.add(record.destination)
            records.append(record)
        self._records = self._sorted(records)
        self._loaded = True

    def _save(self, records: Iterable[InstallRecord]) -> None:
        ordered = self._sorted(records)
        payload = {
            "schema_version": STATE_SCHEMA_VERSION,
            "installs": [record.to_mapping() for record in ordered],
        }
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StateError(
                f"cannot create managed state directory {self.directory}: {exc}"
            ) from exc
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".installs-", suffix=".tmp", dir=self.directory
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                yaml.safe_dump(
                    payload,
                    handle,
                    sort_keys=False,
                    allow_unicode=True,
                    width=1000,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except OSError as exc:
            raise StateError(
                f"cannot atomically write managed state {self.path}: {exc}"
            ) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        self._records = ordered
        self._loaded = True

    @staticmethod
    def _sorted(records: Iterable[InstallRecord]) -> list[InstallRecord]:
        return sorted(
            records,
            key=lambda record: (
                record.target,
                record.skill,
                record.destination,
                record.source,
            ),
        )
