# Cypher cookbook for Obsidian vaults

Every query here was executed against a fixture vault (notes across two folders, folder note,
frontmatter edges, typed link, table rows, procedure, callout, fenced example, image, dangling
link) with kglite 0.21.2. "Returns" describes the shape, not a promise about your vault.

Run them with:

```bash
kglite query GRAPH.kgl '<one statement>' --format json
```

Python: `okf.build("VAULT", dialect="obsidian").cypher(q)` returns rows as dicts.

Four rules that prevent most wasted queries:

- **One statement per call.** `MATCH …; MATCH …` returns `[]` silently. Split the work.
- **Notes have `file_path`; derived nodes do not.** Sections, chunks, callouts, examples,
  procedures, steps and table rows are derived, so `file_path IS NOT NULL` means "real file".
- **`path` is not an attachment-only property.** A `Section` also carries `path` (the list of
  heading titles in its id). Filter attachments by label (`(:Image)`, `(:Attachment)`), never by
  `path IS NOT NULL`.
- **Unknown labels and relationship types warn, they do not fail.** A warning that the graph has no
  `Attachment` type means zero attachments *of that name* — not "the query is broken", and not
  proof that nothing exists under another label.

Table headers become property names verbatim. A header with a space needs backticks in Cypher:
``RETURN p.`source anchor` ``. (Verified.)

---

## 1. Inventory

```cypher
// nodes by label
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC, label
```

Returns one row per label (fixture: `Chunk 11, Section 9, Tag 3, ApiParameter 2, Note 2, ProcedureStep 2,
Project 2, Area 1, Concept 1, Example 1, Intent 1, Journal 1, Procedure 1`).

```cypher
// edge census — the fastest way to see what the vault actually asserts
MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS n ORDER BY n DESC
```

```cypher
// the files behind the notes
MATCH (n) WHERE n.file_path IS NOT NULL
RETURN n.file_path AS file, labels(n)[0] AS label, n.title AS title
ORDER BY file
```

```cypher
// folder nodes (only for directories without a folder note; the vault root is not a Folder)
MATCH (f:Folder) RETURN f.id AS path, f.title AS title ORDER BY path
```

A vault whose top level is all folder notes has **no** `Folder` nodes at all — do not read an empty
result as a broken query.

## 2. Identity and integrity

Id collisions and other hard errors are reported by `okf check`, not by a query — the build already
renamed the survivors to path-relative ids.

```cypher
// notes sharing a filename stem, after the fallback renamed them
MATCH (n) WHERE n.file_path IS NOT NULL
WITH toLower(split(n.file_path,'/')[-1]) AS stem, collect(n.concept_id) AS ids
WHERE size(ids) > 1
RETURN stem, ids
```

```cypher
// ids that differ only in case (a warning in every build)
MATCH (n) WHERE n.concept_id IS NOT NULL
WITH toLower(n.concept_id) AS k, count(*) AS c
WHERE c > 1
RETURN k, c
```

```cypher
// path-relative ids, i.e. notes that lost the stem fallback
MATCH (n) WHERE n.file_path IS NOT NULL AND n.concept_id CONTAINS '/'
RETURN n.concept_id AS id, n.file_path AS file ORDER BY file
```

## 3. Link graph

```cypher
// what a note asserts
MATCH (n:Project {concept_id:'Beta'})-[r]->(m)
RETURN type(r) AS type, m.concept_id AS target, r.section AS section
ORDER BY type, target
```

```cypher
// everything pointing at a note, with the section it was written under
MATCH (m)-[r]->(n:Project {concept_id:'Beta'})
RETURN type(r) AS type, m.concept_id AS source, r.section AS section
```

```cypher
// orphans: no semantic edge to another note (structural edges are excluded by the file_path filter)
MATCH (n) WHERE n.file_path IS NOT NULL AND NOT coalesce(n._provisional,false)
OPTIONAL MATCH (n)-[r]-(m) WHERE m.file_path IS NOT NULL AND NOT type(r) IN ['CONTAINS','TAGGED']
WITH n, count(r) AS d WHERE d = 0
RETURN n.concept_id AS id ORDER BY id
```

```cypher
// dangling links: referenced, never written
MATCH (n {_provisional: true}) RETURN n.concept_id AS missing, n.title AS title
```

```cypher
// who dangles where
MATCH (m)-[r]->(n {_provisional: true})
RETURN n.concept_id AS missing, type(r) AS type, m.concept_id AS source, r.section AS section
```

```cypher
// degree ranking over semantic edges — bridges and hubs at a glance
MATCH (n) WHERE n.file_path IS NOT NULL AND NOT coalesce(n._provisional,false)
OPTIONAL MATCH (n)-[r]-(m) WHERE m.file_path IS NOT NULL
WITH n, collect(type(r)) AS ts
WITH n, [t IN ts WHERE NOT t IN ['CONTAINS','TAGGED']] AS sem
WITH n, size(sem) AS degree
RETURN n.concept_id AS id, degree ORDER BY degree DESC, id LIMIT 20
```

```cypher
// unlinked mention: the text names another note, no link was written
MATCH (c:Chunk), (n)
WHERE n.file_path IS NOT NULL AND n.title IS NOT NULL
  AND c.note_id <> n.concept_id
  AND c.text CONTAINS n.title
  AND NOT c.text CONTAINS ('[[' + n.title)
RETURN c.note_id AS source, n.concept_id AS target, left(c.text, 60) AS evidence
```

The `NOT c.text CONTAINS ('[[' + n.title)` clause is what keeps existing links from being reported as
mentions. Chunks pack paragraphs, so `evidence` is the packed range, not a single sentence — open the
file before editing.

```cypher
// two-signal proposal helper: shared neighbours between notes that are not linked yet
MATCH (a)-[:LINKS_TO]->(m)<-[:LINKS_TO]-(b)
WHERE a.file_path IS NOT NULL AND b.file_path IS NOT NULL
  AND a.concept_id < b.concept_id
  AND NOT (a)-[]-(b)
RETURN a.concept_id AS a, b.concept_id AS b, collect(m.concept_id) AS via, count(*) AS strength
ORDER BY strength DESC LIMIT 20
```

Add a second signal (shared tag, unlinked mention, folder sibling) before proposing anything; the
proposal protocol is in `LINK-GRAPH.md`.

## 4. Section tree

```cypher
// a note's outline, in document order
MATCH (n:Project {concept_id:'Alpha'})-[:HAS_SECTION]->(s:Section)
OPTIONAL MATCH (s)-[:HAS_SECTION]->(c:Section)
RETURN s.title AS section, s.level AS level, s.ordinal AS ordinal, collect(c.title) AS children
ORDER BY level, ordinal
```

```cypher
// every leaf section in the vault
MATCH (s:Section) WHERE NOT (s)-[:HAS_SECTION]->()
RETURN s.concept_id AS leaf ORDER BY leaf
```

```cypher
// subtree under one heading (breadth-first over HAS_SECTION)
MATCH (s:Section {concept_id:'Alpha#Alpha'})-[:HAS_SECTION*1..3]->(d)
RETURN d.concept_id AS id, d.level AS level ORDER BY level, id
```

```cypher
// walk up instead, when you start from a deep heading
MATCH (s:Section {concept_id:'Alpha#Alpha#Parameters'})-[:PARENT_SECTION*1..3]->(p)
RETURN p.concept_id AS parent, p.level AS level ORDER BY level DESC
```

```cypher
// headings carrying a link or an image: the reference is scoped to that section
MATCH (s:Section) WHERE s.text CONTAINS '!['
RETURN s.concept_id AS section, left(s.text, 80) AS text
```

## 5. Chunks and retrieval

```cypher
// passage search — retrieve the range, then open the note for context
MATCH (c:Chunk) WHERE c.text CONTAINS 'datum'
RETURN c.note_id AS note, c.concept_id AS chunk, c.text
```

```cypher
// chunk counts per section reveal over-long sections and missing structure
MATCH (s:Section)-[:HAS_CHUNK]->(c:Chunk)
RETURN s.concept_id AS section, count(c) AS chunks ORDER BY chunks DESC, section LIMIT 20
```

```cypher
// chunks keyed by an authored block id — the only chunk ids that survive editing around them
MATCH (c:Chunk) WHERE c.concept_id CONTAINS '#^'
RETURN c.concept_id AS id, left(c.text, 60) AS text
```

```cypher
// ordered reading of one section
MATCH (:Section {concept_id:'Alpha#Alpha#Parameters'})-[:HAS_CHUNK]->(c:Chunk)
RETURN c.ordinal AS ordinal, c.text AS text ORDER BY ordinal
```

`forced_splits` is a build-report number, not a query: non-zero means a chunk cap cut inside a block,
and the fix is an authored `<!-- kglite chunk -->` or a `^block-id`. `embed_text` is a property only if
`embed_text:` is declared — then `text_indexes: {Chunk: [embed_text]}` and `embed: {Chunk: embed_text}`
name it.

## 6. Facts from declared structure

```cypher
// table rows (node form): one property per column, named exactly as the header
MATCH (p:ApiParameter) RETURN p.name AS name, p.type AS type, p.default AS default ORDER BY name
```

A cell is text, so `0.0` comes back as the string `"0.0"`. Cast in the query if you need numbers.

```cypher
// rows of one table, scoped to its section
MATCH (:Section {concept_id:'Alpha#Alpha#Parameters'})-[:HAS_PARAMETER]->(p:ApiParameter)
RETURN p.name AS name, p.`source anchor` AS anchor ORDER BY name
```

```cypher
// procedures and their steps, in order
MATCH (pr:Procedure)-[:HAS_STEP]->(s:ProcedureStep)
RETURN pr.concept_id AS procedure, s.ordinal AS ordinal, s.text AS step
ORDER BY procedure, ordinal
```

```cypher
// callouts by kind — a corpus keeps its own vocabulary (versionadded, caution, …)
MATCH (n:Note) WHERE n.kind IS NOT NULL
RETURN n.kind AS kind, count(*) AS n ORDER BY n DESC, kind
```

```cypher
// code examples by language
MATCH (e:Example) RETURN e.lang AS lang, count(*) AS n, collect(e.concept_id)[0..3] AS samples
ORDER BY n DESC, lang
```

```cypher
// symbols relabelled by key_from_heading, with the signature split out
MATCH (s:ApiSymbol) RETURN s.qualified_name AS name, s.signature AS signature ORDER BY name
```

Only present when `key_from_heading:` is declared and the heading really is a symbol (it requires
`under_label:` and a `.` or `(` in the heading).

## 7. Tags and modelled tag families

```cypher
// tag hubs by size — the honest measure of "this tag means something"
MATCH (t:Tag)<-[:TAGGED]-(n)
RETURN t.id AS tag, count(n) AS uses ORDER BY uses DESC, tag
```

```cypher
// co-occurrence: which tags travel together
MATCH (a:Tag)<-[:TAGGED]-(n)-[:TAGGED]->(b:Tag)
WHERE a.id < b.id
RETURN a.id AS a, b.id AS b, count(DISTINCT n) AS together ORDER BY together DESC LIMIT 20
```

```cypher
// tag_labels: the family became a node, not a tag
MATCH (c:Chunk)-[:HAS_INTENT]->(i:Intent)
RETURN i.title AS intent, c.concept_id AS chunk, left(c.text, 60) AS text
```

```cypher
// one-word markers that stayed tags (per-chunk, not per-page)
MATCH (c:Chunk) WHERE 'warning' IN c.tags
RETURN c.concept_id AS chunk, left(c.text, 60) AS text
```

## 8. Attachments

```cypher
// images and files, with the size stat read at build time
MATCH (i:Image) RETURN i.path AS path, i.title AS title, i.mime AS mime, i.size_bytes AS bytes
ORDER BY path
```

```cypher
// who references which file, with alt text and section
MATCH (m)-[r:HAS_IMAGE|HAS_ATTACHMENT]->(f)
RETURN m.concept_id AS note, f.path AS file, type(r) AS type,
       r.alt AS alt, r.section AS section, r.ordinal AS ordinal
ORDER BY note, ordinal
```

```cypher
// missing files (a stub keeps the reference as written)
MATCH (n {missing: true}) RETURN n.path AS path, labels(n)[0] AS label
```

## 9. Health, staleness, what the graph carries

```bash
kglite okf status VAULT --graph G      # current (exit 0) / stale (exit 1)
kglite describe G                      # agent-oriented schema document
kglite describe G --types Chunk        # focused views: --types, --cypher, --connections
kglite skill G                         # skills carried in the graph
```

`okf status` reads no note; it stats the files a build would read and folds them into a fingerprint.
With `--graph` it compares against the stamp: `current`, or `stale` with both fingerprints.

## 10. Graph algorithms

Documented in the OKF guide and available on this build:

```cypher
CALL leiden() YIELD node, community
RETURN community, count(*) AS size ORDER BY size DESC
```

```cypher
CALL pagerank() YIELD node, score
RETURN node.concept_id AS id, score ORDER BY score DESC LIMIT 20
```

Node-level output lists every derived node too (chunks, steps), so filter by `file_path IS NOT NULL`
when you want notes only.

## 11. Python-only answers

```python
from kglite import okf

report = okf.validate("VAULT")            # same report the CLI prints
g = okf.build("VAULT", dialect="obsidian")  # explicit: okf.build defaults to the "okf" dialect
g = okf.open("VAULT", dialect="obsidian", cache="../out/cache.kgl")  # cached, cache kept outside
rows = g.cypher("MATCH (n) RETURN labels(n)[0] AS l, count(*) AS n")  # list of dicts
df = g.cypher("MATCH (n:Project) RETURN n.concept_id AS id", to_df=True)  # needs kglite[pandas]
body = okf.source("VAULT/Projects/Alpha.md")   # markdown body without frontmatter
okf.export(g, "OUT", source_root="VAULT")      # vault back out, manifest-guarded
```

`to_df=True` requires the pandas extra; the rest needs no runtime dependencies.
