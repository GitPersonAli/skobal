# Skobal

[![CI](https://github.com/YOUR_USERNAME/skobal/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/skobal/actions/workflows/ci.yml)

Skobal is a local-first, Git-backed catalog of portable AI-agent skills.
Profiles select skill sets, and filesystem adapters install them for Claude,
Cursor, and OpenCode. There is no server, account, database, or marketplace.

## Installation

Skobal requires Python 3.10 or newer and PyYAML:

```bash
git clone <your-skobal-repository-url> skobal
cd skobal
python3 -m pip install PyYAML
./skillctl validate
```

The executable remains the entry point for every command:

```bash
./skillctl list
./skillctl sync --profile personal --dry-run
```

On Windows, use `python skillctl ...` if the shell does not execute extensionless
scripts directly.

## Architecture

```text
skills/* + skill.yaml ---> skillctl <--- profiles/*.yaml
                            |
                validate / registry / status
                            |
                    atomic sync/update
                            |
              Claude / Cursor / OpenCode
                            |
          central managed-install state manifest
```

The thin `skillctl` entry point delegates to small modules in `skobal/`.
Adapter-specific destination and filesystem preparation behavior stays under
`adapters/`. `registry.yaml` is generated and must not be edited by hand.

## Skill metadata schema

Each real skill contains `SKILL.md` plus a `skill.yaml` using schema version 1:

```yaml
schema_version: 1
name: documentation
version: 0.1.0
description: Write and maintain accurate project documentation.
targets: [claude, cursor]
tags: [documentation]
requires: []
```

`schema_version` must be exactly `1`; unknown versions are rejected. `name` uses
lowercase-hyphen form and must match the directory. `version` follows SemVer.
`description` is non-empty, and `targets` is a non-empty list containing only
installed adapter names. `tags` and `requires` are optional string lists.
Duplicate skill names are rejected.

`SKILL.md` frontmatter remains portable and contains only `name` and a
trigger-oriented `description`. Run:

```bash
./skillctl validate
./skillctl registry
```

Registry entries are sorted and include `name`, `version`, `schema_version`,
repository-relative `path`, and `targets` (plus description and tags).

## Profiles and synchronization

A profile selects targets and skills:

```yaml
name: personal
targets: [claude]
skills: [documentation, hello-world]
```

Synchronize it with:

```bash
./skillctl sync --profile personal --dry-run
./skillctl sync --profile personal
./skillctl sync --profile work --target cursor
./skillctl sync --profile personal --copy
./skillctl sync --profile personal --prune
```

Symlink mode is the default: repository edits become visible immediately.
`--copy` creates independent, complete directory copies. Prune only considers
exact records in Skobal's central state manifest; an unmanaged path, a changed
managed copy, a wrong-source symlink, or a missing/corrupt manifest is never
deleted.

Default destinations and test/automation overrides are:

| Target | Default destination | Override |
| --- | --- | --- |
| Claude | `~/.claude/skills` | `SKOBAL_CLAUDE_DIR` |
| Cursor | `~/.cursor/skills` | `SKOBAL_CURSOR_DIR` |
| OpenCode | `~/.config/opencode/skills` | `SKOBAL_OPENCODE_DIR` |

The managed state defaults to the platform data directory
(`~/.local/share/skobal/installs.yaml` on Linux, the XDG data directory when
configured, and local application data on Windows). Set `SKOBAL_STATE_DIR` to
isolate it. State writes use a same-directory temporary file and `os.replace`;
records are deterministically sorted. Symlink installs are always recorded.

### Collisions and `--force`

Sync classifies each destination before changing it:

- an absent path is installed;
- an intact Skobal-managed path is skipped or safely updated;
- an unmanaged existing path is a conflict;
- a dangling symlink or wrong-source managed install is a conflict.

Nothing unmanaged is silently overwritten. If an unmanaged collision is known
and intentional, use:

```bash
./skillctl sync --profile personal --force
```

Skobal first moves the existing path under the destination's timestamped
`.skobal-backups/<timestamp>/<target>/<skill>/` directory, installs the skill,
and prints the exact backup path. `--force` does not override dangling
symlinks, wrong-source records, or modified managed copies; resolve those
explicitly.

### Atomicity and recovery

Each install is its own transaction: validate the source, prepare and verify a
complete same-filesystem temporary install, move the previous managed install
aside, atomically replace the destination, then atomically update state.
Failures remove temporary data and restore the previous destination whenever
possible. Copy mode never exposes a partially copied final directory.

After a normal reported failure, rerun `status`, correct the reported source,
permission, or collision problem, then retry sync. If both the operation and
rollback fail, the error prints the recovery path; preserve it, move it back to
the printed destination manually, and verify before retrying. Never delete a
backup until its contents have been reviewed.

## Status

Status is read-only and exits zero only when every selected entry is synced:

```bash
./skillctl status --profile personal
./skillctl status --profile work --target cursor
./skillctl status --profile personal --json
```

The deterministic human table and JSON output use these states: `synced`,
`missing`, `modified`, `outdated`, `unmanaged-conflict`, `wrong-source`,
`dangling-symlink`, and `unsupported`. JSON is suitable for scripts and CI.

## Safe repository update

`update` composes the safe maintenance pipeline:

```bash
./skillctl update --profile personal --dry-run
./skillctl update --profile personal
```

It confirms the checkout is a Git repository, refuses a dirty working tree,
runs only `git pull --ff-only`, validates skills, regenerates the registry, and
syncs the selected profile. It never resets, force-pulls, rebases, resolves
conflicts, or discards local changes. A failed fast-forward pull stops
immediately; validation failure prevents registry and sync changes. Dry-run
still checks repository cleanliness but performs no pull or filesystem writes.

## Windows behavior

All Python filesystem code uses `pathlib`, platform temporary directories, and
same-filesystem `os.replace` operations. CI covers Windows, macOS, and Linux on
Python 3.10 and 3.12.

Creating symlinks on Windows can require Developer Mode or an appropriately
privileged process. If symlink creation is denied, Skobal reports the operating
system error and suggests the supported fallback:

```powershell
python skillctl sync --profile personal --copy
```

Copy mode has the same collision, state, rollback, prune, and status
protections.

## Development

Install the project and development tools:

```bash
python3 -m pip install -e ".[dev]"
```

Or install the declared tools directly:

```bash
python3 -m pip install --user PyYAML pytest ruff
```

Run the repository checks:

```bash
python3 -m pytest -q
python3 -m ruff check .
./skillctl validate
./skillctl doctor
```

Tests always set `SKOBAL_CLAUDE_DIR`, `SKOBAL_CURSOR_DIR`,
`SKOBAL_OPENCODE_DIR`, and `SKOBAL_STATE_DIR` to temporary paths; tests must
never inspect or change a real home destination.

## Recommended workflow

```bash
./skillctl new review-release
# Edit skills/review-release/SKILL.md and skill.yaml, then add it to a profile.
./skillctl validate review-release
./skillctl registry
./skillctl sync --profile personal --dry-run
./skillctl sync --profile personal
./skillctl status --profile personal
./skillctl test review-release
git add skills/review-release profiles registry.yaml
git commit -m "Add review-release skill"
git push
```

Before committing, review any `.skobal-backups` path reported by a forced sync
and keep the central state directory out of the repository.
