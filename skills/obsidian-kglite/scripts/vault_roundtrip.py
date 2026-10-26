#!/usr/bin/env python3
"""Prove the vault -> graph -> vault -> graph loop, including the reconciliation export needs.

What it does:

1. build a graph from the vault (G1)
2. export G1, then seal the export: drop frontmatter keys whose edge the body already states, and copy
   .kglite/ declarations back in. Without this, a heading_edges type comes back twice (once from prose,
   once from the frontmatter list an export writes for it)
3. export the same graph twice and compare the sealed trees byte for byte (determinism)
4. build G2 from the sealed export
5. compare G1 and G2 on what must survive: note set, bodies, note-to-note link targets, edge types,
   dangling links
6. export G2 again, seal, and compare with the first sealed export (fixed point)

Hard checks fail the run. Declared losses that survive reconciliation (edge properties on undeclared
types) are reported, not failed.

Usage:
    python vault_roundtrip.py VAULT [--workdir DIR] [--json]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import shutil
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

# Labels that only exist because a note's body was split up. Image, Attachment, Folder and Tag
# regenerate from files, so their absence is not evidence that structure was lost.
BODY_DERIVED = {"Section", "Chunk", "Example", "Procedure", "ProcedureStep", "ApiParameter",
                "ApiReturn", "ApiException", "ApiSymbol", "Intent"}

RESERVED = {"id", "type", "title", "aliases", "tags", "kg_skip", "parent", "cssclasses"}
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
KEY_VALUE = re.compile(r"^([A-Za-z0-9_.-]+):(.*)$")


def q(graph, statement):
    return list(graph.cypher(statement))


def notes_of(graph):
    return {row["id"]: row["file"] for row in q(
        graph, "MATCH (n) WHERE n.file_path IS NOT NULL RETURN n.concept_id AS id, n.file_path AS file")}


def bodies_of(graph):
    return {row["id"]: row["body"] for row in q(
        graph, "MATCH (n) WHERE n.file_path IS NOT NULL RETURN n.concept_id AS id, n.body AS body")}


def semantic_rows(graph):
    rows = q(
        graph,
        "MATCH (a)-[r]->(b) WHERE a.file_path IS NOT NULL AND b.file_path IS NOT NULL "
        "RETURN a.concept_id AS src, b.concept_id AS dst, type(r) AS type, "
        "r.section AS section, r.anchor AS anchor, r.label AS label",
    )
    return [row for row in rows if row["type"] not in STRUCTURAL]


def body_edges(graph):
    """Edges the prose states: they carry section, anchor or label; frontmatter edges carry none."""
    return {(row["src"], row["type"], row["dst"]) for row in semantic_rows(graph)
            if row["section"] or row["anchor"] or row["label"]}


def edge_type_of(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_").upper()


def seal_note(path: Path, note_id: str, stated: set) -> int:
    """Remove frontmatter keys whose wikilink targets the body already states with the same type."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not match:
        return 0
    lines = match.group(1).splitlines()
    kept, removed = [], 0
    index = 0
    while index < len(lines):
        entry = [lines[index]]
        index += 1
        while index < len(lines) and (lines[index].startswith((" ", "\t", "- "))):
            entry.append(lines[index])
            index += 1
        head = KEY_VALUE.match(entry[0].strip()) or KEY_VALUE.match(entry[0])
        if not head:
            kept.extend(entry)
            continue
        key = head.group(1)
        if key in RESERVED:
            kept.extend(entry)
            continue
        targets = WIKILINK.findall("\n".join(entry))
        if not targets:
            kept.extend(entry)
            continue
        edge_type = edge_type_of(key)
        if all((note_id, edge_type, target.strip()) in stated for target in targets):
            removed += 1
            continue
        kept.extend(entry)
    if not removed:
        return 0
    path.write_text("---\n" + "\n".join(kept) + "\n---\n" + text[match.end():], encoding="utf-8")
    return removed


def seal_export(export_dir: Path, graph, vault: Path) -> dict:
    notes = notes_of(graph)
    stated = body_edges(graph)
    by_stem = {Path(rel).stem: note_id for note_id, rel in notes.items()}
    removed, files = 0, 0
    for path in sorted(export_dir.rglob("*.md")):
        note_id = by_stem.get(path.stem)
        if not note_id:
            continue
        count = seal_note(path, note_id, stated)
        removed += count
        files += 1 if count else 0

    copied = []
    declarations = vault / ".kglite"
    if declarations.is_dir():
        for name in ("vault.yaml", "skills", "recipes"):
            source = declarations / name
            if not source.exists():
                continue
            target = export_dir / ".kglite" / name
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, target)
            copied.append(name)
    return {"frontmatter_keys_removed": removed, "files_changed": files, "declarations_copied": copied}


def stubs_of(graph):
    return {row["id"] for row in q(graph, "MATCH (n {_provisional:true}) RETURN n.concept_id AS id")}


def labels_of(graph):
    return {row["label"]: row["n"] for row in q(
        graph, "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label")}


def tree_hashes(root: Path):
    return {str(path.relative_to(root)).replace(chr(92), "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        match = re.match(r"---\r?\n.*?\r?\n---\r?\n", text, re.S)
        if match:
            return text[match.end():]
    return text


def diff_counter(a: collections.Counter, b: collections.Counter) -> dict:
    return {
        "only_in_graph": [" | ".join(item) + f" x{count}" for item, count in (a - b).items()],
        "only_in_exported": [" | ".join(item) + f" x{count}" for item, count in (b - a).items()],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vault")
    parser.add_argument("--workdir", help="scratch directory (default: sibling .kglite-roundtrip)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        sys.exit(f"not a directory: {vault}")
    work = Path(args.workdir).resolve() if args.workdir else vault.parent / ".kglite-roundtrip"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    report = {"vault": str(vault), "work": str(work), "checks": {}, "failures": [], "losses": []}

    g1 = okf.build(str(vault), dialect="obsidian")

    sealed = []
    for name in ("exported-a", "exported-b"):
        target = work / name
        target.mkdir(parents=True, exist_ok=True)
        okf.export(g1, str(target), source_root=str(vault))
        sealed.append(seal_export(target, g1, vault))

    exp_a, exp_b = work / "exported-a", work / "exported-b"
    hashes_a, hashes_b = tree_hashes(exp_a), tree_hashes(exp_b)
    report["checks"]["export_deterministic"] = hashes_a == hashes_b
    if not report["checks"]["export_deterministic"]:
        report["failures"].append("two exports of the same graph differ")
    report["seal"] = sealed[0]

    g2 = okf.build(str(exp_a), dialect="obsidian")

    notes1, notes2 = notes_of(g1), notes_of(g2)
    gap = {"only_in_graph": sorted(set(notes1) - set(notes2)),
           "only_in_exported": sorted(set(notes2) - set(notes1))}
    report["note_gap"] = gap
    report["checks"]["note_set_preserved"] = not (gap["only_in_graph"] or gap["only_in_exported"])
    if not report["checks"]["note_set_preserved"]:
        report["failures"].append("note set changed across the round trip")

    body1, body2 = bodies_of(g1), bodies_of(g2)
    body_diff = [note for note in sorted(set(body1) & set(body2))
                 if strip_frontmatter(body1.get(note) or "").strip() != strip_frontmatter(body2.get(note) or "").strip()]
    report["body_diff"] = body_diff
    report["checks"]["bodies_preserved"] = not body_diff
    if body_diff:
        report["failures"].append(f"{len(body_diff)} note bodies changed")

    edges1 = collections.Counter((r["src"], r["type"], r["dst"]) for r in semantic_rows(g1))
    edges2 = collections.Counter((r["src"], r["type"], r["dst"]) for r in semantic_rows(g2))
    edge_gap = diff_counter(edges1, edges2)
    report["edge_gap"] = edge_gap
    report["semantic_edges"] = {"graph": sum(edges1.values()), "exported": sum(edges2.values())}
    report["checks"]["semantic_edges_preserved"] = not (edge_gap["only_in_graph"] or edge_gap["only_in_exported"])
    if not report["checks"]["semantic_edges_preserved"]:
        report["failures"].append("note-to-note edges changed after the sealed round trip")

    stubs1, stubs2 = stubs_of(g1), stubs_of(g2)
    report["dangling"] = {"graph": sorted(stubs1), "exported": sorted(stubs2)}
    report["checks"]["dangling_links_preserved"] = stubs1 == stubs2
    if stubs1 != stubs2:
        report["failures"].append("dangling links changed")

    exp_c = work / "exported-c"
    exp_c.mkdir(parents=True, exist_ok=True)
    okf.export(g2, str(exp_c), source_root=str(exp_a))
    seal_export(exp_c, g2, exp_a)
    hashes_c = tree_hashes(exp_c)
    report["checks"]["fixed_point"] = hashes_a == hashes_c
    report["fixed_point_diff"] = sorted(
        name for name in set(hashes_a) | set(hashes_c) if hashes_a.get(name) != hashes_c.get(name))[:10]

    labels1, labels2 = labels_of(g1), labels_of(g2)
    lost = {label: labels1[label] for label in labels1 if label in BODY_DERIVED and label not in labels2}
    report["checks"]["structure_rebuilt"] = not lost
    if lost:
        report["losses"].append(f"derived nodes not rebuilt: {', '.join(f'{k}={v}' for k, v in sorted(lost.items()))}")
    report["losses"].append(
        "edge properties are still lost for types without an export.edge_tables entry; declare the table, "
        "then read it back with a structure.tables rule")
    report["labels"] = {"graph": labels1, "exported": labels2}

    passed = not report["failures"]
    report["passed"] = passed

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"round trip: {'PASS' if passed else 'FAIL'}")
        for name, ok in report["checks"].items():
            print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        print(f"  notes {len(notes1)} -> {len(notes2)}; semantic edges {sum(edges1.values())} -> {sum(edges2.values())}")
        print(f"  seal removed {report['seal']['frontmatter_keys_removed']} duplicated frontmatter key(s) "
              f"in {report['seal']['files_changed']} file(s); declarations copied: "
              f"{', '.join(report['seal']['declarations_copied']) or 'none'}")
        if report["edge_gap"]["only_in_graph"] or report["edge_gap"]["only_in_exported"]:
            for row in report["edge_gap"]["only_in_graph"][:5]:
                print(f"    - {row}")
            for row in report["edge_gap"]["only_in_exported"][:5]:
                print(f"    + {row}")
        for line in report["losses"]:
            print(f"  loss {line}")
        if not report["checks"]["fixed_point"]:
            print(f"  fixed-point differences: {report['fixed_point_diff']}")
        if report["failures"]:
            print("failures:")
            for failure in report["failures"]:
                print(f"  - {failure}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
