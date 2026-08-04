from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parents[1]


def test_frontmatter_matches_directory() -> None:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, _ = text.split("---", maxsplit=2)
    metadata = yaml.safe_load(frontmatter)

    assert metadata["name"] == "codex-control"
    assert metadata["description"].startswith("Use when")


def test_reference_files_exist_and_are_linked() -> None:
    body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for ref in ("runtime.md", "report-protocol.md", "prompt-contracts.md"):
        assert (SKILL_DIR / "references" / ref).is_file(), f"missing references/{ref}"
        assert f"references/{ref}" in body, f"SKILL.md does not link references/{ref}"


def test_runtime_facts_stay_authoritative() -> None:
    runtime = (SKILL_DIR / "references" / "runtime.md").read_text(encoding="utf-8")
    # Guard verified constraints; if these change upstream, re-verify the file.
    assert "codex-companion.mjs" in runtime
    assert "--resume-last" in runtime
    assert "xhigh" in runtime
    assert "gpt-5.6-sol" in runtime
    assert "WATCHDOG: STALLED" in runtime, "watchdog stall detection missing"
    assert "Parallel lanes" in runtime, "parallel lanes section missing"
    assert "merger" in runtime, "merger agent flow missing"
