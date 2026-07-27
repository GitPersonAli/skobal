"""Safe pull, validation, registry, and sync orchestration."""

from __future__ import annotations

from skobal.errors import SkobalError
from skobal.gitops import GitRepository
from skobal.schema import Repository
from skobal.state import StateStore
from skobal.sync import sync_profile


def run_update(
    repository: Repository,
    profile_name: str,
    *,
    dry_run: bool,
    git: GitRepository,
    store: StateStore,
) -> list[str]:
    """Run the update pipeline, stopping at the first failed gate."""
    git.ensure_repository()
    git.ensure_clean()
    lines: list[str] = []
    if dry_run:
        lines.append("git: would pull --ff-only")
    else:
        git.pull_ff_only()
        lines.append("git: pulled with --ff-only")

    errors = repository.validate_skills()
    if errors:
        raise SkobalError(
            "skill validation failed after pull: " + "; ".join(errors)
        )
    lines.append(
        f"validation: passed for {len(repository.skill_directories())} skills"
    )

    if dry_run:
        current = (
            repository.registry_path.read_text(encoding="utf-8")
            if repository.registry_path.exists()
            else None
        )
        planned = repository.registry_text()
        action = "unchanged" if current == planned else "would regenerate"
        lines.append(f"registry: {action}")
    else:
        repository.write_registry()
        lines.append("registry: regenerated")

    sync_lines = sync_profile(
        repository,
        profile_name,
        target_name=None,
        copy=False,
        dry_run=dry_run,
        prune=False,
        force=False,
        store=store,
    )
    lines.extend(sync_lines)
    lines.append(
        f"update: {'dry-run complete' if dry_run else 'complete'} "
        f"for profile {profile_name}"
    )
    return lines
