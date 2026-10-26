---
name: obsidian-kglite
description: Build a KGLite knowledge graph from an Obsidian vault and answer questions about notes, backlinks, tags, sections, chunks and dangling links with Cypher. 把 Obsidian vault 读成可查询的知识图谱：孤儿笔记、断链、双链、标签、章节与段落检索，并可用 MCP 交给其他 agent。Use whenever the user mentions an Obsidian vault, note graph, backlinks, orphan or dangling notes, broken wikilinks, vault health or audit, kglite, okf, .kgl, 知识图谱, 双链, 断链, 孤儿笔记 — even when they never say kglite or Cypher.
---

# Obsidian → KGLite

An Obsidian vault is a directory of frontmatter-markdown notes. KGLite reads it as a
property graph and writes it back out again. Every task below is one of two things:

1. **Measure** — ask what the vault cannot answer by eye: orphans, dangling links, hub
   inflation, duplicate stems, which section mentions what, which table row carries
   which fact.
2. **Repair** — act on those measurements with evidence, then re-measure. Editing the
   vault stays a deliberate, reviewable step; the graph never edits itself.

The vault stays the source of truth. The graph is a rebuildable lens, and building one
never writes into the vault.

## Preflight

```bash
uv tool install kglite==0.21.2     # or: uv pip install kglite==0.21.2 in the project venv
kglite --version                    # expect 0.21.2 or newer
```

- The vault format is versioned `kglite_vault: 1`. A newer kglite reads it; an older one
  fails the build loudly on a key it does not know. Check `kglite --version` before
  trusting a report on a vault that uses `structure:`.
- Keep the compiled graph (`.kgl`) **outside** the vault. Every non-hidden file under the
  root is a candidate attachment, so a graph written inside changes the vault it
  describes.
- `kglite okf build` does not create its output directory (`failed to save ... os error 3`).
- One Cypher statement per call. Two statements separated by `;` return `[]` silently.

## Mental model — six rules decide every query

| On disk | In the graph |
| --- | --- |
| `Faults.md` | one node, id = stem `Faults`; `title` from frontmatter or first heading |
| top-level folder `Geology/` | primary label `:Geology` |
| `type: Project` | overrides the folder label |
| `depends_on: "[[Horizons]]"` | a `DEPENDS_ON` **edge**, not a property |
| `[[Page#Heading]]`, `[[Page#^block]]` | resolves onto the derived section or chunk |
| `#seismic`, `tags: [seismic]` | one `:Tag` hub, case-insensitive, joined by `TAGGED` |

Two consequences matter before writing any query:

- **Notes carry `file_path`; derived nodes never do.** Sections, chunks, callouts,
  examples, procedures, steps and table rows are derived from a note's body, so
  `n.file_path IS NOT NULL` is the cheapest way to say "real file". Use it for orphan
  detection and file inventories.
- **Hierarchy edges run parent→child.** `(note)-[:HAS_SECTION]->(top-level section)` and
  `(section)-[:HAS_SECTION]->(child section)`. Matching from the note reaches only the
  first level; match `(s:Section)` directly when you need every section, and use
  `PARENT_SECTION` to walk up.

### 中文术语对照

Chinese users say these words; the graph calls them something else. Map the request before writing Cypher.

| 你会怎么说 | Graph object | Where to start |
| --- | --- | --- |
| 孤儿笔记 / 孤岛笔记 | a note with no semantic edge | `file_path IS NOT NULL` plus a degree filter |
| 断链 / 空链接 | `_provisional: true` stub | `MATCH (n {_provisional: true})` |
| 双链 / 反向链接 | typed edges and `LINKS_TO` | `(m)-[r]->(n)` |
| 标签体系 / 标签树 | `Tag` hub | `(t:Tag)<-[:TAGGED]-(n)` |
| 章节 / 小节 | `Section` | `HAS_SECTION`, `PARENT_SECTION` |
| 段落块 / 引用块 | `Chunk` | `text CONTAINS` |
| 提示框 / 警告块 | `Note` with `kind` | `MATCH (n:Note)` |
| 参数表 / 字段表 | row nodes from a table rule | `structure.tables` |

Read `references/CYPHER-COOKBOOK.md` for the query behind each row.

Read `references/VAULT-FORMAT.md` when an answer depends on exact resolution, typing or
edge precedence. It condenses the normative spec with section numbers.

## The loop

```bash
mkdir -p .kglite-out                                    # 1. output dir must exist
kglite okf check VAULT --strict                         # 2. read without building; exit != 0 = invalid
kglite okf build VAULT -o .kglite-out/vault.kgl         # 3. report on stderr, path on stdout
kglite query .kglite-out/vault.kgl "MATCH (n) WHERE n.file_path IS NOT NULL RETURN count(*) AS notes" --format json
kglite okf status VAULT --graph .kglite-out/vault.kgl   # 4. current / stale, exit 0 / 1
```

- `check` runs the same read a build runs and throws the graph away. It is not a second
  opinion: if `check` passes, the build reads the same files the same way. `--strict`
  promotes warnings to errors — the setting for a converter's own tests.
- A build never writes into the vault; `okf open` does, because it caches. The default
  cache is `VAULT/.kglite/graph.kgl` (plus `.lock` siblings). Use
  `--cache ../out/cache.kgl` or `--cache none` when the vault must stay clean or read-only.
- Re-run `check` and `status` after every edit. A graph is stale the moment a note,
  `.kglite/vault.yaml` or an attachment changes.

## Choose the surface

| Need | Use | Why |
| --- | --- | --- |
| audit, inventory, one-off question | `kglite query G "..." --format json` | no server, no state |
| multi-step work on one graph | `kglite session G --format json` with JSONL ops | one load, many ops |
| bounded output for an agent | `--format agent` | byte budget plus an expansion handle |
| programmatic analysis | Python `okf.build` then `g.cypher` | typed rows, `to_df=True`, reusable graph |
| serve another agent | `kglite-mcp-server --graph G` or `--vault VAULT` | MCP tools, skills, recipes |

`g.cypher(q)` returns rows as dicts. `okf.validate(path)` returns the same report the CLI
prints. `okf.build(path, dialect="obsidian")` names the vault dialect explicitly —
`okf.build` defaults to `okf`, a real footgun when you meant a vault.

## Queries you will reach for first

Every query below was executed against a fixture vault; expected shapes are in the cookbook.

```cypher
// inventory by label
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC, label

// whole-vault edge census
MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n ORDER BY n DESC

// notes with no semantic edge to another note
MATCH (n) WHERE n.file_path IS NOT NULL AND NOT coalesce(n._provisional,false)
OPTIONAL MATCH (n)-[r]-(m) WHERE m.file_path IS NOT NULL AND NOT type(r) IN ['CONTAINS','TAGGED']
WITH n, count(r) AS d WHERE d = 0
RETURN n.concept_id AS id ORDER BY id

// dangling links (referenced, never written)
MATCH (n {_provisional: true}) RETURN n.concept_id AS missing, n.title

// retrieve the passage, not the page
MATCH (c:Chunk) WHERE c.text CONTAINS 'datum' RETURN c.note_id, c.concept_id, c.text
```

`references/CYPHER-COOKBOOK.md` groups the rest by question: identity conflicts, link
graph, section tree, tables and procedures, tags, health and staleness.

## Making structure survive

Structure is opt-in and declarative. It lives in `.kglite/vault.yaml`, never in flags,
and every rebuild re-applies it. Without it a note is one node holding one body; with it
the note's own markdown becomes sections, chunks, callouts, examples, procedures and
table rows.

```yaml
# .kglite/vault.yaml
kglite_vault: 1
structure:
  sections: {label: Section, edge: HAS_SECTION, parent: PARENT_SECTION, next: NEXT_SECTION}
  chunks: {label: Chunk, edge: HAS_CHUNK, next: NEXT_CHUNK, max_words: 650, max_chars: 6000}
```

Four in-note annotations carry facts prose alone cannot reach: a typed link, a directive,
a modelled tag, a chunk boundary. They render as ordinary Obsidian markdown and no export
rewrites them. `references/ANNOTATIONS.md` gives each one with the query that reads it
back; `assets/note-annotations.md` is a copyable template.

Rules that matter when authoring or repairing notes:

- A wikilink-valued frontmatter key **is** an edge. Do not also write a property that
  repeats it; the property is not stored.
- `{type}` sits directly after `]]` with no space. A misplaced brace is prose plus a
  warning, not an error — read the report.
- Heading text is scanned: links, tags and images inside a heading carry that heading as
  `section`. The built-in heading ladder (`depend` → `DEPENDS_ON`, `relate` → `RELATED`,
  `refer` → `REFERENCES`, `cite` → `CITES`, `join` → `JOINS_WITH`) *classifies text, it does
  not prove meaning*. Write `[[Target]]{LINKS_TO}` for a neutral reference and reserve
  stronger types for asserted relationships.
- A chunk is as narrow as the author made it. Two paragraphs often pack into one chunk, so
  a marker meant for one marks both. Fix with `<!-- kglite chunk -->` or a `^block-id`.
- `type:` on every file when the folder already says it makes a later folder move a no-op.
  Prefer folders for labels, `type:` only for the exceptions (root-level folder notes,
  cross-cutting kinds).

## Link-graph repair

The graph is evidence, not a generator. Repair navigation among notes that already exist;
never mint parallel concept notes for the same thing. The full protocol — including the
two-signal rule and the anti-sprawl checks — is in `references/LINK-GRAPH.md`. The short
form:

1. **Snapshot** — `check --strict` and `build`; keep the report.
2. **Measure** — orphans, stubs, hub degrees, bridge notes.
3. **Propose** — every proposal carries its evidence query and the row that justified it.
   One signal is not enough: a shared tag alone links everything to everything, so require
   a second signal (shared neighbour, an unlinked mention, a relation the folder tree
   already implies).
4. **Validate** — no duplicate edge of a different type, no link that contradicts the
   id/stem namespace, no prose rewrite.
5. **Apply** — through the Obsidian CLI or a file edit, one note at a time.
6. **Re-measure** — the same queries must move in the direction claimed. If they do not,
   revert and report the null result instead of adding more links.

## Serving the vault to an agent

```bash
kglite-mcp-server --graph .kglite-out/vault.kgl   # static graph
kglite-mcp-server --vault VAULT                   # owns build + cache, rebuilds when stale
```

- `.kglite/skills/*.md` become `:KgliteSkill` nodes the server serves to agents;
  `.kglite/recipes/*.md` become stored, parameterised Cypher. A recipe must be read-only
  and must not spell `LIMIT 200` — that is the result cap an agent host enforces, so a
  stored `LIMIT 200` would hide truncation. Write `LIMIT 199` for "everything under the
  cap".
- `--format agent` is a byte budget over the whole serialized response, not a row cap.
  Default 16,384 bytes, minimum 4,096. Expansion reads the retained result and never
  re-runs the query. Coverage fields distinguish "the query said LIMIT" from "the database
  has nothing more" — never read a non-truncated first page as proof of completeness.
- Rebuild and reload are different acts: note content needs a rebuild; a recipe change or
  a `tool:` name needs a server restart.

## Failure modes seen in practice

| Symptom | Cause | Fix |
| --- | --- | --- |
| `id collision: N notes resolve to id README` (error) | the same stem in several folders | declare `id:` per note, or rename the stems |
| build fails on an unknown `vault.yaml` key | `structure:` read by an older kglite | upgrade kglite; the declaration file is a hard compatibility boundary |
| `failed to save ... os error 3` | output directory missing | create the parent directory first |
| a query returns `[]` | two statements in one call | one statement per call |
| every link is `LINKS_TO` | no `structure:`, no `heading_edges:`, no `{type}` | declare one of them |
| structure vanished after export | an export does not write `vault.yaml` | copy `.kglite/vault.yaml` beside the exported tree |
| labels changed after export | export re-files a note under `<Label>/` when folder and label disagree | keep folder and label aligned, or accept the re-filing |
| a rule matched nothing | regex vs actual heading text | the build warns; fix the rule, not the vault |
| warnings nobody can fix | dangling links are normal mid-authoring | fix or name and accept them; `--strict` is for converter tests |

## Verification checklist

A result is trustworthy only when all of these hold:

- `kglite okf check VAULT --strict` exits 0, or every remaining warning is named and
  accepted.
- `kglite okf status VAULT --graph G` prints `current` after the last edit.
- The claim you are about to make has a query behind it, and that query returned the rows
  you quote — including empty ones. "No orphans" is a result; "I did not look" is not.
- Counts reconcile: `files scanned` matches the notes you expect; a rule that matched
  nothing appears as a warning, which is the fastest converter defect to spot.
- Vault edits are reversible and separately owned: generated notes, operator edits and
  reviewed annotations live in distinct paths, each with stable ids and source anchors.

## Reference map

| Read | When |
| --- | --- |
| `references/VAULT-FORMAT.md` | exact labels, ids, resolution ladders, typing, directives, `vault.yaml` keys, validation classes, export losses |
| `references/CYPHER-COOKBOOK.md` | the query you need is not in this file |
| `references/ANNOTATIONS.md` | adding structure to notes, or debugging an annotation that did nothing |
| `references/LINK-GRAPH.md` | auditing or repairing links, orphans, stubs, hub inflation |
| `references/SERVING.md` | MCP server, `.kglite/skills`, `.kglite/recipes`, agent output budgets |
| `references/OBSIDIAN-CLI.md` | reading and writing notes through the Obsidian CLI |
| `references/OBSIDIAN-MARKDOWN.md` | wikilinks, embeds, callouts, properties, block ids |
| `references/SOURCES.md` | provenance, verified-vs-documented status |
| `scripts/vault_graph.py` | path-safe wrapper for check/build/status/query/export |
| `scripts/vault_report.py` | Markdown health report from the Python API |
| `scripts/check_upstream.py` | are the inlined Obsidian skills stale? |
| `assets/vault.yaml` | starting declaration file |
| `assets/note-annotations.md` | template showing all five annotations |