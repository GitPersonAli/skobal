# Report protocol — `.codex-reports/`

Communication between judge and Codex agents is file-based, indexed, and durable. The judge gates on `recap.md` alone; everything deeper is reached through precise pointers, so suspicion costs one grep + one sliced read.

## Layout

```
.codex-reports/                       # gitignored; audit trail + re-entry point
  2026-08-03_add-auth/                # {YYYY-MM-DD}_{task-slug}
    plan.json                         # living plan — single source of truth
    context.md                        # frozen understand-phase output
    baseline.sha
    01_investigate-db-schema/         # {NN}_{slug}; insertions get 01a_, 01b_
      implementer/                    # role: implementer | reviewer | lane-<slug>
        prompt.md                     # exact spawn prompt, judge-written, frozen
        recap.md                      # THE contract file (template below)
        qa.md                         # interrogation log, append-only
        details/                      # Codex long-form analyses, anchored headings
        raw/                          # verbatim logs/diffs, append-only, never edited
          step.diff                   # frozen git diff of the step
    02_write-migration/
```

## plan.json

```json
{
  "task": "add-auth",
  "steps": [
    {"id": "01_investigate-db-schema", "tier": "S", "status": "done",
     "accept": "root cause named with mechanism + evidence pointer",
     "attempts": 1, "recap": "01_investigate-db-schema/implementer/recap.md"},
    {"id": "02_write-migration", "tier": "L", "status": "active",
     "accept": "migration applies clean; pnpm test db 14/14", "attempts": 0}
  ]
}
```

`status`: `pending|active|done|failed|dropped`. Re-evaluate the whole list after every gate; inserting/splitting/reordering is normal operation, not an exception.

A parallel step adds a `lanes` list; each lane mirrors a step entry (allowlist, accept, attempts, status) and reports into its own `lane-<slug>/` dir:

```json
{"id": "04_port-adapters", "tier": "L", "status": "active",
 "lanes": [
   {"id": "a-claude",  "paths": ["adapters/claude.py"],  "status": "active", "attempts": 0},
   {"id": "b-cursor",  "paths": ["adapters/cursor.py"],  "status": "done",   "attempts": 1}
 ],
 "accept": "all lanes gated, merged in order, step verification green"}
```

## recap.md template (Codex fills; judge pre-creates the stub)

```markdown
---
step: 01_investigate-db-schema
agent: implementer
status: done            # done|failed|blocked
files_touched: [src/db/pool.ts]
artifacts: [raw/test-run.log, raw/step.diff, details/root-cause.md]
---
## TL;DR
<=3 lines.

## Findings
Each bullet = one claim -> pointer:
- Conn leak in retry path exhausts pool -> details/root-cause.md#leak, raw/test-run.log:L45

## Verification
Exact command + observed result:
- `pnpm test db` -> 14/14 pass -> raw/test-run.log:L102

## Assumptions & deviations
Hypotheses labeled as such; anything done beyond/instead of prompt.md.

## Handoff
What the next step must know.
```

Hard rules: recap ≤ 60 lines (overflow → `details/` + pointer); pointer format is exactly `path:Lnn` or `path#anchor`; unverified claims labeled hypothesis; reviewer recaps order findings by severity.

## qa.md entry format

```markdown
## Q3 (job j-abc123)
Q: prompt.md says preserve retry semantics; recap shows retry loop deleted — reconcile.
A: <verbatim Codex answer>
-> judge: accepted | recap amended | redo ordered
```

## Gate checklist (run in order, stop at first failure)

1. Frontmatter parses; `status` is `done`; recap ≤ 60 lines; every finding has a valid pointer. Noncompliant → `task --resume-last "rewrite recap per report contract"` (does not count as an attempt).
2. `files_touched` matches `git diff --name-only` since checkpoint; diff within the step's path allowlist.
3. Rerun the recap's Verification command yourself; result must match the claim.
4. Masking grep (see runtime.md) on fix steps.
5. Acceptance criterion from plan.json met, judged against evidence, not the TL;DR.
6. Anything ambiguous → interrogation (read-only) before any deep read; `result --json` is the dispute fallback when a recap smells cooked, not a routine read.

Answer changed the conclusions → order a recap amendment; qa.md is history, recap stays the single truth.
