#!/usr/bin/env python3
"""Write from the KGLite graph back into the Obsidian vault.

Two directions, both safe to re-run:

  backlinks  regenerate one index note that lists inbound and outbound links per note. The note
             carries kg_skip: true, so Obsidian renders it (with real, clickable wikilinks) while the
             vault reader skips it: the index never feeds back into the graph it reports.
  export     write the whole graph back out as a vault (okf export), manifest-guarded, for round trips
             and migrations.

Writing the index into the vault is the graph-to-Obsidian half of the loop. Re-running it is
idempotent: the generated region is replaced, and because the note is skipped, the graph counts stay
identical.

Usage:
    python vault_writeback.py backlinks VAULT [--graph G] [--name Backlinks.md] [--include-stubs]
    python vault_writeback.py export GRAPH OUT [--source-root VAULT] [--force]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from kglite import okf
except ImportError:  # pragma: no cover
    sys.exit("kglite is not importable. Install it: uv pip install kglite==0.21.2")

STRUCTURAL = {
    "CONTAINS", "CHILD_OF", "TAGGED", "PARENT_SECTION", "NEXT_SECTION", "NEXT_CHUNK", "NEXT_STEP",
    "HAS_SECTION", "HAS_CHUNK", "HAS_NOTE", "HAS_EXAMPLE", "HAS_PROCEDURE", "HAS_STEP",
    "HAS_PARAMETER", "HAS_IMAGE", "HAS_ATTACHMENT",
}

BEGIN = "<!-- kglite:backlinks -->"
END = "<!-- /kglite:backlinks -->"


def resolve_kglite() -> str:
    """Find the CLI even when it lives beside the running interpreter instead of on PATH."""
    found = shutil.which("kglite")
    if found:
        return found
    for name in ("kglite.exe", "kglite"):
        candidate = Path(sys.executable).with_name(name)
        if candidate.is_file():
            return str(candidate)
    sys.exit("kglite CLI not found: install it (uv tool install kglite==0.21.2) or put it on PATH")


def q(graph, statement):
    return list(graph.cypher(statement))


def link_rows(graph):
    inbound = q(
        graph,
        "MATCH (m)-[r]->(n) WHERE n.file_path IS NOT NULL AND m.file_path IS NOT NULL "
        "RETURN n.concept_id AS note, m.concept_id AS other, type(r) AS type, r.section AS section "
        "ORDER BY note, type, other",
    )
    outbound = q(
        graph,
        "MATCH (n)-[r]->(m) WHERE n.file_path IS NOT NULL AND m.file_path IS NOT NULL "
        "RETURN n.concept_id AS note, m.concept_id AS other, type(r) AS type, r.section AS section "
        "ORDER BY note, type, other",
    )
    stubs = q(
        graph,
        "MATCH (m)-[r]->(n {_provisional: true}) RETURN m.concept_id AS note, n.concept_id AS missing, "
        "type(r) AS type ORDER BY note, missing",
    )
    return (
        [r for r in inbound if r["type"] not in STRUCTURAL],
        [r for r in outbound if r["type"] not in STRUCTURAL],
        stubs,
    )


def render(graph, include_stubs: bool) -> str:
    notes = q(
        graph,
        "MATCH (n) WHERE n.file_path IS NOT NULL AND NOT coalesce(n._provisional,false) "
        "RETURN n.concept_id AS id, n.title AS title ORDER BY id",
    )
    inbound, outbound, stubs = link_rows(graph)
    by_in, by_out, by_stub = {}, {}, {}
    for row in inbound:
        by_in.setdefault(row["note"], []).append(row)
    for row in outbound:
        by_out.setdefault(row["note"], []).append(row)
    for row in stubs:
        by_stub.setdefault(row["note"], []).append(row)

    lines = [
        BEGIN,
        "Generated from the KGLite graph. This note carries kg_skip: true, so Obsidian shows it while the",
        "vault reader skips it: the index never feeds back into the graph it reports. Re-run",
        "python scripts/vault_writeback.py backlinks VAULT to refresh it.",
        "",
        f"Notes {len(notes)} · inbound edges {len(inbound)} · outbound edges {len(outbound)}",
        "",
    ]
    for note in notes:
        ins, outs = by_in.get(note["id"], []), by_out.get(note["id"], [])
        stub_rows = by_stub.get(note["id"], [])
        if not ins and not outs and not stub_rows:
            continue
        title = note["title"] or note["id"]
        lines.append(f"## [[{note['id']}|{title}]]")
        if ins:
            lines.append("")
            lines.append("Inbound:")
            for row in ins:
                section = f" · section {row['section']}" if row.get("section") else ""
                lines.append(f"- {row['type']} ← [[{row['other']}]]{section}")
        if outs:
            lines.append("")
            lines.append("Outbound:")
            for row in outs:
                section = f" · section {row['section']}" if row.get("section") else ""
                lines.append(f"- {row['type']} → [[{row['other']}]]{section}")
        if include_stubs and stub_rows:
            lines.append("")
            lines.append("Dangling:")
            for row in stub_rows:
                lines.append(f"- {row['type']} → [[{row['missing']}]] (not written yet)")
        lines.append("")
    lines.append(END)
    return "\n".join(lines) + "\n"


def write_index(vault: Path, name: str, body: str, force: bool) -> Path:
    target = (vault / name).resolve()
    frontmatter = "---\ntype: Index\nkg_skip: true\n---\n\n# Backlinks index\n\n"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if BEGIN not in existing and not force:
            sys.exit(
                f"{target} exists and was not written by this script (no {BEGIN} marker). "
                "Pass --force to replace it, or choose another --name."
            )
        target.write_text(frontmatter + body, encoding="utf-8")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(frontmatter + body, encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_back = sub.add_parser("backlinks", help="regenerate the skipped backlinks index note")
    p_back.add_argument("vault")
    p_back.add_argument("--graph", help="use an existing .kgl instead of building")
    p_back.add_argument("--name", default="Backlinks.md", help="index note path, relative to the vault")
    p_back.add_argument("--include-stubs", action="store_true", help="also list unresolved targets")
    p_back.add_argument("--force", action="store_true", help="replace a file this script did not write")

    p_export = sub.add_parser("export", help="write the graph back out as a vault")
    p_export.add_argument("graph")
    p_export.add_argument("out")
    p_export.add_argument("--source-root", help="vault the graph was built from (copies attachments)")
    p_export.add_argument("--edge-table", action="append", help="TYPE=Heading, repeatable")
    p_export.add_argument("--force", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "backlinks":
        vault = Path(args.vault).resolve()
        if not vault.is_dir():
            sys.exit(f"not a directory: {vault}")
        graph = __import__("kglite").load(args.graph) if args.graph else okf.build(str(vault), dialect="obsidian")
        body = render(graph, args.include_stubs)
        target = write_index(vault, args.name, body, args.force)
        notes = len(q(graph, "MATCH (n) WHERE n.file_path IS NOT NULL RETURN n"))
        print(f"wrote {target}")
        print(f"notes {notes}; the index note is kg_skip, so the graph is unchanged")
        return 0

    if args.cmd == "export":
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=True)
        cmd = [resolve_kglite(), "okf", "export", args.graph, str(out)]
        if args.source_root:
            cmd += ["--source-root", args.source_root]
        for table in args.edge_table or []:
            cmd += ["--edge-table", table]
        if args.force:
            cmd.append("--force")
        return subprocess.run(cmd).returncode

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
