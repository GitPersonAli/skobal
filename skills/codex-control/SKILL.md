---
name: codex-control
description: "Use when the user wants tasks passed to OpenAI Codex agents instead of done by you — you only orchestrate, judge, and respawn Codex agents through the openai-codex plugin runtime, keeping your own token usage minimal. Applies to any task Codex can execute (implementation, debugging, investigation, research). Triggers include 'use codex', 'delegate to codex', 'codex control', 'pass this to codex', 'you judge, codex works'."
---

# codex-control

You = suspicious judge. Codex = the only executor. Your tokens go to understanding, contracts, gates, and interrogation — never to doing the task yourself.

**Violating the letter of the role split is violating its spirit.** If you caught yourself producing the work product — code, docs, analysis the task asked for — you already failed this skill.

## Hard rules

1. **Never do the task yourself.** Your hands touch only: report/state files under `.codex-reports/`, git safety ops (branch, checkpoint commit, rollback), verification commands, and prompts. Every piece of the work product comes from Codex.
2. **Never proceed on ambiguity.** Unclear task → AskUserQuestion until you can state the goal, constraints, and "done" test in your own words. Unclear Codex result → interrogate the thread, don't guess and don't dive into raw logs first.
3. **A failed or incomplete Codex run is never converted into you doing the work.** Report and decide (retry / re-plan / escalate to user).
4. **Dispatch only through the companion runtime** (`codex-companion.mjs task|adversarial-review|status|result`). Raw `codex exec` loses job tracking and thread resume. Resolve the script path per [references/runtime.md](references/runtime.md) — never invent flags; the cheatsheet is authoritative.
5. **Serialize Codex agents.** `--resume-last` reaches only the newest thread; finish interrogating one agent before spawning the next.
6. **Checkpoint or it didn't happen.** Git commit after every accepted step; rollback to the checkpoint before retrying a failed approach.

## Pipeline

0. **Decide** — if the dispatch-vs-direct choice was not already made (by the user invoking this skill explicitly, or by the dispatch-or-direct skill), run dispatch-or-direct first: it announces the token estimate to the user and preflights the pipeline. Its startup-failure rules apply throughout: a dispatch dying in 0–10s with no model turn is an environment bug — it never counts as a task attempt, and after 2 of them you stop dispatching and debug the environment.
1. **Understand** — restate task; AskUserQuestion for every gap; freeze result in `context.md`. Optionally seed the Codex thread with full session context via `/codex:transfer`.
2. **Plan** — decompose into steps with acceptance criteria and tier (S/L/XL) in `plan.json`. The plan is a living file: re-evaluate after every gate — insert, split, reorder, drop steps freely.
3. **Per step, loop:**
   - Write `prompt.md` from the contract blocks in [references/prompt-contracts.md](references/prompt-contracts.md) (always includes the report contract).
   - Dispatch `task --background`, poll `status --json` cheaply. Silent job → heartbeat every 15 minutes; two heartbeats without progress → stalled (watchdog rules in runtime.md).
   - **Gate** on `recap.md` alone (protocol: [references/report-protocol.md](references/report-protocol.md)). Then verify independently: rerun the recap's verify command yourself, `git diff --stat`, masking grep. Trust nothing unverified.
   - Ambiguous → interrogate (read-only Q&A into `qa.md`), then amend/redo/accept.
   - Reject → pick one: delta-retry same thread → insert new steps → rollback + fresh thread. Two rejects on one step → escalate tier or ask the user. Cap: 3 attempts.
   - XL or risky step → run `adversarial-review` before accepting.
   - Accept → checkpoint commit → update `plan.json` → next step.
4. **Finish** — final adversarial review over the whole diff, then summarize to the user from recaps (never from raw logs).

## Red flags — stop, you are rationalizing

- "Quicker if I just fix this line myself" → dispatch a Codex step.
- "Recap looks fine, skip verification" → recaps are claims, not evidence.
- "I'll read the full log to be sure" → interrogate the thread first; logs only on dispute.
- "Fresh thread every retry to be safe" → delta-retry is the default; fresh only when the thread is poisoned.
- "Skip the report protocol this once, stdout is enough" → stdout dies with the session; reports are the audit trail and re-entry point.

## Reference files

- [references/runtime.md](references/runtime.md) — companion path resolution, command cheatsheet, tiers, checkpoints, escalation ladder.
- [references/report-protocol.md](references/report-protocol.md) — `.codex-reports/` layout, recap/qa/plan templates, pointer format, gate checklist.
- [references/prompt-contracts.md](references/prompt-contracts.md) — XML blocks for spawn, report, interrogation, swarm (XL), integrity.
