#!/usr/bin/env python3
"""Path-safe wrapper around the kglite CLI for Obsidian vaults.

Why a wrapper: three defaults in this skill are easy to get wrong by hand.
  * an output directory that does not exist makes "okf build" fail with os error 3;
  * a graph written inside the vault becomes a file of the vault;
  * two Cypher statements in one "query" call return [] silently.

Subcommands: check, build, status, open, query, export, describe, skill.
Everything else is passed through to kglite unchanged.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_KGLITE = "kglite"


def find_kglite(explicit: str | None) -> str:
    if explicit:
        return explicit
    found = shutil.which(DEFAULT_KGLITE)
    if not found:
        sys.exit(
            "kglite not found on PATH. Install it (uv tool install kglite==0.21.2) "
            "or pass --kglite /path/to/kglite."
        )
    return found


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def count_statements(query: str) -> int:
    """Count top-level semicolons, ignoring them inside quotes and line comments."""
    statements, i, quote, in_line_comment, in_block_comment = 0, 0, None, False, False
    while i < len(query):
        ch = query[i]
        nxt = query[i + 1] if i + 1 < len(query) else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == ";":
            statements += 1
        i += 1
    return statements


def run(cmd: list[str]) -> int:
    printable = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    print(f"+ {printable}", file=sys.stderr)
    proc = subprocess.run(cmd)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kglite", help="path to the kglite executable (default: found on PATH)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="read the vault without building; non-zero exit means invalid")
    p_check.add_argument("vault")
    p_check.add_argument("--strict", action="store_true", help="promote warnings to errors")
    p_check.add_argument("--json", action="store_true", help="machine-readable report")

    p_build = sub.add_parser("build", help="build the graph, keeping it outside the vault by default")
    p_build.add_argument("vault")
    p_build.add_argument("-o", "--out", help="graph path (default: <vault>/../.kglite-out/<name>.kgl)")
    p_build.add_argument("--dialect", default="obsidian", choices=["obsidian", "okf", "loose"])
    p_build.add_argument("--allow-inside", action="store_true", help="permit a graph path inside the vault")

    p_status = sub.add_parser("status", help="current vs stale, exit 0 vs non-zero")
    p_status.add_argument("vault")
    p_status.add_argument("--graph")

    p_open = sub.add_parser("open", help="cached open; writes the cache into .kglite/ by default")
    p_open.add_argument("vault")
    p_open.add_argument("--cache", help="cache path, or 'none' to disable")
    p_open.add_argument("--dialect", default="obsidian", choices=["obsidian", "okf", "loose"])

    p_query = sub.add_parser("query", help="run one read-only statement")
    p_query.add_argument("graph")
    p_query.add_argument("statement")
    p_query.add_argument("--format", default="json", choices=["json", "csv", "table", "agent"])
    p_query.add_argument("--timeout-ms", type=int)
    p_query.add_argument("--response-max-bytes", type=int)
    p_query.add_argument("--allow-multiple", action="store_true")

    p_export = sub.add_parser("export", help="write the graph back out as a vault")
    p_export.add_argument("graph")
    p_export.add_argument("out")
    p_export.add_argument("--source-root", help="vault the graph was built from (copies attachments)")
    p_export.add_argument("--edge-table", action="append", help="TYPE=Heading, repeatable")
    p_export.add_argument("--force", action="store_true")

    p_describe = sub.add_parser("describe", help="schema document for an agent")
    p_describe.add_argument("graph")
    p_describe.add_argument("--types", nargs="*")
    p_describe.add_argument("--cypher", action="store_true")
    p_describe.add_argument("--connections", action="store_true")

    p_skill = sub.add_parser("skill", help="list skills carried in the graph, or print one body")
    p_skill.add_argument("graph")
    p_skill.add_argument("name", nargs="?")
    p_skill.add_argument("--format", default="table", choices=["table", "json", "csv"])

    args = parser.parse_args(argv)
    exe = find_kglite(args.kglite)

    if args.cmd == "check":
        cmd = [exe, "okf", "check", args.vault]
        if args.strict:
            cmd.append("--strict")
        if args.json:
            cmd.append("--json")
        return run(cmd)

    if args.cmd == "build":
        vault = Path(args.vault).resolve()
        if args.out:
            out = Path(args.out).resolve()
        else:
            out = vault.parent / ".kglite-out" / (vault.name + ".kgl")
        if inside(out, vault) and not args.allow_inside:
            sys.exit(
                f"refusing to write {out} inside the vault: every non-hidden file under the root is a "
                "candidate attachment, so the graph would change the vault it describes. "
                "Pass --allow-inside to override."
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        return run([exe, "okf", "build", str(vault), "-o", str(out), "--dialect", args.dialect])

    if args.cmd == "status":
        cmd = [exe, "okf", "status", args.vault]
        if args.graph:
            cmd += ["--graph", args.graph]
        return run(cmd)

    if args.cmd == "open":
        cmd = [exe, "okf", "open", args.vault, "--dialect", args.dialect]
        if args.cache:
            cmd += ["--cache", args.cache]
        return run(cmd)

    if args.cmd == "query":
        trimmed = args.statement.strip().rstrip(";").rstrip()
        separators = count_statements(trimmed)
        if separators >= 1 and not args.allow_multiple:
            sys.exit(
                "the statement contains a top-level ';', so it holds more than one statement; kglite runs "
                "one statement per call and returns [] for the rest. Split the query, or pass "
                "--allow-multiple."
            )
        cmd = [exe, "query", args.graph, args.statement, "--format", args.format]
        if args.timeout_ms:
            cmd += ["--timeout-ms", str(args.timeout_ms)]
        if args.response_max_bytes:
            cmd += ["--response-max-bytes", str(args.response_max_bytes)]
        return run(cmd)

    if args.cmd == "export":
        Path(args.out).mkdir(parents=True, exist_ok=True)
        cmd = [exe, "okf", "export", args.graph, args.out]
        if args.source_root:
            cmd += ["--source-root", args.source_root]
        for table in args.edge_table or []:
            cmd += ["--edge-table", table]
        if args.force:
            cmd.append("--force")
        return run(cmd)

    if args.cmd == "describe":
        cmd = [exe, "describe", args.graph]
        if args.types:
            cmd += ["--types", *args.types]
        if args.cypher:
            cmd.append("--cypher")
        if args.connections:
            cmd.append("--connections")
        return run(cmd)

    if args.cmd == "skill":
        cmd = [exe, "skill", args.graph]
        if args.name:
            cmd.append(args.name)
        else:
            cmd += ["--format", args.format]
        return run(cmd)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
