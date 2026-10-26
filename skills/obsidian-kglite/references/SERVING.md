# Serving a vault to an agent

Three surfaces, one graph. Pick the smallest one that answers the question.

| Surface | Command | State | Use when |
| --- | --- | --- | --- |
| one-shot | `kglite query G "…" --format json` | none | a single question |
| JSONL session | `kglite session G --format json` | one loaded graph | several operations on one graph |
| MCP server | `kglite-mcp-server --graph G` / `--vault VAULT` | long-lived, tools | another agent drives the vault |

## MCP server

```bash
kglite-mcp-server --graph .kglite-out/vault.kgl    # a fixed graph
kglite-mcp-server --vault VAULT                    # owns build + cache; rebuilds when stale
kglite-mcp-server --vault VAULT --vault-cache none # never cache inside the vault
```

Tools an agent gets: `graph_overview` (schema discovery), `cypher_query`, `ping`,
`reload_graph`, `expand_response`, `fetch_images`, and three file tools — `read_source`, `grep`,
`list_source` — sandboxed to the graph's own directory. A sibling `<basename>_mcp.yaml` with
`source_root: ./data` moves that sandbox; it does not add tools.

`--vault` boots through the same cached-open path as `okf open`, so a restart over an untouched vault
serves immediately.

## Skills carried in the vault

`.kglite/skills/*.md` become `:KgliteSkill` nodes. Frontmatter is the MCP skills dialect:
`name`, `description`, `references_tools`, `delivery`, then the body.

```bash
kglite skill G                # name + description of each skill
kglite skill G wells          # the body, raw markdown, byte for byte
kglite describe G             # the schema document indexes skills and recipes
```

A skill is methodology stored *inside* the graph, so the server can explain how to query itself. The
server merges graph skills with its own bundled and operator layers; `kglite skill` shows only what the
graph carries.

## Recipes carried in the vault

`.kglite/recipes/*.md`: one read-only Cypher per file.

```markdown
---
recipe: help
name: children_of
description: The articles directly below one article in the TOC.
recipe_description: Navigating the help hierarchy.
parameters:
  {type: object, properties: {id: {type: string}},
   required: [id], additionalProperties: false}
---
```

```cypher
MATCH (c:Article)-[:CHILD_OF]->(p:Article {concept_id: $id})
RETURN c.concept_id AS id, c.title AS title ORDER BY title LIMIT 50
```

Rules that decide whether a recipe loads:

- The statement must parse and must be read-only.
- It must **not** spell `LIMIT 200`. That number is the agent host's result cap: a result of more
  than 200 rows is refused outright, naming the count, so a caller always learns an answer was
  incomplete. A stored `LIMIT 200` would cap the result exactly at the threshold and the refusal could
  never fire. `LIMIT 50` and `LIMIT 201` are accepted; `LIMIT $rows` is always accepted; write
  `LIMIT 199` for "everything under the cap".
- `parameters` must name exactly the `$parameters` the statement uses. Every property without a
  default belongs in `required`; the root schema needs `type: object`, `properties`, `required` and
  `additionalProperties: false`. Omission binds a declared default; an explicit null stays null.
- `tool:` serves the query as a named MCP tool (`^[A-Za-z_][A-Za-z0-9_-]{0,63}$`, unique, fixed at
  boot). Expose a curated few — every named tool adds its description and schema to every
  `tools/list` response.
- A file that fails validation is skipped with a warning; its siblings still load.

Lifecycle while serving:

| Change | What exposes it |
| --- | --- |
| note content, `vault.yaml`, attachments | rebuild (with `--vault`, before the next tool call; `rebuild_graph` forces it) |
| skill body, description or routing | rebuild; re-resolved on the graph swap |
| recipe query, schema or description | rebuild **and restart** (catalogue is fixed at boot) |
| `tool:` add, remove or rename | rebuild **and restart** (router is fixed at boot) |

If a rebuild or reload fails, the previous graph stays active.

## Agent output budgets

`--format agent` is a byte budget over the whole serialized response — data, navigation, warnings,
metadata, escaping and follow-up actions. It is not a row cap. A Cypher `LIMIT`, an executor row limit
and the response budget are three separate boundaries.

```bash
kglite query G "MATCH (n:Evidence) RETURN n.id ORDER BY n.id" --format agent
kglite query G "…" --format agent --response-max-bytes 32768
kglite query G "…" --format agent --response-full
```

- Default 16,384 serialized bytes; minimum 4,096. `--response-max-bytes` and `--response-full` are
  mutually exclusive and valid only with `--format agent`; invalid controls are rejected before
  execution.
- A bounded response carries an executable `next.selected_value` action with a retained result id. Copy
  the action rather than constructing a cache path:

```bash
kglite response expand RESULT_ID --path /rows/37/0 --offset 0 --response-max-bytes 4096
kglite response purge --all
```

- Expansion reads the retained result and never re-runs the query, so it still works after the graph
  changes. Retention is best effort: a private per-user disk cache, 32 entries and 32 MiB globally,
  entries expiring ten minutes after creation.
- Coverage tells you what the result does *not* prove: `executed_rows`, any executor row limit, every
  literal limit in the parsed query, and `literal_limit_status`. `LIMIT 120` returning only write
  callers establishes something about those 120 rows, not about the database.

## JSONL session

```bash
kglite session .kglite-out/vault.kgl --format json
```

```text
{"op":"help"}
{"op":"describe","types":["Chunk"]}
{"id":"q1","op":"query","query":"MATCH (c:Chunk) RETURN count(c) AS n","format":"json"}
{"id":"w1","op":"write","query":"CREATE (:Task {id:'t1'})"}
{"op":"save"}
{"op":"exit"}
```

The session keeps one graph loaded; responses echo `id`. `{"op":"help"}` publishes the exact request
shape, so a driver that only has the pipe can discover the protocol. The JSONL contract stays complete
by default — a single request opts into bounded output with `"format":"agent"` plus
`"response":{"max_bytes":4096}` or `"response":{"mode":"full"}`.

## Writing through the CLI

```bash
kglite write G "CREATE (:Task {id:'t1', status:'todo'})" \
  --save --write-scope Task --git-sha abc123 --modified-by agent
```

`--write-scope` restricts a statement's writes to the listed node types (node writes are judged by the
node's stored type; relationship writes need at least one endpoint in scope). `--git-sha` and
`--modified-by` stamp provenance on auto-timestamp types.

A vault graph is regenerated from files, so writes into it are for scratch graphs and task graphs.
Change the vault through files or the Obsidian CLI, then rebuild.
