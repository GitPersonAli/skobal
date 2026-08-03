---
name: dispatch-or-direct
description: "Use when considering handing work to Codex or another external agent instead of doing it directly, when the user asks whether offloading is worth it, when a dispatch fails or hangs at startup, or before re-dispatching a task that already failed once."
---

# Dispatch or Direct

Decide whether to hand work to an external executor (Codex) or do it directly. Core rule: **estimate hand-off + monitoring + review; dispatch only if that total is smaller than the work itself.**

## Announce before acting

Give the user one short block before committing either way:

```
Offload estimate — dispatch: ~<hand-off + monitoring + review> tokens on me, work burns Codex tokens.
Direct: ~<my implementation + verification> tokens. Recommendation: <dispatch|direct> because <one line>.
```

Close call or user preference unknown → ask (dispatch / direct). Obvious branch → state it and proceed. Dispatch branch → execute through the codex-control skill (full orchestration protocol); this skill only decides and preflights.

## Decision table

| Signal | Do |
|---|---|
| Files already in your context, fixes small and specified | **Direct** — hand-off costs more than the edits |
| Big implementation from a short spec (hours of writing, one page of instructions) | Dispatch |
| Unfamiliar codebase/subsystem you'd have to read first | Dispatch — the executor burns its own tokens reading |
| Several independent tasks (parallel lanes) | Dispatch one job per lane |
| Your context near capacity; implementation churn would force compaction | Dispatch — context protection beats token math |
| Task needs clarification round-trips | Direct — each round-trip re-pays hand-off cost |
| Verification dominates the cost | Direct — verification stays with you either way |
| Pipeline never proven this session | Preflight first (below), or direct |
| Want a second opinion / cross-model review | Dispatch review, implement directly (or reverse) |

## Retry cap (hard rule)

A dispatch that fails at **startup** (0–10s, no model turn) is an environment problem, not a task problem.

- **Max 2 startup failures per task.** After the 2nd: STOP dispatching. Debug the environment directly from your shell, or do the task directly.
- Re-dispatching "because I fixed the cause" does not reset the count.
- Long-lived daemons can hold stale state: your shell verifying clean ≠ the dispatch path being clean.
- Startup failures never count as task attempts in codex-control's failure ladder — different bug class, different fix.

## Preflight (before first dispatch of a session, or after any startup failure)

```bash
codex --version                                   # CLI resolves and runs
codex exec --help >/dev/null && echo CONFIG_OK    # ~/.codex/config.toml parses
ps aux | grep -E "codex|companion" | grep -v grep # stale companion broker daemon?
```

A stale companion broker serves ALL queued jobs with an old binary — kill it (pid in `.claude/plugins/data/codex-openai-codex/state/*/broker.json`), it respawns fresh. Machine-specific incidents and pinned paths: [references/machine-notes.md](references/machine-notes.md).

## Which direction — who orchestrates, who executes

Rule: **the model holding the user's conversation orchestrates; the other executes.** Context hand-off is the expensive, lossy part — never invert mid-session.

| Situation | Direction |
|---|---|
| Working in Claude Code | Claude orchestrates → Codex executes |
| User lives in a Codex session | Codex orchestrates → Claude executes (`claude -p "<task>"` headless) |
| Cross-model review | Whoever **implemented** must not be the sole reviewer — dispatch the review to the other model |
| Verification / final judgment | Stays with the orchestrator, always — it holds the user's intent and history |

Don't chain dispatches (A → B → A…): each hop re-pays hand-off cost and loses intent. One hop, then results come home.

## After dispatch

- Monitor with a poll that fires on **every terminal state** (completed | failed | cancelled), not just success.
- Verify the executor's diff yourself: sandboxed runs often have no network, so its "tests failed: EPERM" means *you* run type-check/tests locally before reporting done.

## Red flags

- "One more re-dispatch, I fixed it this time" (startup-failure count ≥ 2 → stop)
- Dispatching edits to files already open in context
- Trusting the executor's own verification output from a sandboxed run
- Counting only your input tokens and ignoring forwarder + monitoring + review cost
- Skipping the user announcement because "the answer is obvious" — the estimate line is one sentence; send it
