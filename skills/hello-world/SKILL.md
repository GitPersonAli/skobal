---
name: hello-world
description: Greet a person with the bundled deterministic script when testing skill discovery or script execution.
---
# Hello world

Use this skill to verify that an agent can discover a skill and run a bundled
resource.

## Run the greeting

Execute:

```bash
python3 scripts/greet.py --name "Ada"
```

Run the command from this skill directory. Replace `Ada` with the requested
name. Return the script output exactly unless the user asks for additional
context.

If no name is supplied, omit `--name`; the script greets `World`.
