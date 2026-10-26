#!/usr/bin/env python3
"""Check that the repository's documentation matches its own tree.

What it verifies:

- every markdown link and image target resolves (inline code and fenced blocks are skipped, because
  they hold syntax examples rather than links)
- SKILL.md's reference map names every reference and every script that exists
- the counted claims in the docs match the tree (seven scripts, four eval prompts)
- no stale phrases survive a rename or a scoring change
- every committed SVG has a committed .mmd source next to it or under diagrams/
- plugin.json and marketplace.json agree on the version

Run from anywhere: python scripts/check_docs.py
Exit code 0 means the documentation is internally consistent; it does not prove the prose is true.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "obsidian-kglite"
STALE = [
    "三条测试提示",
    "影响最大的五处",
    "77/100",
    '"version": "1.0.0"',
    "one of two things",
]


def strip_examples(text: str) -> str:
    """Drop fenced blocks and inline code spans: they contain markdown syntax examples."""
    kept, inside = [], False
    for line in text.splitlines():
        if line.lstrip().startswith(("\x60\x60\x60", "~~~")):
            inside = not inside
            kept.append("")
            continue
        kept.append("" if inside else line)
    return re.sub(r"\x60[^\x60]*\x60", "", "\n".join(kept))


def main() -> int:
    problems: list[str] = []
    notes: list[str] = []

    mds = [p for p in REPO.rglob("*.md") if ".git" not in p.parts]
    for path in mds:
        text = strip_examples(path.read_text(encoding="utf-8"))
        for match in re.finditer(r"!?\[[^\]]*\]\(([^)\s]+)\)", text):
            target = match.group(1).split("#")[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if target in {"url", "…"}:
                continue
            if not (path.parent / target).exists():
                problems.append(f"{path.relative_to(REPO)}: broken link {target}")

    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for reference in sorted((SKILL / "references").glob("*.md")):
        if f"references/{reference.name}" not in skill_md:
            problems.append(f"SKILL.md reference map omits {reference.name}")
    for script_path in sorted((SKILL / "scripts").glob("*.py")):
        if f"scripts/{script_path.name}" not in skill_md:
            problems.append(f"SKILL.md reference map omits {script_path.name}")

    scripts = sorted((SKILL / "scripts").glob("*.py"))
    references = sorted((SKILL / "references").glob("*.md"))
    evals = json.loads((SKILL / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]
    notes.append(f"scripts={len(scripts)} references={len(references)} evals={len(evals)}")
    if len(scripts) != 7:
        problems.append(f"expected 7 scripts, found {len(scripts)}")
    if len(references) != 9:
        problems.append(f"expected 9 references, found {len(references)}")
    if len(evals) != 4:
        problems.append(f"expected 4 eval prompts, found {len(evals)}")
    readme_zh = (REPO / "README.md").read_text(encoding="utf-8")
    if "七个脚本" not in readme_zh:
        problems.append("README.md no longer states seven scripts")
    if "四条测试提示" not in readme_zh:
        problems.append("README.md does not state four eval prompts")

    for phrase in STALE:
        candidates = mds + [REPO / ".claude-plugin" / "plugin.json", REPO / ".claude-plugin" / "marketplace.json"]
        for path in candidates:
            if phrase in path.read_text(encoding="utf-8"):
                problems.append(f"{path.relative_to(REPO)}: stale phrase {phrase!r}")

    for svg in sorted(REPO.rglob("*.svg")):
        candidates = [svg.with_suffix(".mmd"), svg.parent / "diagrams" / (svg.stem + ".mmd")]
        if not any(candidate.exists() for candidate in candidates):
            problems.append(f"{svg.relative_to(REPO)}: no .mmd source")
        else:
            notes.append(f"{svg.relative_to(REPO)} <- {next(c.name for c in candidates if c.exists())}")

    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    if plugin["version"] != market["plugins"][0]["version"]:
        problems.append(f"plugin version {plugin['version']} != marketplace {market['plugins'][0]['version']}")

    print("\n".join(notes))
    if problems:
        print("PROBLEMS:")
        for problem in problems:
            print(" -", problem)
        return 1
    print("all checks ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
