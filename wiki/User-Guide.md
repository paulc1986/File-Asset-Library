# User Guide

## Main Panels

### Custom Asset Library

The main browser panel provides:

- search
- category, subcategory, and tag filters
- favorites-only toggle
- grid/list views
- sorting
- append/link actions
- import options such as `Make Local`, `Collection Instance`, and `Namespace`

### Asset Details

The details panel provides:

- a preview image
- an `Asset` dropdown based on the current filtered list
- library override fields
- metadata and warning display
- actions for validation, thumbnail regeneration, reveal, and opening the source `.blend`

### Libraries

Library management is grouped under:

- `Asset Library Paths`
- `Categories`
- `Sub-categories`
- `Tags`

## Library Overrides

Overrides are saved beside the source `.blend` in:

```text
<blendname>.bgal.json
```

Overrides can change:

- display name
- category
- subcategory
- tags

## Shared Registries

Each root can also store:

- `.bgal_categories.json`
- `.bgal_tags.json`

These are the shared registries used by the category, sub-category, and tag manager panels.

## Auto Refresh

The add-on can periodically check enabled roots for new, removed, or changed files.

It uses a lightweight file signature pass and only rescans when the library contents actually change.

Configuration is available in add-on preferences:

- `Auto Refresh Libraries`
- `Auto Refresh Interval (Seconds)`
