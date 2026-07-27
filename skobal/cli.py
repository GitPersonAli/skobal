"""Command-line interface for the Skobal skill catalog."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import yaml

from adapters import ADAPTER_NAMES, get_adapter
from skobal.config import repository_root
from skobal.errors import SkobalError
from skobal.gitops import GitRepository
from skobal.schema import Repository, valid_skill_name
from skobal.state import StateStore
from skobal.status import profile_status
from skobal.sync import sync_profile
from skobal.update import run_update


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print("  ".join(value.ljust(widths[index]) for index, value in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def cmd_list(args: argparse.Namespace) -> int:
    repository = _repository(args)
    rows = [
        [
            skill.name,
            skill.version,
            skill.description,
            ", ".join(skill.tags),
        ]
        for skill in repository.skills()
    ]
    print_table(["NAME", "VERSION", "DESCRIPTION", "TAGS"], rows)
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    repository = _repository(args)
    if not valid_skill_name(args.name):
        raise SkobalError(
            "skill name must use lowercase-hyphen format and be under "
            "64 characters"
        )
    destination = repository.skills_dir / args.name
    if destination.exists():
        raise SkobalError(f"skill already exists: {args.name}")
    template = repository.skills_dir / "_template"
    if not template.is_dir():
        raise SkobalError("missing skills/_template")
    replacements = {
        "{{ name }}": args.name,
        "{{name}}": args.name,
        "{{ date }}": date.today().isoformat(),
        "{{date}}": date.today().isoformat(),
    }
    try:
        for source in sorted(template.rglob("*")):
            relative = source.relative_to(template)
            target_name = relative.name.removesuffix(".tmpl")
            target = destination / relative.parent / target_name
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source.read_text(encoding="utf-8")
            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)
            target.write_text(content, encoding="utf-8")
            if source.parent.name == "scripts":
                target.chmod(target.stat().st_mode | 0o111)
    except OSError as exc:
        if destination.exists():
            shutil.rmtree(destination)
        raise SkobalError(f"failed to create skill {args.name}: {exc}") from exc
    print(f"Created skills/{args.name}")
    print("Run './skillctl registry' to add it to registry.yaml.")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    repository = _repository(args)
    paths = (
        [repository.skill_directory(args.name)]
        if args.name
        else repository.skill_directories()
    )
    errors = repository.validate_skills(paths)
    errors.extend(repository.validate_registry())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    noun = args.name if args.name else f"{len(paths)} skills"
    print(f"Validation passed for {noun}; registry.yaml is consistent.")
    return 0


def cmd_registry(args: argparse.Namespace) -> int:
    repository = _repository(args)
    errors = repository.validate_skills()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    try:
        repository.write_registry()
    except OSError as exc:
        raise SkobalError(f"cannot write registry.yaml: {exc}") from exc
    print(
        f"Wrote registry.yaml ({len(repository.skill_directories())} skills)."
    )
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    lines = sync_profile(
        _repository(args),
        args.profile,
        target_name=args.target,
        copy=args.copy,
        dry_run=args.dry_run,
        prune=args.prune,
        force=args.force,
        store=StateStore(),
    )
    for line in lines:
        print(line)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    items = profile_status(
        _repository(args),
        args.profile,
        target_name=args.target,
        store=StateStore(),
    )
    if args.json:
        print(
            json.dumps(
                [item.to_mapping() for item in items],
                indent=2,
                sort_keys=True,
            )
        )
    else:
        rows = [
            [
                item.target,
                item.skill,
                item.status,
                item.mode or "-",
                item.version,
                item.installed_version or "-",
                item.destination,
            ]
            for item in items
        ]
        print_table(
            [
                "TARGET",
                "SKILL",
                "STATUS",
                "MODE",
                "VERSION",
                "INSTALLED",
                "DESTINATION",
            ],
            rows,
        )
    return 0 if all(item.status == "synced" for item in items) else 1


def cmd_test(args: argparse.Namespace) -> int:
    repository = _repository(args)
    try:
        import pytest  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SkobalError(
            "pytest is required for skill tests; install it with: "
            "python3 -m pip install pytest"
        ) from exc
    candidates = (
        [repository.skill_directory(args.name)]
        if args.name
        else repository.skill_directories()
    )
    test_dirs = [path / "tests" for path in candidates if (path / "tests").is_dir()]
    if args.name and not test_dirs:
        raise SkobalError(f"skill has no tests directory: {args.name}")
    if not test_dirs:
        print("No skill tests found.")
        return 0
    command = [sys.executable, "-m", "pytest", *map(str, test_dirs), "-q"]
    return subprocess.run(
        command,
        cwd=repository.root,
        check=False,
    ).returncode


def writable_or_creatable(path: Path) -> tuple[bool, str]:
    if path.exists():
        if not path.is_dir():
            return False, "exists but is not a directory"
        writable = os.access(path, os.W_OK)
        return writable, "writable" if writable else "not writable"
    ancestor = path
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    writable = ancestor.is_dir() and os.access(ancestor, os.W_OK)
    state = f"creatable via {ancestor}" if writable else f"not creatable via {ancestor}"
    return writable, state


def cmd_doctor(_args: argparse.Namespace) -> int:
    healthy = True
    version = sys.version_info
    python_ok = version >= (3, 10)
    healthy &= python_ok
    print(
        f"python: {'ok' if python_ok else 'error'} "
        f"({version.major}.{version.minor}.{version.micro})"
    )
    print(f"PyYAML: ok ({yaml.__version__})")
    try:
        records = StateStore().records
        print(f"managed state: ok ({len(records)} installs)")
    except SkobalError as exc:
        healthy = False
        print(f"managed state: error ({exc})")

    for name in ADAPTER_NAMES:
        adapter = get_adapter(name)
        destination = adapter.default_dest()
        writable, state = writable_or_creatable(destination)
        healthy &= writable
        print(f"{name}: {'ok' if writable else 'error'} ({destination}; {state})")
        if destination.is_dir():
            dangling = sorted(
                path.name
                for path in destination.iterdir()
                if path.is_symlink() and not path.exists()
            )
            for skill_name in dangling:
                healthy = False
                print(f"{name}: error (dangling symlink: {skill_name})")
    return 0 if healthy else 1


def cmd_update(args: argparse.Namespace) -> int:
    repository = _repository(args)
    lines = run_update(
        repository,
        args.profile,
        dry_run=args.dry_run,
        git=GitRepository(repository.root),
        store=StateStore(),
    )
    for line in lines:
        print(line)
    return 0


def build_parser(root: Path | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillctl",
        description="Manage Skobal skills, profiles, registry, and adapters.",
    )
    parser.set_defaults(repository_root=root or repository_root())
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list repository skills")
    list_parser.set_defaults(func=cmd_list)

    new_parser = subparsers.add_parser("new", help="scaffold a skill")
    new_parser.add_argument("name")
    new_parser.set_defaults(func=cmd_new)

    validate_parser = subparsers.add_parser(
        "validate", help="validate skills and registry"
    )
    validate_parser.add_argument("name", nargs="?")
    validate_parser.set_defaults(func=cmd_validate)

    registry_parser = subparsers.add_parser(
        "registry", help="regenerate registry.yaml"
    )
    registry_parser.set_defaults(func=cmd_registry)

    sync_parser = subparsers.add_parser("sync", help="sync a profile to adapters")
    sync_parser.add_argument("--profile", required=True)
    sync_parser.add_argument("--target", choices=ADAPTER_NAMES)
    sync_parser.add_argument("--copy", action="store_true")
    sync_parser.add_argument("--dry-run", action="store_true")
    sync_parser.add_argument("--prune", action="store_true")
    sync_parser.add_argument(
        "--force",
        action="store_true",
        help="back up an unmanaged collision before installing",
    )
    sync_parser.set_defaults(func=cmd_sync)

    status_parser = subparsers.add_parser(
        "status", help="report profile synchronization status"
    )
    status_parser.add_argument("--profile", default="personal")
    status_parser.add_argument("--target", choices=ADAPTER_NAMES)
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(func=cmd_status)

    test_parser = subparsers.add_parser("test", help="run skill-local pytest suites")
    test_parser.add_argument("name", nargs="?")
    test_parser.set_defaults(func=cmd_test)

    doctor_parser = subparsers.add_parser(
        "doctor", help="check Python, state, and adapter destinations"
    )
    doctor_parser.set_defaults(func=cmd_doctor)

    update_parser = subparsers.add_parser(
        "update", help="safely pull, validate, index, and sync"
    )
    update_parser.add_argument("--profile", default="personal")
    update_parser.add_argument("--dry-run", action="store_true")
    update_parser.set_defaults(func=cmd_update)
    return parser


def main(argv: Sequence[str] | None = None, *, root: Path | None = None) -> int:
    parser = build_parser(root)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (SkobalError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _repository(args: argparse.Namespace) -> Repository:
    return Repository(Path(args.repository_root))
