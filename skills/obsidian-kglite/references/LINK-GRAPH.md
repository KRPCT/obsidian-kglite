# Link-graph repair

An Obsidian graph is worth maintaining when links express durable relations between notes that
already exist — not when a tool manufactures a denser picture. The idea this file follows is
"repair links by strengthening existing canonical paths and avoiding duplicate concept notes"
(galaxy-dawn/claude-scholar's `obsidian-link-graph`). KGLite supplies what that idea lacked: a
measurement for every claim, before and after.

## Principles

1. **The graph is evidence, not a generator.** KGLite reports; a human or an explicit edit step acts.
2. **Repair, do not proliferate.** Strengthen an existing note, a folder note, or an index note. Never
   mint a second note for a concept that already has one — two stems, one concept, is the defect this
   discipline exists to prevent.
3. **Durable relations only.** "Both mention the same word" is not a relation. A table-of-contents
   relation, a prerequisite, an ownership, a documented-in — those are.
4. **Type discipline.** A neutral reference is `LINKS_TO`. Reserve `DEPENDS_ON`, `CITES`,
   `JOINS_WITH`, `RELATED`, `REFERENCES` for relations the prose actually asserts. The built-in
   heading ladder will mistype a plain reference as `DEPENDS_ON` because the heading happened to say
   "Dependencies".
5. **Links are cheap; review is not.** A proposal you cannot justify in one sentence with one query
   row is noise.

## Protocol

### 1. Snapshot

```bash
kglite okf check VAULT --json > .kglite-out/check-before.json
kglite okf build VAULT -o .kglite-out/before.kgl
```

### 2. Measure

Run in this order; each later number only means something against the earlier one.

```cypher
// orphans
MATCH (n) WHERE n.file_path IS NOT NULL AND NOT coalesce(n._provisional,false)
OPTIONAL MATCH (n)-[r]-(m) WHERE m.file_path IS NOT NULL AND NOT type(r) IN ['CONTAINS','TAGGED']
WITH n, count(r) AS d WHERE d = 0 RETURN n.concept_id AS id ORDER BY id
```

```cypher
// dangling links, with their sources
MATCH (m)-[r]->(n {_provisional: true})
RETURN n.concept_id AS missing, m.concept_id AS source, r.section AS section
```

```cypher
// hub inflation: tags used once are labels nobody shares
MATCH (t:Tag)<-[:TAGGED]-(n) RETURN t.id AS tag, count(n) AS uses ORDER BY uses ASC
```

```cypher
// degree ranking: bridges at the top, islands at the bottom
MATCH (n) WHERE n.file_path IS NOT NULL AND NOT coalesce(n._provisional,false)
OPTIONAL MATCH (n)-[r]-(m) WHERE m.file_path IS NOT NULL
WITH n, collect(type(r)) AS ts
WITH n, [t IN ts WHERE NOT t IN ['CONTAINS','TAGGED']] AS sem
WITH n, size(sem) AS degree
RETURN n.concept_id AS id, degree ORDER BY degree DESC, id LIMIT 20
```

### 3. Propose

A proposal is a row plus a sentence, and it needs two signals from different query families.

| Signal | Query family | Alone it only means |
| --- | --- | --- |
| shared neighbour | two-hop over `LINKS_TO` | both are linked from somewhere |
| shared tag | `Tag` co-occurrence | they share a word |
| unlinked mention | chunk text contains the title, no link | the prose already points there |
| folder sibling plus shared tag | `CHILD_OF` plus `TAGGED` | same neighbourhood, same word |
| same folder note | `CHILD_OF` to one folder note | the table of contents already groups them |

A shared tag **and** an unlinked mention is a link worth writing. A shared tag **and** a shared
neighbour is a link worth writing from the *hub* note, not from every pair.

Write the proposal down before editing:

```text
from: Projects/Alpha
to:   Projects/Beta
type: LINKS_TO
why:  the chunk "Consider Beta for the next pass" names Beta; both notes sit in Projects/; no link
      exists in either direction.
```

### 4. Validate

Reject the proposal if any of these hold:

- an edge of a different type already exists between the pair (you would retype a relation, not add
  one);
- the target is a stub you have not decided to write — dangling links are allowed, but *creating* one
  is a decision;
- the link needs an ambiguous stem (qualify folder-first instead of renaming);
- the source note is not canonical (it duplicates another note's concept);
- the change would rewrite human prose rather than append a link.

### 5. Apply

One note at a time, reversible:

```bash
obsidian read file="Alpha"
obsidian append file="Alpha" content="See [[Beta]] for the surface tie-in."
```

Or edit the file directly. Keep generated links in a clearly owned section — for example under
`## Related topics`, typed by `heading_edges:` — so an operator can audit them separately from
hand-written prose.

### 6. Re-measure

```bash
kglite okf build VAULT -o .kglite-out/after.kgl
kglite query .kglite-out/after.kgl '<the same orphan query>' --format json
```

The claimed direction must appear: orphan count down by exactly the notes you connected, no new
dangling link, no new duplicate stem. If it does not move, revert and report the null result. A
"repair" that changes the graph's shape without changing the measure was cosmetic.

## Anti-patterns

- **Mass auto-linking** on shared tags. It destroys the signal: once everything is linked, a link says
  nothing.
- **Concept sprawl**: creating `Alpha (project).md` beside `Alpha.md` because the stem was taken.
  Declare `id:` or rename; do not fork the concept.
- **Hub inflation**: tagging every note `#project` until the hub has four hundred members. A hub is
  useful only while it discriminates.
- **Prose rewriting**: turning a sentence into a table, or a table into prose, to make a query easier.
  Query what is there; changing the source is an authoring task with its own review.
- **Silent scope creep**: repairing links in folders nobody asked about. Report the finding and stop at
  the boundary.

## What a healthy vault looks like

- Every note reachable from a folder note or an index note within two hops.
- Dangling links are decisions, not accidents: each is either a note you intend to write or a typo you
  fixed.
- Tags are either hubs with several members or markers with a query behind them.
- `DEPENDS_ON` and friends appear only where the prose asserts them.
