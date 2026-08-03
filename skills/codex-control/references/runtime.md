# Companion runtime — authoritative cheatsheet

All facts below were verified against openai-codex plugin 1.0.6 and codex-cli 0.145.0. Do not invent flags beyond this file; if a call fails, re-verify with `node "$COMPANION" 2>&1 | head -15` (prints usage) instead of guessing.

## Path resolution

`${CLAUDE_PLUGIN_ROOT}` is unset outside plugin commands. Resolve newest installed version:

```bash
COMPANION=$(ls -d ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs | sort -V | tail -1)
```

If empty → plugin missing; stop and tell the user to install/enable the openai-codex plugin, then run `/codex:setup`. Never fall back to raw `codex exec` (loses job tracking, thread registry, status/result store).

## Commands

```bash
node "$COMPANION" task [--background] [--write] [--resume-last|--fresh] [--model <m>] [--effort <none|low|medium|high|xhigh>] "<prompt>"
node "$COMPANION" adversarial-review [--wait|--background] [--base <ref>] [--scope auto|working-tree|branch] [focus text]
node "$COMPANION" review            [--wait|--background] [--base <ref>] [--scope ...]
node "$COMPANION" status [job-id] [--all] [--json]     # cheap poll
node "$COMPANION" result [job-id] [--json]             # stored final output — dispute fallback only
node "$COMPANION" cancel [job-id]
node "$COMPANION" transfer [--source <claude-jsonl>]   # current Claude session → resumable Codex thread
```

- Implementation steps: add `--write`. Investigation/diagnosis-only steps: omit it.
- `--background` + `status --json` polling is the default dispatch mode; `--wait` only for tiny bounded asks.
- `--resume-last` continues the **newest** thread in this repo — there is no thread-id targeting. Hence: serialize agents.
- Review commands return schema-enforced JSON (verdict `approve|needs-attention`, findings with severity/file/line/confidence, next_steps) — gate on that, not prose.

## Tiers

Effort ceiling is `xhigh` — `max`/`ultra` do not exist as effort values. "Ultra" is a skill-level tier implemented by prompt, not flag:

| Tier | When | Flags | Extra |
|---|---|---|---|
| S | mechanical/bounded step | `--effort medium` | |
| L | default hard step | `--model gpt-5.6-sol --effort xhigh` | |
| XL | huge/multi-part step | same as L | add `<swarm_block>` (see prompt-contracts.md) — Codex orchestrates its own registered `[agents.*]`; judge still sees one thread, one recap |

Reviewer runs are always ≥ L: the critic is never weaker than the implementer. Interrogation resumes: keep model/effort unset (inherit thread; mid-thread model switch is untested).

## Failure ladder (per step)

1. **Delta-retry** (default): `task --resume-last --write "<what failed, observed evidence, try Y>"` — send only the delta, never restate the whole task.
2. **Re-plan**: insert/split steps in `plan.json` (e.g. failed step 03 → 03a investigate + 03b apply), continue same thread.
3. **Rollback + fresh**: thread poisoned by a wrong approach → `git reset --hard <last-checkpoint>` (work branch only), then `task --fresh`. State in the fresh prompt what was tried and 1–3 bullets why it was rejected.
4. **Escalate**: 2 rejects on one step → raise tier (S→L→XL). 3 total attempts → stop, report blocker to user. Never implement it yourself instead.

## Checkpoints & repo safety

```bash
git switch -c codex/<task-slug>                # never work on main
git rev-parse HEAD > .codex-reports/<task>/baseline.sha
# after each ACCEPTED step (judge-authored commit is safety bookkeeping, allowed):
git add -A ':!.codex-reports' && git commit -m "step NN: <slug> [codex]"
```

Post-step invariants (all must hold before accept): `git status --porcelain` empty or committed by the step itself; diff confined to the step's declared path allowlist; no new dependency unless flagged in the recap. Masking grep on every "fix" step — a fix that hides the symptom is auto-reject:

```bash
git diff <checkpoint>.. | grep -nE '\bskip\b|xfail|\bsleep\(|retry|timeout.*=.*[0-9]'
```

`.codex-reports/` stays out of checkpoints (gitignored by default — add the entry on task start if missing).

## Session re-entry

After context loss: read `.codex-reports/<task>/plan.json` (statuses + recap paths) → read the active step's `recap.md`/`qa.md` → `status --all --json` for live jobs. Never reconstruct state from raw logs.
