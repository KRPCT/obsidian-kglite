#!/usr/bin/env python3
"""Markdown health report for an Obsidian vault, using the KGLite Python API.

Every number is produced by a named query or by okf.validate, so each line can be re-derived.
Read-only: nothing is written into the vault. The graph lives in memory unless --graph is given.

Usage:
    python vault_report.py VAULT [--graph G] [--top 10] [--out report.md] [--json] [--skip-check]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

try:
    from kglite import okf
except ImportError:  # pragma: no cover - dependency guidance
    sys.exit("kglite is not importable. Install it: uv pip install kglite==0.21.2 (or uv tool install).")

ORPHANS = """
MATCH (n) WHERE n.file_path IS NOT NULL AND NOT coalesce(n._provisional,false)
OPTIONAL MATCH (n)-[r]-(m) WHERE m.file_path IS NOT NULL AND NOT type(r) IN ['CONTAINS','TAGGED']
WITH n, count(r) AS d WHERE d = 0
RETURN n.concept_id AS id ORDER BY id
"""

LABELS = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC, label"
EDGES = "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n ORDER BY n DESC"
STUBS = "MATCH (n {_provisional: true}) RETURN n.concept_id AS id ORDER BY id"
STUB_SOURCES = """
MATCH (m)-[r]->(n {_provisional: true})
RETURN n.concept_id AS missing, m.concept_id AS source ORDER BY missing, source
"""
TAGS = "MATCH (t:Tag)<-[:TAGGED]-(n) RETURN t.id AS tag, count(n) AS uses ORDER BY uses DESC, tag"
CASE_IDS = """
MATCH (n) WHERE n.concept_id IS NOT NULL
WITH toLower(n.concept_id) AS k, collect(n.concept_id) AS ids, count(*) AS c
WHERE c > 1 RETURN k, ids
"""
CHUNK_SIZES = "MATCH (c:Chunk) RETURN size(c.text) AS chars"
NOTE_COUNT = "MATCH (n) WHERE n.file_path IS NOT NULL RETURN count(*) AS n"


def q(graph, statement: str):
    """Run one statement, returning [] if the graph cannot answer it (e.g. missing label)."""
    try:
        return list(graph.cypher(statement))
    except Exception as exc:  # noqa: BLE001 - a health report should not die on one gap
        print(f"warning: query failed ({exc}): {statement.strip()[:60]}...", file=sys.stderr)
        return []


def summary_lines(report_text: str) -> list[str]:
    keep = ("files scanned", "concepts:", "nodes:", "edges:", "folder notes", "dangling links", "missing attachments",
            "indexes declared", "text indexes built", "skills imported", "recipes imported",
            "forced chunk splits", "embed targets")
    return [line for line in report_text.splitlines() if line.strip().startswith(keep)]


def build_markdown(vault: Path, graph, report_text: str | None, top: int) -> tuple[str, dict]:
    labels = q(graph, LABELS)
    edges = q(graph, EDGES)
    orphans = [row["id"] for row in q(graph, ORPHANS)]
    stubs = [row["id"] for row in q(graph, STUBS)]
    stub_sources = q(graph, STUB_SOURCES)
    tags = q(graph, TAGS)
    case_ids = q(graph, CASE_IDS)
    chunk_chars = [row["chars"] for row in q(graph, CHUNK_SIZES) if row.get("chars")]
    notes = (q(graph, NOTE_COUNT) or [{"n": 0}])[0]["n"]

    data = {
        "vault": str(vault),
        "notes": notes,
        "labels": labels,
        "edges": edges,
        "orphans": orphans,
        "stubs": stubs,
        "stub_sources": stub_sources,
        "tags": tags,
        "case_collisions": case_ids,
        "chunks": len(chunk_chars),
        "chunk_chars_median": statistics.median(chunk_chars) if chunk_chars else None,
        "chunk_chars_max": max(chunk_chars) if chunk_chars else None,
    }

    out: list[str] = []
    out.append(f"# Vault health: {vault.name}")
    out.append("")
    out.append(f"Path: `{vault}`")
    out.append("")
    if report_text:
        out.append("## Build report")
        out.append("")
        out.append("```text")
        out.extend(summary_lines(report_text) or [report_text.strip()[:2000]])
        out.append("```")
        out.append("")

    out.append("## Size")
    out.append("")
    out.append(f"- notes: **{notes}**")
    total_nodes = sum(row["n"] for row in labels)
    out.append(f"- total nodes: **{total_nodes}**")
    out.append(f"- chunks: **{len(chunk_chars)}**"
               + (f", median {data['chunk_chars_median']:.0f} chars, max {data['chunk_chars_max']}"
                  if chunk_chars else ""))
    out.append("")
    out.append("Nodes by label:")
    out.append("")
    out.append("| label | nodes |")
    out.append("| --- | --- |")
    out.extend(f"| {row['label']} | {row['n']} |" for row in labels)
    out.append("")
    out.append("Edges by type:")
    out.append("")
    out.append("| type | edges |")
    out.append("| --- | --- |")
    out.extend(f"| {row['t']} | {row['n']} |" for row in edges)
    out.append("")

    out.append("## Link graph")
    out.append("")
    out.append(f"- orphan notes (no semantic edge to another note): **{len(orphans)}**")
    for name in orphans[:top]:
        out.append(f"  - {name}")
    if len(orphans) > top:
        out.append(f"  - … {len(orphans) - top} more")
    out.append(f"- dangling links: **{len(stubs)}**")
    for name in stubs[:top]:
        out.append(f"  - {name}")
    if len(stubs) > top:
        out.append(f"  - … {len(stubs) - top} more")
    if stub_sources:
        out.append("- who points at them:")
        for row in stub_sources[:top]:
            out.append(f"  - {row['source']} → {row['missing']}")
    out.append("")

    out.append("## Tags")
    out.append("")
    if tags:
        out.append("| tag | uses |")
        out.append("| --- | --- |")
        out.extend(f"| {row['tag']} | {row['uses']} |" for row in tags[:top])
        singles = sum(1 for row in tags if row["uses"] == 1)
        out.append("")
        out.append(f"Tags used exactly once (candidate labels that discriminate nothing yet): **{singles}**")
    else:
        out.append("_No Tag nodes: the vault carries no tags, or the build has no tags hub._")
    out.append("")

    out.append("## Identity")
    out.append("")
    if case_ids:
        out.append("Ids that differ only in case (a warning on every host, because the vault must open on"
                   " Linux, macOS and Windows):")
        for row in case_ids[:top]:
            out.append(f"- {row['k']}: {', '.join(row['ids'])}")
    else:
        out.append("No case-insensitive id collisions.")
    out.append("")

    out.append("## How to read this")
    out.append("")
    out.append("- Orphans and dangling links are the two movable numbers: see `references/LINK-GRAPH.md`.")
    out.append("- A tag used once is not automatically a problem; a hundred of them usually is.")
    out.append("- Chunk median tells you whether `chunks:` caps match the prose length. A median near the"
               " cap means the cap is cutting, not packing.")
    out.append("- Re-run this report after any edit and compare the same numbers, not a fresh set.")
    out.append("")
    return "\n".join(out), data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vault")
    parser.add_argument("--graph", help="open an existing .kgl instead of building")
    parser.add_argument("--cache", help="cache path for okf.open (default: none, build in memory)")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--out", help="write markdown here instead of stdout")
    parser.add_argument("--json", action="store_true", help="emit the collected data as JSON")
    parser.add_argument("--skip-check", action="store_true", help="skip okf.validate")
    args = parser.parse_args(argv)

    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        sys.exit(f"not a directory: {vault}")

    if args.graph:
        import kglite
        graph = kglite.load(args.graph)
        report_text = None
    elif args.cache:
        graph = okf.open(str(vault), dialect="obsidian", cache=args.cache)
        report_text = None if args.skip_check else str(okf.validate(str(vault)))
    else:
        graph = okf.build(str(vault), dialect="obsidian")
        report_text = None if args.skip_check else str(okf.validate(str(vault)))

    markdown, data = build_markdown(vault, graph, report_text, args.top)

    if args.json:
        payload = json.dumps(data, indent=2, default=str)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
        else:
            print(payload)
    else:
        if args.out:
            Path(args.out).write_text(markdown, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
