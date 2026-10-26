---
name: vault-query-guide
description: How to query this vault. Read before writing Cypher against it.
references_tools: [cypher_query, graph_overview]
delivery: inline
---
# Querying this vault

This vault is served as a KGLite graph. Three facts decide most answers:

1. Notes carry `file_path`; sections, chunks, steps and table rows are derived and never do. Use
   `n.file_path IS NOT NULL` when you mean "a real note".
2. Hierarchy runs parent→child: `(note)-[:HAS_SECTION]->(top-level section)`, then
   `(section)-[:HAS_SECTION]->(child section)`. Match `(s:Section)` directly for every section.
3. Passage questions belong to `Chunk`, not to the note.

## Recipes

Passage search:

```cypher
MATCH (c:Chunk) WHERE c.text CONTAINS $needle
RETURN c.note_id AS note, c.concept_id AS chunk, c.text LIMIT 199
```

Outline of one note:

```cypher
MATCH (n {file_path: $file})-[:HAS_SECTION]->(s:Section)
RETURN s.title AS section, s.level AS level, s.ordinal AS ordinal ORDER BY level, ordinal
```

Never write `LIMIT 200`: that is the host result cap, and a query that caps at the threshold hides
truncation. Use `LIMIT 199` or a parameter.
