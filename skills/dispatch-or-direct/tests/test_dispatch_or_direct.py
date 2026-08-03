from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parents[1]


def test_frontmatter_matches_directory() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, _ = text.split("---", maxsplit=2)
    metadata = yaml.safe_load(frontmatter)

    assert metadata["name"] == "dispatch-or-direct"
    assert metadata["description"].startswith("Use when")


def test_core_rules_present() -> None:
    body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "Max 2 startup failures" in body
    assert "codex-control" in body, "dispatch branch must route to codex-control"
    assert "references/machine-notes.md" in body
    assert (SKILL_DIR / "references" / "machine-notes.md").is_file()
