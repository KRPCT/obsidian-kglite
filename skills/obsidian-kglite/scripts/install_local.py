#!/usr/bin/env python3
"""Copy this skill into a skills directory (default: ~/.agents/skills/obsidian-kglite).

The repo is the source of truth; a local skills directory is a deployment target. Run this after a
change instead of editing two copies.

Usage:
    python install_local.py --dry-run
    python install_local.py
    python install_local.py --target ~/.codex/skills
    python install_local.py --force        # replace an existing installed copy
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def differs(src: Path, dst: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        other = dst / rel
        if not other.is_file() or not filecmp.cmp(path, other, shallow=False):
            changed.append(str(rel))
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default=str(Path.home() / ".agents" / "skills"),
                        help="skills root (default: ~/.agents/skills)")
    parser.add_argument("--force", action="store_true", help="replace the installed copy")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.target).expanduser()
    dest = root / SKILL_DIR.name

    if not SKILL_DIR.joinpath("SKILL.md").is_file():
        sys.exit(f"not a skill directory: {SKILL_DIR}")

    if dest.exists():
        changed = differs(SKILL_DIR, dest)
        if not changed:
            print(f"up to date: {dest}")
            return 0
        print(f"{len(changed)} file(s) differ in {dest}")
        for rel in changed[:20]:
            print(f"  {rel}")
        if len(changed) > 20:
            print(f"  … {len(changed) - 20} more")
        if not args.force:
            print("re-run with --force to replace the installed copy")
            return 1

    if args.dry_run:
        print(f"would copy {SKILL_DIR} -> {dest}")
        return 0

    root.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SKILL_DIR, dest, ignore=IGNORE)
    count = sum(1 for p in dest.rglob("*") if p.is_file())
    print(f"installed {count} files to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
