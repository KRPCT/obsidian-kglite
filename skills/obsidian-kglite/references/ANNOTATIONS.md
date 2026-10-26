# Annotations: structure the prose cannot reach

A converted or hand-kept vault says things in sentences that no query can reach: which task pane
opens a dialog, what a paragraph is *for*, where one topic ends. Five annotations state those facts
in the note itself, in syntax Obsidian either renders normally or hides. **Nothing is rewritten**,
and an export writes every file back byte for byte.

They are read whether or not `structure:` is declared, but callouts, chunks and sections only become
*nodes* when the matching `structure:` rule exists.

## 1. Typed link — what this one link means

```markdown
[[Wells]]{opens-dialog} opens the annotation table.
```

- The brace sits directly after `]]`, holds no whitespace, closes on the same line.
- It outranks `heading_edges:` and the built-in heading ladder.
- It renders as the wikilink plus the literal text `{opens-dialog}`; that is expected.
- Normalisation matches frontmatter keys: `{opens-dialog}` → `OPENS_DIALOG`, so `{see-also}`,
  `{see_also}` and `{SEE_ALSO}` are the same type.

```cypher
MATCH (a)-[r:OPENS_DIALOG]->(b) RETURN a.concept_id AS from, b.concept_id AS to, r.section AS section
```

Use it when the sentence asserts a specific relation and the enclosing heading would type it wrongly.
For a neutral reference write `{LINKS_TO}` explicitly — more honest than letting a heading called
"Related" retype it.

## 2. Directive — a fact about this section

```markdown
### Annotation table

To open the **Annotation table** dialog, click the button on the **Wells** task pane.

<!-- kglite address: Data tree -> Wells | Task pane: Wells -> Annotations table -->
<!-- kglite documented_in: [[Wells]] -->
```

- A directive on a line of its own is cut out of every derived text and `embed_text`; retrieval sees
  only the prose, and Obsidian hides it.
- It states its key on the enclosing section (or on the note when it sits above the first heading, or
  when no `sections:` rule exists).
- A value naming wikilinks becomes **typed edges** (`UPPER_SNAKE(key)`); anything else becomes a
  property.
- A directive may not name reserved frontmatter keys, a property a derived node defines itself,
  `body`, `concept_id` or `file_path` — that is an error, not a warning.

```cypher
MATCH (s:Section) WHERE s.address CONTAINS 'Task pane' RETURN s.title, s.address
MATCH (s:Section)-[:DOCUMENTED_IN]->(n) RETURN s.concept_id AS section, n.concept_id AS doc
```

Use it for a fact that belongs to one section. A fact about the whole note belongs in frontmatter; a
fact nobody will query belongs nowhere.

## 3. Modelled tag — what kind of statement this is

```markdown
Use the import dialog to load a deviation survey. #intent/import-wells

The datum is not checked on import. #warning
```

```yaml
tag_labels:
  "intent/*": {label: Intent, edge: HAS_INTENT}
```

- `#intent/import-wells` becomes an `Intent` node with id `import-wells`, joined from the innermost
  derived node that holds the tag (usually a chunk).
- `#warning` stays a tag and lands in that chunk's own `tags` list.
- Both forms (inline and frontmatter `tags:`) feed the same hub, so a matched tag leaves the Tag hub
  entirely — but the text stays wherever it was written.

```cypher
MATCH (c:Chunk)-[:HAS_INTENT]->(i:Intent) RETURN i.title AS intent, c.concept_id AS chunk
MATCH (c:Chunk) WHERE 'warning' IN c.tags RETURN c.concept_id, left(c.text, 60)
```

Reach for `tag_labels:` when a family is a *kind of thing* the corpus has many of and queries by name
(`intent/…`, `task/…`, `product/…`). Leave a one-word marker as a tag.

## 4. Chunk boundary — where the topic ends

```markdown
The import validates the header row. #warning

<!-- kglite chunk -->

The datum is not checked on import. #warning
```

- `<!-- kglite chunk -->` closes the open chunk at that point and is not counted in `forced_splits`.
- Only a **top-level** marker counts. Inside a list item, a quotation or a table there is no chunk to
  close, and the build warns.
- The alternative is a `^block-id` on the paragraph, which also gives the chunk a stable id that
  editing around it cannot move.

```cypher
MATCH (:Section {title:'Annotation table'})-[:HAS_CHUNK]->(c:Chunk)
RETURN c.ordinal AS ordinal, c.concept_id AS chunk, left(c.text, 60) AS text ORDER BY ordinal
```

Why it matters: chunks are greedy, so a caution and the procedure it belongs to often pack into one
chunk, and `#warning` then marks both.

## 5. Synthetic heading — a heading the source never wrote

```markdown
### rmsapi.Project

<!-- kglite heading -->
**open(filename, readonly=False)**
```

- Promotes the paragraph's first line to a heading, level = enclosing level + 1 (max 6).
- A surrounding pair of `**` comes off the heading text and nothing else.
- From there it is a heading like any other: it derives a `Section`, is addressable as
  `[[Note#rmsapi.Project#open(filename, readonly=False)]]`, and feeds `key_from_heading:`.
- The body is untouched; only the tree a reader builds changes.

Use it for a converter that emitted bold signature lines where `####` belonged, without touching the
file.

## When an annotation did nothing

`kglite okf check VAULT --strict` reports all three silent failures:

- a `<!-- kglite heading -->` that promoted nothing (nothing below it, or a list, table or fence next);
- a `tag_labels:` rule no tag matched;
- a directive naming a key a note or derived node defines itself.

Three more failure modes are not warnings:

| Symptom | Cause |
| --- | --- |
| the brace appears in the note text and no edge got the type | a space before `{`, or the line ended before `}` — it stayed prose |
| `#warning` marks paragraphs that do not carry it | a chunk packed several paragraphs; add a chunk marker or a block id |
| a directive's key is null | an earlier directive on the same node already stated it (the last one wins, and the build warns) |

## Order of operations

1. Declare the rules first (`structure:`, `tag_labels:`, `heading_edges:`, `types:`) in
   `.kglite/vault.yaml`.
2. Annotate a handful of notes.
3. `check --strict`, then `build`, then run the query that should see the new fact.
4. Only then annotate at scale — each annotation is a promise that some query will read it.
