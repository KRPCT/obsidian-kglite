# Vault format, condensed

Normative source: KGLite Vault Format (https://kglite.readthedocs.io/en/latest/reference/vault-format.html).
Section numbers below are that document's. The dialect string is exactly `obsidian`; it is **not**
an alias for `loose`. The format version is `kglite_vault: 1`.

Contents

1. What is and is not interpreted
2. Labels, folders, folder notes
3. Identity
4. Frontmatter and the typed-edge rule
5. Links
6. Tags
7. Stubs, comments, block ids, callouts
8. Directives
9. Attachments
10. `.kglite/vault.yaml`
11. `structure:` and derived nodes
12. Skills and recipes carried in the vault
13. Build report and validation classes
14. Rebuild, provenance, cache
15. Export
16. Modelling guide for converters

---

## 1. What is and is not interpreted

A vault is a directory tree of UTF-8 markdown. The files are canonical; the graph is a derived,
rebuildable lens. **A build never writes into the vault.** Writing markdown from a graph is a
separate, explicit operation (export).

Only `.md` files become notes. A non-`.md` file becomes a node only when a note references it.
Unreferenced files are not in the graph.

Never interpreted: HTML tags (`<a href>`, `<img src>`, `<table>` are prose), canvas files,
Dataview inline fields (`key:: value`), Logseq properties. Heading-level splitting does not
happen unless `structure:` asks for it.

Ignored paths, whole subtree: any directory starting with `.` (`.obsidian`, `.trash`, `.git`,
`.kglite` itself), `node_modules`, `target`, `__pycache__`, `venv`, `env`, `site-packages`, plus
`skip_dirs:`. A single file opts out with `kg_skip: true`.

`index.md` and `log.md` are ordinary notes in this dialect (in `okf` and `loose` they are folder
metadata and skipped).

## 2. Labels, folders, folder notes

One primary label per note, the first rung that yields a non-empty value:

1. frontmatter `type:`
2. `default_label:` from `vault.yaml`
3. the note's **top-level folder name**, verbatim (no singularising, no case change)
4. `Note`

`label_from: folder` moves rung 3 to the front, so a folder move relabels even a note that
carries `type:`.

Every directory becomes a `Folder` node with `CONTAINS` edges (opt-out at build time). A vault's
first folder level is therefore both a label and a Folder node — intentional redundancy.

**Folder notes.** `X.md` beside `X/`, or `X/X.md`. The note takes the folder's place and no
`Folder` node is created for `X/`; notes inside `X/` join it by `folder_notes.edge` (default
`CHILD_OF`, child → parent). This is how a table of contents is expressed on disk. Declaring
both spellings for one directory is an error.

Trap: a folder note is labelled from **where its folder sits**, not from inside. A folder note at
the vault root is therefore `Note` unless it declares `type:`. The fix is one `type:` per
root-level folder note.

`X/index.md` is **not** a folder note. A tree whose section pages are all `index.md` gets no
folder notes at all and collides on the stem `index`.

## 3. Identity

| Field | Rule |
| --- | --- |
| id | frontmatter `id:` → filename stem |
| title | frontmatter `title:` → `name:` → the body's first heading (any level) → stem |
| file_path | vault-relative, forward-slashed |

The id is the node's `concept_id` and the target of every link. Ids are deliberately not
path-derived: moving a note must not change its identity (embeddings, `.kgl` snapshots and
external references key on it).

Stem collisions: if two or more notes share a stem and neither declares `id:`, **every**
colliding note falls back to its path minus `.md` (`projects/alpha`, `archive/alpha`), and the
collision is reported as an **error**. The same fallback settles a duplicate declared `id:` and a
fallback that collides in turn. Case-insensitive collisions (`Foo.md` / `foo.md`) are warnings on
every host, because the vault must open on Linux, macOS and Windows.

This is the most common error in real vaults that keep a `README.md` in every folder: one
26-note vault produced `14 notes resolve to id README`. Either declare `id:`, rename the stems,
or accept path-relative ids and query `concept_id` accordingly.

## 4. Frontmatter and the typed-edge rule

YAML 1.2 between `---` fences at the first byte. Unparseable YAML is an error, but the note still
becomes a node with no properties.

| Key | Meaning |
| --- | --- |
| `id` | node id |
| `type` | label |
| `title` | display title (stored as `title`) |
| `aliases` | extra names for link resolution (stored as a list) |
| `tags` | tag hub membership (stored as a list) |
| `kg_skip` | `true` excludes the file |
| `parent` | additional parents; emits the folder-note edge type |
| `cssclasses` | ignored entirely |

Every other key becomes a property, or edges under the typed-edge rule.

Typing: scalars keep their YAML type; sequences become native lists (unlike `okf`/`loose`, which
keep JSON strings); nested maps flatten to dotted keys (`metadata.source`); a top-level string
matching `YYYY-MM-DD` becomes a date and RFC 3339 becomes a UTC datetime — quoting does not stop
inference, only `types:` does. Inference does not reach inside a sequence.

**Typed-edge rule.** If a key's value is a wikilink string, or a list in which every element is a
wikilink string, the key becomes edges of type `UPPER_SNAKE(key)` and **no property is stored**. A
list mixing wikilinks and plain strings stays a plain list property; the rule never splits a key.
`parent:` is the one reserved key that follows this rule.

```yaml
depends_on: "[[Seismic interpretation]]"
see_also: ["[[Faults]]", "[[Horizons]]"]
```

## 5. Links

| Written | Meaning |
| --- | --- |
| `[[Note]]` | link to Note |
| `[[Note|display text]]` | same link; with `structure:` the text is stored as the edge's `label` |
| `[[Note#Heading]]`, `[[Note#A#B]]`, `[[Note#^block-id]]` | link with `anchor`; with `structure:` retargets to the derived node |
| `[[Label/Name]]` | folder-qualified, for an ambiguous stem |
| `[[Note]]{type}` | typed link; the brace outranks every heading rule |
| `[text](path.md)`, `[text](path.md "EDGE_TYPE")` | path link; the title is the edge type |
| `[text](file.ext)` | attachment reference, link text is the alt |
| `[text](#frag)`, `[text](mailto:…)`, `[text](sub/dir/)` | names no node: silent no-op |
| `![[Note]]` | embed → `EMBEDS` edge |
| `![[img.png]]`, `![alt](img/x.png)` | attachment, never a note link |
| `[![alt](thumb.png)](full.png)` | two references: thumbnail and link target |
| `https://…` | external `Source` node keyed by URL |

Regions **not** scanned: fenced code blocks, `%%comments%%`, `<!-- kglite … -->` directives, inline
code spans. Everything else is scanned, including indented code, HTML blocks and heading lines.
To keep text from being read, write `\[\[` for a literal `[[`.

A `[[wikilink]]` stays on one line (as in Obsidian). The text half of `[…](…)` may be hard-wrapped.
Percent-decoding applies to `[text](…)` and `![alt](…)` targets, never to wikilink names.
Absolute filesystem paths (`C:/…`, `\\server\share`, `~/…`, `file:…`) and `../` climbs above the
vault root are **errors**, not links. A leading `/` is vault-root-relative and legal.

Resolution ladder (first rung matching exactly one note): exact id → filename stem → some note's
`aliases:` → normalised slug (case-insensitive, `_` and `-` equivalent) → `title` → otherwise a
stub. A trailing `.md` is stripped first. A target containing `/` is tried as a vault-relative id,
then relative to the linking note.

Edge type for a body link, first rung that applies:

1. `{type}` written straight after `]]`
2. explicit link title that looks like a type — `[x](y.md "JOINS_WITH")`
3. `heading_edges:` matching the enclosing heading in full, case-insensitively
4. the built-in heading ladder, matched as a **substring** of the enclosing heading:
   `citation` → `CITES`, `join` → `JOINS_WITH`, `reference` → `REFERENCES`, `related` → `RELATED`,
   `depend` → `DEPENDS_ON`
5. `LINKS_TO`

The heading ladder classifies text; it does not prove semantics. A neutral reference under a
heading containing "depend" becomes `DEPENDS_ON` even when the source never asserted a
prerequisite. Use `[[Target]]{LINKS_TO}` for source-neutral references, and keep distinct source
relations distinct — a table of contents, a breadcrumb, a GUI path, a related-topic link, API
index membership, symbol ownership and an execution prerequisite are not interchangeable.

Edge properties: `section` (enclosing heading text, verbatim, absent above the first heading);
`anchor` (fragment without `#`, nested paths keep inner `#`s); `label` (display text, only when
`structure:` is declared). Two links from one note to one target are two edges when they differ in
`section`, `anchor` or `label`, and one otherwise.

The `{type}` suffix must follow `]]` with nothing between, hold no whitespace, close on the same
line, and normalise like a frontmatter key (`{see-also}` → `SEE_ALSO`). A failing brace stays prose
and the build warns. `[[Note]] #tag` is a tag, not a type. `![[Note]]{x}` is an embed: type
`EMBEDS`.

## 6. Tags

Both `tags:` in frontmatter and inline `#tag` feed one `Tag` hub per distinct tag, joined by
`TAGGED`. Identity is case-insensitive (`#Seismic` and `#seismic` are one tag, held under the
lowercased id and titled with the most-used casing).

Inline extraction skips fenced code, inline code spans, a `#` inside a URL or wikilink anchor, and
a line-initial `#` followed by a space (a heading — but a `#tag` inside a heading's text is still a
tag). A tag name runs over letters, digits, `_`, `-`, `/`, and must contain at least one letter
(`#2026` is not a tag).

With `structure:`, every inline tag is also written into a `tags` list on the innermost derived node
whose range contains it, which is why a one-word marker becomes selectable per paragraph:
`MATCH (c:Chunk) WHERE 'warning' IN c.tags`.

`tag_labels:` turns a prefix family into nodes:

```yaml
tag_labels:
  "intent/*": {label: Intent, edge: HAS_INTENT}
```

`#intent/create-grid` then mints an `Intent` node with id `create-grid` and an edge from the
innermost derived node. Rules: the pattern is `<prefix>/*` only; both `label` and `edge` are
required; longest prefix wins; a tag that is only the prefix stays an ordinary tag; a rule no tag
matched is a warning. A matched tag leaves the Tag hub but stays in the frontmatter list and in the
derived node's `tags` property.

## 7. Stubs, comments, block ids, callouts

- An unresolved target becomes a `_provisional: true` stub, label `Concept`, keyed by the
  unresolved name. Stubs are counted in the report and never exported as files.
  `MATCH (n {_provisional: true})` is the dangling-link query.
- `%%…%%` hides text from the reader, inline or as a block; never scanned, still part of the stored
  body.
- `^id` at the end of a paragraph (or on its own line after a table, list or fence, or on a bullet)
  names a block; `[[Note#^id]]` reaches exactly that block. Charset: Latin letters, digits, dashes.
  `^my_id` is text, not a block id.
- A callout is a blockquote whose first line is `> [!type]± Title`. The kind is lowercased and
  **arbitrary** (`[!versionadded]` is legal and is not folded into `note`); `+`/`-` is folding, not
  part of the kind; callouts nest; a callout's body is scanned normally.

## 8. Directives

`<!-- kglite <key>[: <value>] -->` on a line of its own is an instruction to the reader. Obsidian
hides it; KGLite cuts it out of every derived text and `embed_text`, so retrieval sees only prose.

| Directive | Meaning |
| --- | --- |
| `<!-- kglite chunk -->` | close the open chunk here (top-level marker only) |
| `<!-- kglite heading -->` | promote the next paragraph's first line to a heading (level = enclosing + 1, max 6) |
| `<!-- kglite <key>: <value> -->` | state a key on the enclosing section (or on the note above the first heading, or without `sections:`) |
| `<!-- kglite <key> -->` | states nothing; the build warns |

A value naming wikilinks becomes typed edges; anything else becomes a property, typed as frontmatter
would be, with `types:` overriding. Inline value grammar is looser than YAML: a bare `[[Target]]`
needs no quotes, and a value YAML would read as a mapping (or refuse) is taken as raw text.

A directive may not name: reserved frontmatter keys, properties a derived node defines itself, the
note's `body:` property, `concept_id`, `file_path`. Each is an **error** naming the key.

`<!-- kglite heading -->` is for a converter that emitted a bold signature line where a heading
belonged. It changes only the tree a reader builds; the file still renders as before and exports
byte for byte.

## 9. Attachments

Accepted: `![alt](rel/path.png)`, `![[image.png]]`, `![[image.png|alt]]`, `[text](rel/x.pdf)`. The
leading `!` says how a renderer displays it, not whether the vault holds it. A target with a URI
scheme, an in-page anchor or a directory link names nothing.

Resolution: note-relative → vault-root-relative → unique filename anywhere in the vault. The stored
value is always the vault-relative resolved path. A filename occurring twice does not resolve on the
third rung.

One node per distinct resolved file. Label is `Image` for png/jpeg/gif/webp, otherwise
`Attachment` (so SVG and TIFF are Attachments and are not delivered as images). The node's id field
is `path`; `mime`, `size_bytes` and `mtime` come from `stat`; an Image also carries `text` (distinct
alts plus the titles of using notes). Edges `HAS_IMAGE` / `HAS_ATTACHMENT` carry `alt`, `section`,
`ordinal`. Bytes are never read at build time, so cost is independent of image volume and the type
comes from the extension.

A missing target becomes `_provisional: true` with `missing: true`. An ambiguous bare filename
resolves to nothing and the warning names the candidates.

## 10. .kglite/vault.yaml

Optional. Applied on every build and re-applied on every rebuild; with carried embeddings it is the
one state that survives a rebuild. An unknown top-level key, an unknown key inside `structure:`, an
unknown `kglite_vault` version, or a wrong-shaped value **fails the build** — the file is a hard
compatibility boundary, and a vault whose file stopped parsing would silently lose its labels, hubs,
indexes and embed targets.

| Key | Shape | Meaning |
| --- | --- | --- |
| `kglite_vault` | int | format version, `1` |
| `default_label` | string | rung 2 of the label ladder |
| `label_from` | `type` or `folder` | which rung leads |
| `body` | string | property name for prose, default `body` |
| `skip_dirs` | list | extra pruned directories |
| `folder_notes` | object | `edge` (default `CHILD_OF`), `direction` |
| `hubs` | object | list-valued key → hub nodes |
| `tag_labels` | object | tag prefix family → nodes |
| `heading_edges` | object | heading text → edge type, merged over the built-in ladder |
| `types` | object | declared property types: string, int, float, bool, date, datetime, list |
| `indexes` | object | equality, `{range: prop}`, `{composite: [..]}` |
| `text_indexes` | object | BM25 lexical indexes |
| `ontology` | mapping | passed to the ontology API verbatim |
| `embed` | object | which text property to embed per label |
| `structure` | mapping | derived nodes (see §11) |
| `edge_defaults` | object | constant per-type edge properties |
| `export` | object | `edge_tables:` what the exporter writes as a table |

Hubs: a scalar joins no hub; if a hub key is also wikilink-valued, the typed-edge rule wins and the
clash is a warning. A redeclaration changes only what it names.

`types:` overrides inference but does not convert afterwards: a value that will not coerce is left as
written and warned about. `concept_id` is never retyped.

Which property holds the id depends on the node kind. This table saves a silently empty index:

| Node | Id property |
| --- | --- |
| a note (any label) | `concept_id` |
| a `Concept` stub | `concept_id` |
| a hub node (Tag and every `hubs:` entry) | `id` |
| a `Source` node | `id` |
| a `Folder` node | `id`, holding the vault-relative directory path |
| an `Image` or `Attachment` | `path` |
| a `structure:`-derived node | `concept_id` |

`indexes:`, `text_indexes:` and `embed:` may name things the vault does not carry yet: a warning,
never an error.

## 11. structure: and derived nodes

No default and no heuristic. Without the block a note is one node with one body; a vault that never
had it builds exactly as before.

| Rule | Node(s) | Id |
| --- | --- | --- |
| `sections:` | one per heading | `Note#A#B` (heading path joined by `#`) |
| `chunks:` | greedy-packed leaf blocks | `parent~chunk<n>`, or `Note#^block-id` |
| `callouts:` | one per callout (`kind`, `title`, `fold`, `text`) | `…~note<n>` |
| `code_fences:` | one per qualifying fence (`lang`, `code`, `caption`) | `…~example<n>` |
| `ordered_lists:` | container plus steps | `…~list<n>`, `…~list<n>~step<m>` |
| `tables:` | one node per row, or one edge per row with `edges: true` | `<section>~<key value>` |
| `key_from_heading:` | relabels a Section that is a symbol | same node, new label plus `qualified_name` / `signature` |

Stability: only **section ids and block-id ids** survive editing around them. A `~chunk<n>` id
renumbers when a paragraph is inserted above it, and every id under a heading changes when the
heading is renamed. Where an id must survive, write a `^block-id`; where an embedding must survive,
`chunk_hash` carries it across by `(label, chunk_hash)` when exactly one old node of that label
carries the hash.

`sections:` properties: `title`, `level`, `ordinal`, `path`, `note_id`, `text` (verbatim body from
after the heading to the next same-or-higher heading, minus directives), inherited properties, and
whatever directives under it state. Edges: `edge` (note→top-level, section→child), `parent`
(child→parent), `next` (consecutive siblings). Duplicate heading text gets `~2` and a warning:
Obsidian can link only the first, and so can this spec.

`chunks:` packs leaf blocks (paragraphs, list blocks, fences, tables, quotations) greedily to
`max_words` / `max_chars`; a section boundary always closes a chunk. An oversized block splits at its
own boundaries (list items, then line ends), and the report counts `forced_splits` — a non-zero count
means the caps cut blind and the source wants an authored break. `<!-- kglite chunk -->` closes a
chunk deliberately; a paragraph ending in a block id becomes a chunk of its own keyed `Note#^id`.
Properties: `text`, `ordinal`, `chunk_hash`, `note_id`, `section_id`.

`tables:` is a list of rules matched by an `under_heading` regex. Node form: one node per body row,
columns become properties named by header text as written (a blank header names no property and its
cells drop); the key column is `key_column:` or the first; a duplicate or empty key keys on position
`~row<n>` and warns. Edge form (`edges: true`): one edge per row from the note to the first wikilink
column (or `key_column:`), every other column becomes a string edge property, plus `section`,
`anchor`, `label`, `row`.

`key_from_heading:` gates on `under_label:` **and** a `.` or `(` in the heading; both are required
because the shape is cheap to match by accident. The default `when_matches` is a dotted name
optionally with call parentheses and a `→` return annotation.

`inherit:` copies frontmatter properties onto every derived node (it may not name reserved keys or
properties a derived node defines itself). `embed_text:` materialises a template with `{title}`,
`{section_title}`, `{heading_path}`, `{text}`, `{id}`.

Declaring `structure:` also turns on the `label` edge property for displayed link text. There is no
separate switch.

## 12. Skills and recipes carried in the vault

`.kglite/skills/*.md` become `KgliteSkill` nodes; the frontmatter dialect is that of an MCP skills
directory: `name`, `description`, `references_tools`, `delivery`, then the body.

`.kglite/recipes/*.md` become `KgliteRecipe` nodes: one read-only Cypher per file, frontmatter
`recipe` (group id), `name`, `description`, optional `recipe_description`, `parameters` (JSON
Schema), optional `tool:`. The body is a fenced `cypher` block.

Recipe rules: must parse, must be read-only, must **not** spell `LIMIT 200` — that is the agent-host
result cap, equality with it is refused, `LIMIT 199` means "everything under the cap", and
`LIMIT $rows` is always allowed. `parameters` must name exactly the `$parameters` the statement
uses; the root schema needs `type: object`, `properties`, `required`, `additionalProperties: false`.
`tool:` registers a named MCP tool, matched by `^[A-Za-z_][A-Za-z0-9_-]{0,63}$`, unique, fixed at
boot.

A file that fails validation is skipped with a warning; its siblings still load.

Lifecycle while serving: note content needs a rebuild (with `--vault` the watcher rebuilds before the
next tool call); skills re-resolve on the graph swap; a recipe query, schema or description change
needs a **restart** because the catalogue is fixed at boot; a `tool:` add, remove or rename needs a
restart because the router is fixed at boot.

## 13. Build report and validation classes

Every build produces the same structured report. `okf.validate(path)` returns it without keeping the
graph; `kglite okf check <dir>` prints it and sets the exit code; `--json` gives
`{ok, strict, counts, errors, warnings}`. `--strict` promotes warnings to errors.

The report carries: files scanned, notes, nodes per label, edges per type, folder notes, dangling
links, missing and ambiguous attachments, index and text-index and skill and recipe counts,
`forced_splits`, `embed:` targets, and two classified lists.

**Errors** mean the vault does not meet the spec: unparseable frontmatter (the note still becomes a
node), a reserved key of the wrong shape, an id collision, two folder notes for one directory, an
absolute or escaping path in the body or in a typed-edge key, a `vault.yaml` the schema refuses, an
ontology the API refuses, a directive naming a forbidden key.

**Warnings** are legitimate in a real vault: a dangling link, a fragment naming a missing heading, a
duplicate derived id, a table row with an empty or duplicate key, an edge table with no target
column, a `structure:` rule that matched nothing, `<!-- kglite -->` with no key, a `chunk` marker in
a non-top-level position, a directive with no value, a key stated twice on one node, an
`edge_defaults` clash, a missing or ambiguous attachment, a case-insensitive id collision, an alias
clash, a hub key the typed-edge rule took, a value that does not match its declared type, a
declaration naming something the vault does not carry, a skipped skill or recipe file, a
`vault.yaml` under the wrong dialect.

The report proves format validity, not source fidelity or answer completeness. Test those separately:
inventory every source member with path, size and SHA-256; compare rendered content; assert
source-backed expected labels, properties and edges rather than non-zero counts; and test answers with
decisive context present.

## 14. Rebuild, provenance, cache

Five stamps: `source_root`, `source_fingerprint` (a 64-bit summary of relative path, size and mtime
of every file read), `source_dialect`, `source_build_version`, `source_options`.
`okf.fingerprint(dir)` recomputes the fingerprint with a stat pass; `okf.rebuild_if_changed(graph)`
returns `None` when unchanged and a new graph otherwise, carrying vectors across by `(label, id)`.

`okf.open(dir)`, `kglite okf open` and the MCP server's `--vault` do the whole loop: load the cache,
compare the fingerprint, rebuild only if it moved, write the result back. The default cache is
`VAULT/.kglite/graph.kgl`; `--cache PATH` / `cache=` relocates it, `--cache none` / `cache=False`
disables it.

Cache misses, each rebuilding silently: absent or unreadable, vault moved or copied, built by another
kglite version, built with other option knobs, no dialect stamp. A cache problem never fails an open;
an unwritable cache costs one more rebuild.

Caveats worth knowing: mtimes compare as whole seconds, so a same-second rewrite of equal length
reads as unchanged; and the stamp does not record which embedder produced the vectors, so swapping
models reuses old vectors until the notes behind them change.

## 15. Export

`okf.export(graph, dir)` and `kglite okf export G OUT --source-root VAULT` target this dialect only.

- A node with `file_path` becomes a file; a synthesized node never does. A graph with no
  `file_path` anywhere: every node becomes a file.
- File path is preserved when the top-level folder still matches the label; otherwise the note is
  re-filed under `<Label>/`. The stem is preserved, because a stem is the link namespace — renaming
  after the title dangles every `[[wikilink]]` that spells it.
- `type:` is never emitted (the folder carries the label). `id:` is emitted only when it differs from
  the stem. `title:` only when the next import would not recover it.
- Values: keys sorted, dotted keys expanded, lists as YAML sequences, dates as ISO strings, points as
  WKT, strings quoted when YAML would otherwise read something else (including `[[wikilinks]]`).
- Edges become `lower_snake(TYPE): ["[[Target]]"]` frontmatter lists, except edges whose target is
  not a file (CONTAINS, TAGGED, HAS_*) and edges the body already states with the same type.
- `.kglite/export-manifest.json` records a SHA-256 per file the export wrote. On the next run a file
  whose hash differs (human-edited), or that is missing from the manifest (written by somebody else),
  is **refused** unless `--force`. Deletion happens only for manifest-owned files with matching
  bytes. Identical output is not rewritten, so an unchanged export moves no mtimes.
- Determinism: the same graph twice is byte-identical.

Declared losses: (1) edge properties for types not declared as edge tables; (2) attachment bytes
unless `--source-root` names the origin; (3) synthesized nodes; (4) `.kglite/vault.yaml` — hubs,
indexes, embed targets and `heading_edges` retyping all vanish, so copy that file yourself; (5)
`types:` survives only where inference agrees; (6) a re-filed note resolves note-relative references
from its new location.

`export.edge_tables` is the only prose an export ever adds: the table under that heading is owned by
the exporter and rewritten whole, which is what makes a second export a fixed point.

## 16. Modelling guide for converters

Frontmatter is the node, headings are the sections, `^blockid` is the citable unit.

| Source has | Emit | Graph gets |
| --- | --- | --- |
| hierarchy or table of contents | folders plus folder notes (`X.md` beside `X/`) | `CHILD_OF` chain, labels from folders |
| sections within a page | headings, one level per depth | `Section` plus `PARENT_SECTION` and `NEXT_SECTION` |
| a citable passage | paragraph ending in `^id` | `Chunk` keyed `Note#^id` |
| an ordered procedure | numbered list | `Procedure` plus `ProcedureStep` and `NEXT_STEP` |
| parameters, fields, columns | GFM table under a named heading | one node per row |
| notes, warnings, version remarks | callouts `> [!versionadded] Title` | `Note` with `kind`, `title`, `text` |
| code samples | fenced block with the language | `Example` with `lang`, `code` |
| typed relations | `key: ["[[A]]", "[[B]]"]` | `KEY` edges |
| relations with attributes | edge table under a declared heading | edges carrying properties |
| what a link means in prose | `[[Target|the words you would have written]]` | edge `label` |
| categorical facets | list-valued keys plus `hubs:` | hub nodes and edges |
| images and downloads | note-relative references, files copied in | `Image` / `Attachment` |
| a heading that is a symbol name | `key_from_heading:` with `under_label:` | relabelled section plus `qualified_name` |
| a fact about one section | directive under that heading | property on the `Section` |
| provenance constant per edge type | `edge_defaults:` | property on every edge of the type |

Anti-patterns: one file per tiny record; raw HTML tables and definition lists; admonitions flattened
into paragraphs or folded into `note`; unlabelled fences when the language was known; JSON-encoded
lists; nested frontmatter maps; `type:` on every file when the folder already says it;
`default_label:` in a vault whose folders are its labels; absolute paths and `../` climbs; SVG as an
image; duplicate heading text; `[`, `]`, `|` or `#` inside a linked heading.

Conversion loop: convert a fifty-page sample → `check --strict` → read per-label counts against what
the sample holds (a rule that matched nothing is a warning and the fastest defect) → reconcile against
a source inventory and explicit expected facts → fix the converter, not the generated vault → run the
whole corpus with `--strict` in the converter's own test suite.

