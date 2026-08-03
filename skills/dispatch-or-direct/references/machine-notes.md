# Machine notes (non-portable lore)

Recorded incidents and pinned paths from specific machines. Verify before
relying on them elsewhere; the portable rules live in SKILL.md.

## innovina workstation (recorded 2026-07-13, updated 2026-08-03)

- `codex` is a logging wrapper at `~/.local/bin/codex` → real npm CLI under
  `~/.nvm/versions/node/*/bin/codex` (0.145.0 as of 2026-08-03). The VS Code
  extension bundles an alpha build — fallback only, upgrade the npm CLI first.
- Companion runtime: resolve newest with
  `ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | sort -V | tail -1`.
  Broker pid lives in `.claude/plugins/data/codex-openai-codex/state/*/broker.json`.
- Plain `node` can be shadowed by the nvm wrapper; `/usr/bin/node` works when
  the wrapper misbehaves.

## Incident log

2026-07-13 — 5 dispatches (~185k tokens) burned on a 10-minute environment
bug. Failure modes observed:

- `unknown variant 'priority'` → old CLI parsing `service_tier = "priority"`
  in `~/.codex/config.toml`; newer CLI accepts it.
- `model requires a newer version of Codex` → extension-bundled alpha binary;
  upgrade the npm CLI, the wrapper prefers it.
- Same error repeating after the fix → **stale companion broker daemon** still
  serving queued jobs with the old binary; kill it, it respawns fresh.
