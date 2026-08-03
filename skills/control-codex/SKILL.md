---
name: control-codex
description: "Use when the user wants a coding task executed by OpenAI Codex agents while Claude only orchestrates and judges — delegating implementation, debugging, or investigation to Codex (gpt-5.6-sol) through the openai-codex plugin runtime to keep main-loop token usage minimal. Triggers include 'use codex for this', 'delegate to codex', 'control codex', 'you judge, codex works', and offloading implementation while staying suspicious of results."
---

# control-codex

Claude = suspicious judge. Codex = the only implementer. Judge tokens are spent on understanding, contracts, gates, and interrogation — never on writing repo content.

**Violating the letter of the role split is violating its spirit.** If you caught yourself editing source files, you already failed this skill.

## Hard rules

1. **Never implement.** Judge's hands touch only: report/state files under `.codex-reports/`, git safety ops (branch, checkpoint commit, rollback), verification commands, and prompts. Every line of repo content comes from Codex.
2. **Never proceed on ambiguity.** Unclear task → AskUserQuestion until you can state the goal, constraints, and "done" test in your own words. Unclear Codex result → interrogate the thread, don't guess and don't dive into raw logs first.
3. **A failed or incomplete Codex run is never converted into a Claude-side implementation.** Report and decide (retry / re-plan / escalate to user).
4. **Dispatch only through the companion runtime** (`codex-companion.mjs task|adversarial-review|status|result`). Raw `codex exec` loses job tracking and thread resume. Resolve the script path per [references/runtime.md](references/runtime.md) — never invent flags; the cheatsheet is authoritative.
5. **Serialize Codex agents.** `--resume-last` reaches only the newest thread; finish interrogating one agent before spawning the next.
6. **Checkpoint or it didn't happen.** Git commit after every accepted step; rollback to the checkpoint before retrying a failed approach.

## Pipeline

1. **Understand** — restate task; AskUserQuestion for every gap; freeze result in `context.md`. Optionally seed the Codex thread with full session context via `/codex:transfer`.
2. **Plan** — decompose into steps with acceptance criteria and tier (S/L/XL) in `plan.json`. The plan is a living file: re-evaluate after every gate — insert, split, reorder, drop steps freely.
3. **Per step, loop:**
   - Write `prompt.md` from the contract blocks in [references/prompt-contracts.md](references/prompt-contracts.md) (always includes the report contract).
   - Dispatch `task --background`, poll `status --json` cheaply.
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
