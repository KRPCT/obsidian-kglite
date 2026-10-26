---
type: Article
corpus: example
category: guide
depends_on: "[[Horizon interpretation]]"
see_also: ["[[Faults]]", "[[Seismic survey]]"]
tags: [seismic, guide]
aliases: [annotation demo]
---
# Annotation demo

Everything in this file is ordinary Obsidian markdown. The annotations add facts the prose cannot
carry, and none of them changes how the note renders beyond a visible brace or a hidden comment.

## Typed link

[[Wells]]{opens-dialog} opens the task pane described below.

## Directive

To open the **Annotation table** dialog, click the button on the **Wells** task pane.

<!-- kglite address: Data tree -> Wells | Task pane: Wells -> Annotations table -->
<!-- kglite documented_in: [[Wells]] -->

## Tagged statements

Use the import dialog to load a deviation survey. #intent/import-wells

The datum is not checked on import. #warning

<!-- kglite chunk -->

The header row is validated before the datum is read. #warning ^header-check

## Parameters

| name | type | default | source anchor |
| --- | --- | --- | --- |
| depth | float | 0.0 | api.html#depth |
| unit | str | m | api.html#unit |

## Steps

1. Open the survey
2. Import wells
3. Check the datum warning above

## Callout

> [!versionadded] Available since 2.1
> The table reads the header row first.

## Example

```python
print("annotation demo")
```

## Related topics

- [[Faults]]
- [[Horizon interpretation]]
