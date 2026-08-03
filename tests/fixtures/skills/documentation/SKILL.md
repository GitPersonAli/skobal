---
name: documentation
description: Write and maintain accurate project documentation after code, workflow, or architecture changes.
---
# Project documentation

Keep documentation useful, current, and grounded in the repository.

## Workflow

1. Read the request and identify its intended audience.
2. Inspect the relevant code, configuration, tests, and existing docs.
3. Locate the canonical document instead of creating a competing one.
4. List the user-visible behavior, setup steps, constraints, and failure modes.
5. Draft the smallest update that makes the documented workflow complete.
6. Verify every command, path, option, and example against the current tree.
7. Run documented commands when they are safe and practical.
8. Review links, headings, terminology, and examples for consistency.

## Writing rules

- Lead with what the reader can accomplish.
- Prefer concrete commands and examples over abstract descriptions.
- State prerequisites before the steps that depend on them.
- Use the repository's established vocabulary and formatting.
- Explain why only when it helps readers make a decision.
- Keep examples copyable; use placeholders only for values users must supply.
- Mark limitations explicitly and describe a workable alternative when one exists.
- Remove obsolete instructions made incorrect by the change.
- Do not claim support that is absent from code or tests.

## Maintenance checks

- Update navigation or indexes when adding or moving a document.
- Update configuration and environment-variable references together.
- Check relative links from the file that contains them.
- Preserve deliberate historical records such as ADRs; supersede them explicitly.
- Avoid duplicating details that already have a canonical source.

## Completion

Summarize which documents changed, what behavior they now describe, and which
commands or repository evidence were used to verify accuracy.
