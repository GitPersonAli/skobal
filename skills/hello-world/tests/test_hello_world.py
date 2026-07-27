from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parents[1]


def test_greet_script_output() -> None:
    result = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts" / "greet.py"), "--name", "Ada"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        result.stdout.strip()
        == "Hello, Ada! This greeting comes from the hello-world skill."
    )


def test_skill_frontmatter_is_valid() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, _ = text.split("---", maxsplit=2)
    metadata = yaml.safe_load(frontmatter)

    assert metadata == {
        "name": "hello-world",
        "description": (
            "Greet a person with the bundled deterministic script when testing "
            "skill discovery or script execution."
        ),
    }
