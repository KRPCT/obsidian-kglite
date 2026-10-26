# obsidian-kglite

An agent skill that turns an Obsidian vault into a queryable [KGLite](https://kglite.readthedocs.io/)
knowledge graph — and then answers questions the vault cannot answer by eye.

- **Measure**: orphan notes, dangling links, duplicate stems, hub inflation, which section mentions
  what, which table row carries which fact.
- **Repair**: act on those measurements with evidence, then re-measure.
- **Serve**: expose the graph to another agent over MCP, with skills and parameterised recipes that
  live inside the vault.

The vault stays the source of truth. The graph is a rebuildable lens, and building it never writes into
the vault.

## Requirements

| Component | Version | Why |
| --- | --- | --- |
| Python | 3.10+ | the scripts and the API |
| kglite | 0.21.2+ | the graph engine, `okf` vault dialect, CLI |
| Obsidian | 1.14+ | only for the CLI-based repair path |

```bash
uv tool install kglite==0.21.2     # CLI
# or, in a project venv:
uv pip install kglite==0.21.2
```

## Install the skill

```bash
# npx skills (recommended)
npx skills add KRPCT/obsidian-kglite@obsidian-kglite -g -y

# Claude Code plugin marketplace
/plugin marketplace add KRPCT/obsidian-kglite
/plugin install obsidian-kglite@obsidian-kglite

# manual: Codex / any agent that reads a skills directory
git clone https://github.com/KRPCT/obsidian-kglite.git
cp -r obsidian-kglite/skills/obsidian-kglite ~/.agents/skills/
```

## Use it

```bash
mkdir -p .kglite-out
kglite okf check VAULT --strict
kglite okf build VAULT -o .kglite-out/vault.kgl
kglite query .kglite-out/vault.kgl "MATCH (n) WHERE n.file_path IS NOT NULL RETURN count(*) AS notes" --format json
kglite okf status VAULT --graph .kglite-out/vault.kgl
```

Or through the bundled wrapper, which refuses the three mistakes this workflow invites (missing output
directory, graph written inside the vault, two statements in one query):

```bash
python skills/obsidian-kglite/scripts/vault_graph.py build VAULT
python skills/obsidian-kglite/scripts/vault_report.py VAULT --out .kglite-out/health.md
```

## What is inside

```text
skills/obsidian-kglite/
  SKILL.md                     entry point: mental model, loop, failure modes, verification
  references/
    VAULT-FORMAT.md            the normative format, condensed with section numbers
    CYPHER-COOKBOOK.md         queries by question, each one executed
    ANNOTATIONS.md             the five in-note annotations and the queries that read them
    LINK-GRAPH.md              link-repair protocol: two-signal rule, anti-sprawl checks
    SERVING.md                 MCP server, .kglite/skills, .kglite/recipes, output budgets
    OBSIDIAN-CLI.md            inlined Obsidian CLI reference (upstream-synced)
    OBSIDIAN-MARKDOWN.md       inlined Obsidian markdown essentials (upstream-synced)
    SOURCES.md                 provenance, verified vs documented-only
  scripts/
    vault_graph.py             path-safe CLI wrapper
    vault_report.py            Markdown health report
    check_upstream.py          drift check for the inlined Obsidian material
    install_local.py           deploy this skill into a skills directory
  assets/
    vault.yaml                 starter .kglite/vault.yaml
    note-annotations.md        template showing all five annotations
    skill-for-vault.md         template for .kglite/skills/
  evals/evals.json             prompts the skill is expected to handle
```

## Design notes

- **Progressive disclosure.** `SKILL.md` stays under 250 lines and points at references; the format
  reference carries the detail, the cookbook carries the queries.
- **Everything is labeled by evidence status.** A command in this repo was either run against a fixture
  vault with kglite 0.21.2 (and its output quoted) or is explicitly marked documented-only in
  `references/SOURCES.md`.
- **Inlined, and honest about drift.** The Obsidian CLI and markdown material is inlined so the skill
  works without the companion pack; `scripts/check_upstream.py` reports when upstream moved.
- **No prose rewriting.** The repair protocol adds links and annotations; it does not restructure a
  human's text to make a query easier.

## Updating the inlined Obsidian material

```bash
python skills/obsidian-kglite/scripts/check_upstream.py          # exit 1 on drift
python skills/obsidian-kglite/scripts/check_upstream.py --update  # print the hash to paste
```

Re-inline the changed sections, update `upstream-sha256` in the reference header, and commit both
together.

## License and attribution

MIT. See [LICENSE](LICENSE).

The inlined Obsidian CLI and markdown references derive from
[kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) (MIT, © Steph Ango). The
link-repair philosophy follows the `obsidian-link-graph` idea in
[galaxy-dawn/claude-scholar](https://github.com/galaxy-dawn/claude-scholar); the graph queries that
make it measurable are this project's.
