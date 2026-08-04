# Prompt contracts

Spawn prompts are assembled from the openai-codex plugin's XML block system (`codex:gpt-5-4-prompting` skill — reuse its blocks; this file only adds the codex-control-specific ones). Operator style: one task per run, state what done looks like, tighten contracts before raising effort.

## Spawn prompt skeleton (implementer step)

```xml
<task>
Step {NN}_{slug} of task {task}. {concrete job + repo context + expected end state}
Acceptance: {criterion from plan.json, verbatim}
You may modify only: {path allowlist}
</task>

<report_contract>
Write your report to .codex-reports/{task}/{NN}_{slug}/implementer/ :
- recap.md — fill the pre-created stub exactly; <=60 lines; every finding carries a
  pointer of the form path:Lnn or path#anchor into details/ or raw/.
- details/*.md for long-form analysis (anchored headings), raw/ for verbatim command
  logs and raw/step.diff (git diff of your changes). raw/ is append-only.
- Unverified claims must be labeled hypothesis. recap.md is the only file the judge
  reads by default — write it for that.
</report_contract>

<integrity_contract>
End in one of two states: all changes committed-or-clean as instructed, or fully
reverted; never leave a dirty half-done tree. Do not push. Do not touch files outside
the allowlist. Flag any new dependency in the recap.
</integrity_contract>

<completeness_contract>Resolve fully; don't stop at the first plausible answer; check follow-on fixes and edge cases.</completeness_contract>
<verification_loop>Before finalizing, verify against the acceptance criterion and record the exact command + result in recap.md.</verification_loop>
<default_follow_through_policy>Default to the reasonable low-risk interpretation; stop only when a missing detail changes correctness or safety, and record the question in recap.md Assumptions.</default_follow_through_policy>
<action_safety>Tightly scoped; no unrelated refactors.</action_safety>
```

Diagnosis-only steps: drop `--write`, drop `integrity_contract`, add `grounding_rules` + `missing_context_gating` from the plugin blocks.

## Interrogation (read-only, `task --resume-last`, no `--write`)

```xml
<task>
Question about your last step, referencing your prompt.md and recap.md.
{pointed question(s) — e.g. "recap Findings #2 claims X; prompt.md required Y; reconcile."}
</task>
<answer_contract>
Answer only — do not modify any files. <=15 lines. If you realize something was wrong,
say so and propose the correction; do not apply it until instructed.
</answer_contract>
```

Redo after a confession is a separate dispatch (judge first decides: patch in place / rollback / fresh thread).

## Delta-retry (`task --resume-last --write`)

```xml
<task>
Step {NN} rejected. Observed: {evidence — verify cmd output, diff facts}.
Rejected because: {1-3 bullets}. New direction: {Y}.
Update recap.md and raw/step.diff when done; same report contract applies.
</task>
```

Send only the delta. Never restate the full original task on a resumed thread.

## Swarm block (XL tier only)

```xml
<swarm_block>
This step is large. Decompose it and dispatch your own registered agents where useful;
you own their coordination and results. The judge sees only this thread: return ONE
unified recap.md covering the whole step, with per-part evidence in details/ and raw/.
</swarm_block>
```

## Merger spawn (parallel steps, `task --write` in the main task-branch checkout)

```xml
<task>
Finalize step {NN}_{slug} of task {task}. {N} parallel lanes completed their parts on
lane branches: {codex/<task>/NN-a: <scope>, codex/<task>/NN-b: <scope>, ...}.
Their reports are in .codex-reports/{task}/{NN}_{slug}/agents/lane-*/.
Step acceptance: {criterion from plan.json, verbatim}
</task>

<merge_contract>
1. Read every lane recap (and details/raw where a claim needs checking).
2. Merge the lane branches into this branch in the order given above; resolve any
   conflicts yourself.
3. Fix cross-lane inconsistencies (naming, duplicated helpers, divergent patterns)
   so the merged result reads as one coherent change meeting the acceptance criterion.
4. Run the step-level verification and record the exact command + result.
5. Write the final step recap to .codex-reports/{task}/{NN}_{slug}/merger/recap.md —
   standard recap contract, plus one disposition line per lane:
   lane-<slug>: accepted | amended | reworked -> pointer to what changed and why.
6. If the lanes are irreconcilable, stop: status blocked in the recap, with the
   conflicting claims quoted — do not force a merge that fakes coherence.
</merge_contract>

<integrity_contract>
End committed-or-clean on this branch; lane branches must be left untouched apart
from being merged. Do not push.
</integrity_contract>
```

## Fresh-thread respawn (after rollback)

Include: the frozen `context.md` summary (or note that the thread was seeded via `/codex:transfer`), what approach was tried, 1–3 bullets why it was rejected, and the standard spawn skeleton. A fresh thread knows nothing — the poisoned history is the thing you are escaping, so do not resume it.
