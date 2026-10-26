# Obsidian markdown essentials (inlined)

<!-- upstream: kepano/obsidian-skills@obsidian-markdown
     source: https://raw.githubusercontent.com/kepano/obsidian-skills/main/skills/obsidian-markdown/SKILL.md
     upstream-sha256: 7ad72e1f0a9081ed325e76b6402ad5de50a00e63e2341fd403a92f147234a007
     captured: 2026-10-26
     license: MIT, (c) Steph Ango
     sync: python scripts/check_upstream.py -->

Only the Obsidian-specific extensions are here; standard Markdown is assumed. The full upstream skill
also ships `references/PROPERTIES.md`, `EMBEDS.md` and `CALLOUTS.md` — read them when you need the
complete property types, embed variants or the callout alias table.

## Note skeleton

1. Frontmatter with properties (`title`, `tags`, `aliases`, plus whatever the vault queries).
2. Standard Markdown for structure.
3. `[[wikilinks]]` for notes in the vault, `[text](url)` for external URLs only.
4. `![[embed]]` for notes, images, PDFs.
5. `> [!type]` for callouts.
6. Verify in reading view.

## Wikilinks

```markdown
[[Note Name]]                link to note
[[Note Name|Display Text]]   custom display text
[[Note Name#Heading]]        link to heading
[[Note Name#^block-id]]     link to block
[[#Heading in same note]]    same-note heading link
```

A block id is `^block-id` appended to a paragraph, or on its own line after a quote or list:

```markdown
This paragraph can be linked to. ^my-block-id
```

## Embeds

```markdown
![[Note Name]]               embed full note
![[Note Name#Heading]]       embed section
![[image.png]]               embed image
![[image.png|300]]           embed with width
![[document.pdf#page=3]]     embed a PDF page
```

## Callouts

```markdown
> [!note]
> Basic callout.

> [!warning] Custom Title
> Callout with a custom title.

> [!faq]- Collapsed by default
> Foldable callout (- collapsed, + expanded).
```

Common types: note, tip, warning, info, example, quote, bug, danger, success, failure, question,
abstract, todo. Obsidian styles thirteen; **any other identifier renders as a plain callout**, which is
why a corpus keeps its own vocabulary (`[!versionadded]`) and why KGLite stores the kind verbatim,
lowercased.

## Properties

```yaml
---
title: My Note
date: 2024-01-15
tags:
  - project
  - active
aliases:
  - Alternative Name
cssclasses:
  - custom-class
---
```

Default properties: `tags` (searchable labels), `aliases` (alternative names for link suggestions),
`cssclasses` (styling only — ignored by the graph).

## Tags

```markdown
#tag            inline tag
#nested/tag     nested tag
```

Letters, digits (not first), underscores, hyphens and forward slashes. Also allowed in frontmatter
under `tags`.

## Comments and highlights

```markdown
Visible %%hidden%% text.

%%
A whole hidden block.
%%

==Highlighted text==
```

## What the graph does with each of these

| Syntax | Graph effect |
| --- | --- |
| `[[Note]]`, `[[Note\|text]]` | edge; type from `{type}`, link title, `heading_edges:` or the heading ladder |
| `[[Note#Heading]]`, `[[Note#^id]]` | edge with `anchor`; retargets onto the derived section or chunk |
| `![[Note]]` | `EMBEDS` edge |
| `![[image.png]]`, `![alt](x.png)` | attachment node plus `HAS_IMAGE` / `HAS_ATTACHMENT` with `alt`, `section`, `ordinal` |
| `> [!type]` | `Note` node when `callouts:` is declared (`kind`, `title`, `fold`, `text`) |
| `^block-id` | chunk key `Note#^block-id`, the only chunk id that survives edits above it |
| `#tag`, `tags:` | one `Tag` hub, case-insensitive |
| `%%comment%%` | stored in the body, never scanned — no link, tag or image is read out of it |
| `==highlight==` | plain text |
| `cssclasses` | ignored |
| HTML tags | prose (`<table>` rows are not structure; emit GFM tables) |
