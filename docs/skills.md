# Skills catalog

Short description of every skill, then how to use each in detail. Skills are
installed by profile sync (`./skillctl sync --profile personal`) and load
automatically in the agent when their trigger conditions match — no manual
setup beyond sync.

## At a glance

| Skill | One-liner |
| --- | --- |
| [dispatch-or-direct](#dispatch-or-direct) | Decide whether to offload work to an external agent or do it directly, with a user-facing token estimate |
| [codex-control](#codex-control) | Run any task through OpenAI Codex agents while the main agent acts only as a suspicious, token-thrifty judge |
| [design-studio](#design-studio) | Select design departments and validation modules for one integrated product design |

The two delegation skills pair: dispatch-or-direct is the front door (decide + preflight);
codex-control is the machine behind the "dispatch" branch. Either can be
invoked alone; when dispatch-or-direct lands on dispatch, it invokes
codex-control automatically.

## design-studio

Give the studio a product, a user goal, and the deliverable you want. A full redesign uses five departments with three independent Sol contributors and one Astra manager each. The director coordinates decisions across teams. Select fewer departments, change staffing, or add a validation module in the same request.

> Use $design-studio to redesign the mini app around the jobs people used the PHP bot for. Check legacy parity, test the new flows with ten synthetic users, and implement the result on a dedicated branch.

> Use $design-studio for IA and UX only. Give me a design-only proposal for finding saved orders.

> Add four synthetic testers to the approved saved-orders flow. Focus on whether returning users can recover an interrupted order.

A one-off team or test can be described in the brief. To reuse it across projects, add a card beside the existing department or module cards. [Skill and extension instructions](../skills/design-studio/SKILL.md)

---

## dispatch-or-direct

**Short:** cost-benefit gate for offloading. Estimates hand-off + monitoring +
review versus doing the work directly, announces the estimate to the user,
picks the branch (asking when it's close), and preflights the Codex pipeline.

### When it triggers

- You consider handing work to Codex or another external agent
- The user asks "should we offload this?" / "is codex worth it here?"
- A dispatch fails or hangs at startup
- Before re-dispatching a task that already failed once

### What you see as a user

Before anything runs, the agent sends one short block:

```
Offload estimate — dispatch: ~3k tokens on me (hand-off + polling + review),
work burns Codex tokens. Direct: ~20k+ tokens. Recommendation: dispatch
because the executor burns its own tokens reading an unfamiliar codebase.
```

Close call → you get an explicit dispatch/direct question. Obvious call → it
states the branch and proceeds. Dispatch → codex-control takes over
automatically.

### Rules it enforces

- **2-strike startup cap:** a dispatch dying in 0–10s with no model output is
  an environment bug; after the second one the agent stops dispatching and
  debugs the environment instead of burning tokens on retries.
- **Preflight** before the first dispatch of a session: CLI resolves, config
  parses, no stale companion broker daemon.
- **Direction rule:** whoever holds the user conversation orchestrates; the
  other side executes. Never inverted mid-session, never chained A→B→A.
- **Sandbox distrust:** the executor's own "tests failed" from a sandboxed
  no-network run is not evidence; the orchestrator reruns checks locally.

Machine-specific incident notes live in
`skills/dispatch-or-direct/references/machine-notes.md`.

---

## codex-control

**Short:** the main agent becomes a judge that never does the task itself.
Codex agents (default `gpt-5.6-sol`, effort `xhigh`) execute every step;
the judge understands, contracts, gates, interrogates, and checkpoints —
spending as few of its own tokens as possible.

### Requirements

- The [openai-codex Claude Code plugin](https://github.com/openai/codex-plugin-cc)
  installed and enabled
- Codex CLI installed and authenticated (`/codex:setup` verifies)

### When it triggers

Say any of: "use codex", "delegate to codex", "codex control", "pass this to
codex", "you judge, codex works" — or arrive via dispatch-or-direct's
dispatch branch.

### How a task runs

1. **Understand** — the agent restates the task and asks about every gap
   until goal, constraints, and the "done" test are explicit; frozen into
   `.codex-reports/<task>/context.md`.
2. **Plan** — steps with acceptance criteria and a size tier (S/L/XL) in
   `plan.json`. The plan is living: steps get inserted, split, reordered, or
   dropped after every gate.
3. **Execute per step** — a Codex agent is spawned through the plugin's
   companion runtime with an XML prompt contract; a hardcoded watchdog loop
   checks it every minute at zero token cost and wakes the judge on
   completion or after ~30 minutes without progress. A step with
   independent, disjoint-file parts fans out into **parallel lanes** — one
   agent per git worktree, each with its own resumable thread — and a
   **merger Codex agent** then reconciles the lane branches, fixes
   cross-lane inconsistencies, verifies the merged result, and writes the
   final step recap; the judge reads one recap either way.
4. **Gate** — the judge reads only the agent's `recap.md` (≤60 lines,
   pointer-indexed), then verifies independently: reruns the verification
   command itself, checks the diff against the step's file allowlist, greps
   for symptom-masking "fixes". Ambiguity → a cheap follow-up question to the
   same Codex thread instead of log-diving. Rejection → delta-retry, re-plan,
   or rollback + fresh thread (3 attempts, then the user decides).
5. **Finish** — an adversarial Codex review over the whole change, then a
   summary written from recaps.

### What lands on disk

```
.codex-reports/<date>_<task>/     # gitignored audit trail + crash re-entry
  plan.json  context.md
  NN_step/implementer/{prompt.md, recap.md, qa.md, details/, raw/}
```

Work happens on a `codex/<task>` branch with a checkpoint commit per accepted
step — rollback is always one command.

### Guarantees

- The judge never writes the work product; a failed Codex run is never
  silently converted into the judge doing it.
- Nothing is trusted unverified: recaps are claims, evidence is the judge's
  own reruns.
- Startup/environment failures and stall recoveries never consume task
  attempts.
