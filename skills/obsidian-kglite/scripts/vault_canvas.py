#!/usr/bin/env python3
"""Write an Obsidian canvas (or a Mermaid note) from a KGLite vault graph.

This is the graph-to-Obsidian direction of the loop. A .canvas file is never scanned by the vault
reader (canvas files are not interpreted, VAULT.md section 1), so exporting a graph view into the
vault changes no graph at all: what you see in Obsidian is the graph you measured.

Node types used: "file" for notes (Obsidian renders the note card), "text" for unresolved targets,
"group" for one label. Edges carry the relationship type as their label.

Usage:
    python vault_canvas.py VAULT [--graph G] [--out VAULT/Graph.canvas]
    python vault_canvas.py VAULT --mermaid VAULT/Graph.md
    python vault_canvas.py VAULT --types LINKS_TO RELATED_TO --include-stubs
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    from kglite import okf
except ImportError:  # pragma: no cover
    sys.exit("kglite is not importable. Install it: uv pip install kglite==0.21.2")

CANVAS_COLORS = ["1", "2", "3", "4", "5", "6"]

# Hierarchy and containment are already visible in Obsidian's file tree and graph view; a relationship
# canvas that repeats them hides the links a reader actually came for.
STRUCTURAL_TYPES = {
    "CONTAINS",
    "CHILD_OF",
    "TAGGED",
    "PARENT_SECTION",
    "NEXT_SECTION",
    "NEXT_CHUNK",
    "NEXT_STEP",
    "HAS_SECTION",
    "HAS_CHUNK",
    "HAS_NOTE",
    "HAS_EXAMPLE",
    "HAS_PROCEDURE",
    "HAS_STEP",
    "HAS_PARAMETER",
    "HAS_IMAGE",
    "HAS_ATTACHMENT",
}
NOTE_W, NOTE_H, NOTE_GAP = 260, 72, 24
GROUP_HEADER = 44
GROUP_GAP = 80


def cypher(graph, statement):
    return list(graph.cypher(statement))


def load_graph(vault: Path, graph_path: str | None):
    if graph_path:
        import kglite
        return kglite.load(graph_path)
    return okf.build(str(vault), dialect="obsidian")


def collect(graph, types: list[str] | None, include_stubs: bool, include_structural: bool = False):
    notes = cypher(
        graph,
        "MATCH (n) WHERE n.file_path IS NOT NULL AND NOT coalesce(n._provisional,false) "
        "RETURN n.concept_id AS id, n.file_path AS file, n.title AS title, labels(n)[0] AS label "
        "ORDER BY label, title",
    )
    edge_rows = cypher(
        graph,
        "MATCH (a)-[r]->(b) WHERE a.file_path IS NOT NULL AND b.file_path IS NOT NULL "
        "RETURN a.concept_id AS src, b.concept_id AS dst, type(r) AS type, r.section AS section "
        "ORDER BY type, src, dst",
    )
    if types:
        wanted = {t.upper() for t in types}
        edge_rows = [row for row in edge_rows if row["type"] in wanted]
    if not include_structural:
        edge_rows = [row for row in edge_rows if row["type"] not in STRUCTURAL_TYPES]
    stubs = []
    if include_stubs:
        stub_rows = cypher(
            graph,
            "MATCH (m)-[r]->(n {_provisional: true}) "
            "RETURN n.concept_id AS missing, m.concept_id AS src, type(r) AS type "
            "ORDER BY missing, src",
        )
        stubs = stub_rows
    return notes, edge_rows, stubs


def layout(notes):
    """One column per label, notes stacked; groups sized to their children."""
    by_label = defaultdict(list)
    for note in notes:
        by_label[note["label"] or "Note"].append(note)
    coords, groups = {}, []
    x = 0
    for label in sorted(by_label):
        items = by_label[label]
        for row, note in enumerate(items):
            coords[note["id"]] = (x + NOTE_GAP, GROUP_HEADER + row * (NOTE_H + NOTE_GAP))
        width = NOTE_W + NOTE_GAP * 2
        height = GROUP_HEADER + len(items) * (NOTE_H + NOTE_GAP) + NOTE_GAP // 2
        groups.append({"label": label, "x": x, "y": 0, "width": width, "height": height})
        x += width + GROUP_GAP
    return coords, groups


def build_canvas(notes, edge_rows, stubs, coords, groups):
    nodes, edges, ids = [], [], {}
    for index, note in enumerate(notes):
        node_id = f"note-{index:04d}"
        ids[note["id"]] = node_id
        x, y = coords[note["id"]]
        nodes.append({
            "id": node_id,
            "type": "file",
            "file": note["file"],
            "x": x,
            "y": y,
            "width": NOTE_W,
            "height": NOTE_H,
        })
    for index, group in enumerate(groups):
        nodes.append({
            "id": f"group-{index:03d}",
            "type": "group",
            "label": group["label"],
            "x": group["x"],
            "y": group["y"],
            "width": group["width"],
            "height": group["height"],
        })

    stub_ids, stub_y = {}, max((g["height"] for g in groups), default=0) + GROUP_GAP
    for index, stub in enumerate(stubs):
        if stub["missing"] in stub_ids:
            continue
        node_id = f"stub-{len(stub_ids):04d}"
        stub_ids[stub["missing"]] = node_id
        nodes.append({
            "id": node_id,
            "type": "text",
            "text": stub["missing"],
            "x": index * (NOTE_W + NOTE_GAP),
            "y": stub_y,
            "width": NOTE_W,
            "height": NOTE_H,
            "color": "1",
        })

    type_color = {t: CANVAS_COLORS[i % len(CANVAS_COLORS)] for i, t in enumerate(sorted({r["type"] for r in edge_rows}))}
    for index, row in enumerate(edge_rows):
        src, dst = ids.get(row["src"]), ids.get(row["dst"])
        if not src or not dst:
            continue
        edges.append({
            "id": f"edge-{index:04d}",
            "fromNode": src,
            "toNode": dst,
            "label": row["type"],
            "color": type_color.get(row["type"], "1"),
        })
    for index, row in enumerate(stubs):
        src, dst = ids.get(row["src"]), stub_ids.get(row["missing"])
        if not src or not dst:
            continue
        edges.append({
            "id": f"stubedge-{index:04d}",
            "fromNode": src,
            "toNode": dst,
            "label": row["type"],
            "color": "1",
        })
    return {"nodes": nodes, "edges": edges}


def mermaid_block(notes, edge_rows, title: str) -> str:
    ids = {note["id"]: f"n{i}" for i, note in enumerate(notes)}
    lines = ["%% generated by obsidian-kglite: graph view, no vault content touched", "graph LR"]
    for note in notes:
        label = (note["title"] or note["id"]).replace('"', "'")
        lines.append(f'  {ids[note["id"]]}["{label}"]')
    for row in edge_rows:
        if row["src"] in ids and row["dst"] in ids:
            lines.append(f'  {ids[row["src"]]} -->|{row["type"]}| {ids[row["dst"]]}')
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vault")
    parser.add_argument("--graph", help="use an existing .kgl instead of building")
    parser.add_argument("--out", help="canvas path (default: VAULT/Graph.canvas)")
    parser.add_argument("--mermaid", help="write a Markdown note with a Mermaid block instead of a canvas")
    parser.add_argument("--types", nargs="*", help="only these relationship types")
    parser.add_argument("--include-stubs", action="store_true", help="draw unresolved link targets")
    parser.add_argument("--include-structural", action="store_true",
                        help="also draw hierarchy edges (CONTAINS, CHILD_OF, HAS_*, NEXT_*)")
    parser.add_argument("--max-nodes", type=int, default=400, help="refuse to draw more notes than this")
    parser.add_argument("--json", action="store_true", help="print a summary as JSON")
    args = parser.parse_args(argv)

    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        sys.exit(f"not a directory: {vault}")
    graph = load_graph(vault, args.graph)
    notes, edge_rows, stubs = collect(graph, args.types, args.include_stubs, args.include_structural)
    if len(notes) > args.max_nodes:
        sys.exit(
            f"{len(notes)} notes exceed --max-nodes {args.max_nodes}. Raise the cap or filter with --types; "
            "a canvas with thousands of cards is not readable in Obsidian either."
        )

    if args.mermaid:
        out = Path(args.mermaid).resolve()
        body = mermaid_block(notes, edge_rows, vault.name)
        out.write_text(
            "---\ntype: Graph\nkg_skip: true\n---\n# Graph view\n\n"
            "Generated from the KGLite graph. The fence is not scanned, and kg_skip keeps this note out of the graph.\n\n"
            f"```mermaid\n{body}\n```\n",
            encoding="utf-8",
        )
        summary = {"out": str(out), "kind": "mermaid", "notes": len(notes), "edges": len(edge_rows)}
    else:
        out = Path(args.out).resolve() if args.out else vault / "Graph.canvas"
        coords, groups = layout(notes)
        canvas = build_canvas(notes, edge_rows, stubs, coords, groups)
        out.write_text(json.dumps(canvas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary = {
            "out": str(out),
            "kind": "canvas",
            "notes": len(notes),
            "edges": len(edge_rows),
            "stubs": len({s["missing"] for s in stubs}),
            "labels": len(groups),
        }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"{summary['kind']} -> {summary['out']}")
        print(f"notes {summary['notes']}, semantic edges {summary['edges']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
