# Sources, versions, and what is actually verified

Everything in this skill is either **verified** (run against a fixture vault with the pinned tool
version, output quoted) or **documented** (stated by the upstream docs, not exercised here). Nothing is
inferred from naming.

## Pinned versions

| Component | Version | Note |
| --- | --- | --- |
| kglite | 0.21.2 | the version every command and query in this skill was run against |
| vault format | `kglite_vault: 1` | additive keys keep the version at 1 |
| Obsidian | 1.14.5 | desktop app that ships the `obsidian` CLI used in the repair path |
| Python | 3.11 | fixture run; the package publishes CPython wheels |

## Primary sources

| Topic | Source |
| --- | --- |
| vault format (normative) | https://kglite.readthedocs.io/en/latest/reference/vault-format.html |
| CLI surface | https://kglite.readthedocs.io/en/latest/operators/cli.html |
| vault ingestion / Python API | https://kglite.readthedocs.io/en/latest/python/guides/okf.html |
| bounded agent responses | https://kglite.readthedocs.io/en/latest/operators/agent-responses.html |
| MCP server | https://kglite.readthedocs.io/en/latest/operators/mcp-server.html |
| getting started / graph API | https://kglite.readthedocs.io/en/latest/python/getting-started.html |
| worked help-vault tutorial | https://kglite.readthedocs.io/en/latest/python/guides/help-vault.html |
| package | https://pypi.org/project/kglite/ |
| Obsidian CLI (inlined) | https://github.com/kepano/obsidian-skills (MIT, (c) Steph Ango) |
| Obsidian markdown (inlined) | https://github.com/kepano/obsidian-skills (MIT, (c) Steph Ango) |
| link-repair philosophy (attributed) | https://github.com/galaxy-dawn/claude-scholar (`obsidian-link-graph` / `LINK-REPAIR.md`) |

## Verified here

Run on a fixture vault (5 notes, 2 folders with a folder note, frontmatter typed edges, typed link,
table rows, procedure, callout, fenced example, image, one dangling link):

```text
kglite okf check      → files scanned 5, concepts 5, 0 errors, 1 warning (dangling link), exit 0
kglite okf build      → report on stderr, path on stdout
kglite okf status     → "current <fingerprint> <graph> built from <root>", exit 0
kglite okf open       → writes .kglite/graph.kgl + .lock + .lock-owner; cache excluded from the scan
kglite query          → json / agent envelopes; one statement per call (two statements → [])
kglite describe       → XML schema document
CALL leiden(), CALL pagerank()  → both execute
okf.validate/build/open/export/source, graph.cypher  → all exercised from Python
```

Specific behaviours verified, because they change how you write a query or a script:

- `Section.path` exists as a list of heading titles, so `path IS NOT NULL` is **not** an attachment
  filter.
- A table header with a space becomes a property name that needs backticks in Cypher.
- A table cell is text: `0.0` comes back as `"0.0"`.
- `HAS_SECTION` from a note reaches only top-level sections; children hang off the section.
- A note with no semantic edge is found with the `file_path`-based orphan query, not with a bare
  `OPTIONAL MATCH … WHERE type(r)` (that drops null rows).
- Export re-files a note under `<Label>/` when folder and label disagree, and loses the structure
  block because `vault.yaml` is not written.
- Querying a label or relationship type the graph lacks produces a **warning**, not an error, and zero
  rows.

## Documented only

These are stated by the docs and used as guidance here, but were not exercised on this machine:

- `.kglite/recipes/` validation outcomes (the `LIMIT 200` refusal, schema equality checks, `tool:`
  registration) — the rules are quoted from the spec, not reproduced.
- MCP server tool behaviour (`graph_overview`, `read_source`, `grep`, `list_source`, image fetching,
  `reload_graph`, `expand_response`) — the server was not booted here.
- `okf.fingerprint` and `okf.rebuild_if_changed` as Python entry points (the equivalent `okf status`
  was verified from the CLI).
- Embedding carry-across, `chunk_hash` matching, `to_df=True`, and semantic search — no embedder was
  bound.
- `--response-max-bytes` / `response expand` output shape (only the unbounded agent envelope was
  observed).

If a task depends on one of those, run it once before promising it.
