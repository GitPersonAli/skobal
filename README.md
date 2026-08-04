# Skobal

[![CI](https://github.com/GitPersonAli/skobal/actions/workflows/ci.yml/badge.svg)](https://github.com/GitPersonAli/skobal/actions/workflows/ci.yml)

Local-first, Git-backed catalog of portable AI-agent skills. Profiles select
skill sets; filesystem adapters install them for Claude, Cursor, and OpenCode.
No server, no account, no marketplace.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/GitPersonAli/skobal/main/install.sh | bash
```

Installs to `~/.skobal` and syncs the `personal` profile. **Updating is the
same command** — rerunning it fast-forwards, validates, and re-syncs. Direct
form: `~/.skobal/skillctl update --profile personal`.

Options go before `bash`, not before `curl`:

```bash
curl -fsSL https://raw.githubusercontent.com/GitPersonAli/skobal/main/install.sh \
  | SKOBAL_PROFILE=work SKOBAL_DIR=~/dev/skobal bash
```

Manual install (any path):

```bash
git clone https://github.com/GitPersonAli/skobal.git skobal
cd skobal && python3 -m pip install PyYAML && ./skillctl sync --profile personal
```

Requires Git and Python 3.10+. On Windows use `python skillctl ...`; if
symlinks are denied, add `--copy`.

## Skills

| Skill | What it does |
| --- | --- |
| `dispatch-or-direct` | Decide whether to offload work to an external agent or do it directly — announces a token estimate, preflights the pipeline, caps startup-failure retries |
| `codex-control` | Run any task through OpenAI Codex agents while the main agent acts only as a suspicious judge — plans, gates, interrogates, checkpoints; never does the work itself |

They pair: dispatch-or-direct decides, and its dispatch branch hands over to
codex-control automatically. Short + detailed usage per skill:
[docs/skills.md](docs/skills.md).

## Daily commands

| Command | Does |
| --- | --- |
| `./skillctl list` | List repository skills |
| `./skillctl new <name>` | Scaffold a skill |
| `./skillctl validate` | Validate skills and registry |
| `./skillctl registry` | Regenerate `registry.yaml` (never edit by hand) |
| `./skillctl sync --profile <p>` | Install a profile's skills (symlinks; `--copy`, `--prune`, `--force`, `--dry-run`) |
| `./skillctl status --profile <p>` | Read-only drift report (`--json` for scripts) |
| `./skillctl update --profile <p>` | Safe pull + validate + registry + sync |
| `./skillctl test [skill]` | Run skill-local pytest suites |
| `./skillctl doctor` | Check Python, state, and adapter destinations |

## Add a skill

```bash
./skillctl new my-skill        # edit skills/my-skill/SKILL.md + skill.yaml
./skillctl validate my-skill && ./skillctl registry
# add "my-skill" to profiles/<profile>.yaml, then:
./skillctl sync --profile personal
git add skills/my-skill profiles registry.yaml && git commit && git push
```

A skill is a directory with `SKILL.md` (frontmatter: `name` + trigger
`description`) and a `skill.yaml`:

```yaml
schema_version: 1
name: my-skill
version: 0.1.0
description: One-line purpose.
targets: [claude]
```

A profile picks targets and skills:

```yaml
name: personal
targets: [claude]
skills: [codex-control, dispatch-or-direct]
```

Symlink mode is the default, so repository edits are live immediately;
`--copy` makes independent copies.

## Safety model

- Nothing unmanaged is silently overwritten; `--force` backs up to
  `.skobal-backups/` first and prints the path.
- Installs are atomic transactions with rollback; state lives in a central
  manifest outside the repo.
- `update` only ever fast-forwards; dirty trees and failed pulls stop it.
- `status` exits non-zero on any drift — safe for scripts and CI.

Full details — architecture, schema rules, collision handling, atomicity,
recovery, Windows notes: [docs/reference.md](docs/reference.md).

## Development

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q && python3 -m ruff check . && ./skillctl validate
```

CI runs Linux, macOS, and Windows on Python 3.10 and 3.12.
