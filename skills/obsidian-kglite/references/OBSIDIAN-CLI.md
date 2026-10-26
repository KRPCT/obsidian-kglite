# Obsidian CLI (inlined)

<!-- upstream: kepano/obsidian-skills@obsidian-cli
     source: https://raw.githubusercontent.com/kepano/obsidian-skills/main/skills/obsidian-cli/SKILL.md
     upstream-sha256: b54257cdc0e5d04488b35b0c797bfe427b24359f0848d3c73924dcacf8da6358
     captured: 2026-10-26
     license: MIT, (c) Steph Ango
     sync: python scripts/check_upstream.py -->

Inlined so this skill works without the companion pack installed, and so an update is a diff instead
of a memory exercise. The canonical source is the Obsidian CLI documentation at
https://help.obsidian.md/cli — `obsidian help` is always the current truth, and this file is the
stable shape of it.

## What it is

Use the `obsidian` CLI to interact with a **running** Obsidian instance. It requires Obsidian to be
open; a command that needs the app will hang or fail when it is closed. On this machine the CLI ships
with the desktop app, so updating the app updates the CLI (`obsidian version` prints
`<app version> (installer <installer version>)`).

## Syntax

Parameters take a value with `=`. Quote values containing spaces.

```bash
obsidian create name="My Note" content="Hello world"
```

Flags are boolean switches with no value:

```bash
obsidian create name="My Note" silent overwrite
```

In content values use `\n` for newline and `\t` for tab.

## File targeting

Many commands accept `file` or `path`. Without either, the active file is used.

- `file=<name>` — resolves like a wikilink (name only, no path or extension needed)
- `path=<path>` — exact path from vault root, e.g. `folder/note.md`

## Vault targeting

Commands target the most recently focused vault by default. `vault=<name>` as the first parameter
targets a specific vault:

```bash
obsidian vault="My Vault" search query="test"
```

## Common patterns

```bash
obsidian read file="My Note"
obsidian create name="New Note" content="# Hello" template="Template" silent
obsidian append file="My Note" content="New line"
obsidian search query="search term" limit=10
obsidian daily:read
obsidian daily:append content="- [ ] New task"
obsidian property:set name="status" value="done" file="My Note"
obsidian tasks daily todo
obsidian tags sort=count counts
obsidian backlinks file="My Note"
```

Use `--copy` on any command to copy output to the clipboard. Use `silent` to keep files from opening.
Use `total` on list commands for a count.

## Plugin and theme development

1. Reload after a change:

```bash
obsidian plugin:reload id=my-plugin
```

2. Check for errors — fix and repeat if any appear:

```bash
obsidian dev:errors
```

3. Verify visually:

```bash
obsidian dev:screenshot path=screenshot.png
obsidian dev:dom selector=".workspace-leaf" text
```

4. Read console output:

```bash
obsidian dev:console level=error
```

Additional developer commands: `obsidian eval code="app.vault.getFiles().length"`,
`obsidian dev:css selector=".workspace-leaf" prop=background-color`, `obsidian dev:mobile on`.
Run `obsidian help` for the current list, including CDP and debugger controls.

## Using it alongside this skill

- The CLI is the **write** path for link repair: `obsidian read`, `obsidian append`,
  `obsidian property:set`. It keeps Obsidian's own index and backlink cache in step, which a raw file
  write does not do until the next file-system event.
- The graph is the **measure** path. Never edit through a graph query: rebuild after the edit and
  re-measure.
- A vault the CLI can reach is a vault KGLite can read; the two see the same files, so
  `kglite okf check` after a CLI edit is a valid verification step.
