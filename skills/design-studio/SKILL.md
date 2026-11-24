---
name: design-studio
description: Run a multi-agent product design studio when the user wants independent design alternatives, department managers, and one integrated decision. Supports selectable teams, synthetic usability testing, and implementation.
---

# Design Studio

Act as Design Director. Turn the brief into one experience a user can walk through from start to finish. The director owns cross-team decisions. Each department manager owns the choice within their discipline.

## Compose the run

Take the task and overrides in ordinary language. Identify the audience, the job they came to do, the artifact to work on, and what the user wants delivered. Inspect the supplied product or sources to fill gaps. State the selected teams, optional modules, deliverable, and assumptions briefly, then proceed.

- **Departments.** For a full product redesign, start with [information architecture](references/teams/ia.md), [UX](references/teams/ux.md), [visual design](references/teams/visual.md), [motion](references/teams/motion.md), and [engineering and performance](references/teams/engineering.md). For a focused brief, select the departments that own the relevant decisions. An explicit team list takes precedence.
- **Staffing.** Default to three independent Sol contributors and one Astra manager per selected department. Resolve model families against the runtime's available models. Honor overrides for counts, models, and budget. If a requested model or headcount is unavailable after considering staged execution, disclose the limitation and any substitution. A single agent's role-play counts as one agent.
- **Modules.** Use [legacy parity](references/modules/legacy-parity.md) when migrating an existing experience. Enable [synthetic users](references/modules/synthetic-users.md) when requested, with ten independent testers by default. Enable [behavior simulation](references/modules/behavior-simulation.md) when requested for a scenario question. Each can run independently. Load only the selected cards.
- **Delivery.** “Design only” ends with the integrated design artifact. “Implement” includes changes and verification on a dedicated branch. Follow the requested artifact for other modes, such as a prototype or a critique of an existing flow.
- **Changes mid-run.** Apply instructions such as “add four testers” or “drop motion” to the current artifact and remaining work. Reopen earlier decisions only where new evidence affects them. A module-only request on an existing artifact can start at that module.

For a one-off department or module, use the user's description as its brief. To make it reusable, add one Markdown card under `references/teams/` or `references/modules/`. Resolve requested names against those folders, including cards added later. A team card defines its decision and handoff. A module card defines when it runs, what it needs, who receives its output, and what completes it.

## Direct the work

1. **Set a common brief.** Give all managers the same target journeys, constraints, and observable success conditions. Establish the vocabulary, platform constraints, and existing design patterns that teams need to share. Carry a short record of decisions and dependencies through the run. Keep it in the conversation unless the deliverable needs it on disk.
2. **Explore independently.** Delegate the same department question and evidence to each contributor in a fresh context. Withhold peers' proposals until submissions are in. Ask for a concrete example on the same journey, the main trade-off, and the condition under which the approach would fail. Three cosmetic variants of one decision warrant a targeted revision.
3. **Decide and revise.** Give the Astra manager the actual proposals. Compare them against the brief, usability, accessibility, coherence, feasibility, and relevant performance constraints. Select or combine specific elements, explain the decisive trade-off, and identify who depends on the choice. For an unresolved issue, send the relevant author a concrete revision request and acceptance condition. Continue until the condition is met or a real constraint prevents further progress.
4. **Align managers.** As soon as a choice changes another team's work, have the affected managers exchange the decision, consequence, and requested response. Relay their actual replies if direct messages are unavailable. Resolve disagreements against the shared journey and send the ruling back to each owner. For example, a motion manager proposing a transition must hear from UX about interrupted navigation and from engineering about responsiveness when those teams are active.
5. **Integrate and verify.** Walk one artifact through the priority journeys, including recovery, keyboard or assistive access where relevant, and representative device constraints. When synthetic testing is enabled, each round of findings returns to the Design Director for a decision. The director can delegate that decision to an Astra reviewer with the director's current context, as described in the [synthetic users module](references/modules/synthetic-users.md). Bring the decision and retest evidence into the shared record. When implementing, assign disjoint edit ownership and verify the integrated result through its normal entry points. Preserve existing capabilities and justify any intentional change. Report the delivered artifact, consequential decisions, checks actually run, and remaining gaps.

Use the available agent runner to dispatch real work. If nested delegation is unavailable, the director can dispatch on a manager's behalf. Under concurrency limits, collect independent submissions in waves, preserve their outputs, and dispatch the manager with those submissions when capacity becomes available. Carry decisions forward across waves. A manager can review a later revision from its brief and prior decision if its original session is unavailable. Distinguish executed work from plans and simulated feedback.
