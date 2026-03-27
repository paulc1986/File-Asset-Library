# GTA 000 - Custom Asset Library User Guide

This guide covers the complete day-to-day workflow for `GTA 000 - Custom Asset Library`, including setup, library management, asset overrides, metadata, previews, validation, and troubleshooting.

## 1. Overview

`GTA 000 - Custom Asset Library` is a custom Blender add-on that indexes `.blend` files as package-based assets.

Instead of requiring every reusable piece to be marked as an individual Blender asset, the add-on can treat the following as a single browser entry:

- a full `.blend` package
- a single collection inside a `.blend`
- a detected object hierarchy
- a detected armature-driven package
- multiple package items described by metadata

This is especially useful for:

- rigged props
- armature-based assets
- multi-object signs, vehicles, or characters
- collection-based environment pieces
- packages that depend on materials, modifiers, constraints, or actions

## 2. Core Concepts

### Library Root

A library root is a folder you add to the add-on. The scanner walks it recursively and indexes every `.blend` file it finds.

### Package Asset

A package asset is a browser entry created from one `.blend` file or one metadata-defined item inside that file.

### Library Overrides

Overrides let you rename and reclassify an asset in your own library without editing the original metadata file. These are stored beside the source `.blend` as:

```text
<blendname>.bgal.json
```

### Shared Registries

Each library root can store shared taxonomy files:

- `.bgal_categories.json`
- `.bgal_tags.json`

These define reusable categories, subcategories, and tags for assets in that root.

### Cache And Index

The add-on stores:

- an index of scanned assets in Blender's user config location
- UI state such as favorites and recents in Blender's user config location
- generated thumbnail images in Blender's user cache location

If no library roots are enabled, the add-on clears the runtime index so old assets do not continue to appear.

## 3. Installation

1. Open Blender.
2. Go to `Edit > Preferences > Add-ons`.
3. Click `Install...`.
4. Choose [blend_package_asset_library.zip](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/blend_package_asset_library.zip).
5. Enable `GTA 000 - Custom Asset Library`.

The main UI appears in:

- `3D View > Sidebar > Custom Asset Library`

## 4. Interface Tour

The add-on is organized into these sections:

### Custom Asset Library

This is the main browsing panel. It includes:

- search
- filters for category, subcategory, and tags
- favorites-only toggle
- grid/list switching
- sorting
- asset cards or list rows
- append/link actions
- import options

### Asset Details

This shows information for the currently active asset:

- a preview
- an asset selector dropdown based on the current filtered list
- library overrides
- source path
- warnings
- metadata summary

### Libraries

This is the management area for library-wide configuration.

Child panels:

- `Asset Library Paths`
- `Categories`
- `Sub-categories`
- `Tags`

## 5. Setting Up A Library

### Add A Root Path

1. Open `Libraries > Asset Library Paths`.
2. Click `+`.
3. Pick a root folder containing `.blend` files.
4. Click refresh.

The add-on scans that folder recursively.

### Recommended Folder Layout

You can organize your root however you like, but a clean structure helps.

Example:

```text
PackageLibrary/
  Emergency/
    Lightbars/
      code3_pursuit_1200mm_fire_sign_c.blend
      code3_pursuit_1200mm_fire_sign_c.asset.json
      preview.png
    Sirens/
  Vehicles/
    Police/
```

See also [library_layout.txt](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/examples/library_layout.txt).

## 6. How Scanning Works

For each enabled root:

1. The add-on finds all `.blend` files recursively.
2. It reads sidecar metadata if present.
3. It inspects collections, objects, and actions from the `.blend`.
4. It decides what the package entry should import.
5. It resolves a thumbnail image.
6. It builds the runtime asset list and caches the result.

The scanner reuses unchanged cached entries when possible, based on file signature, modified time, and size.

If auto-refresh is enabled in the add-on preferences, the add-on also performs a lightweight periodic check of enabled roots and rescans only when it detects a change.

## 7. Asset Detection Rules

The import target is resolved in this order:

1. metadata `entry_collection`
2. metadata `entry_object`
3. metadata `entry_objects`
4. metadata `import_mode=BLEND`
5. collection named `ASSET_<name>`
6. single top-level collection
7. single armature hierarchy
8. single root object hierarchy
9. package fallback

This means a plain `.blend` with no metadata can still work well if its structure is clean.

## 8. Metadata Files

Supported metadata filenames:

- `<blend>.asset.json`
- `<blend>.asset.yaml`
- `<blend>.asset.yml`
- `<blend>.json`
- `<blend>.yaml`
- `<blend>.yml`
- `asset.json`
- `asset.yaml`
- `asset.yml`

Supported metadata fields include:

- `display_name`
- `category`
- `subcategory`
- `tags`
- `thumbnail`
- `description`
- `author`
- `version`
- `catalogue`
- `catalogue_path`
- `import_mode`
- `entry_object`
- `entry_objects`
- `entry_collection`
- `enabled`
- `group`
- `items`

### Example JSON

```json
{
  "display_name": "Code 3 Pursuit Fire Sign",
  "category": "Emergency",
  "subcategory": "Lightbars",
  "tags": ["sign", "code3", "fire"],
  "thumbnail": "preview.png",
  "description": "1200mm Code 3 sign package.",
  "author": "Studio Team",
  "version": "1.0",
  "entry_collection": "Collection"
}
```

### Catalogue Paths

`catalogue` or `catalogue_path` can be used as a shorthand grouping path:

```json
{
  "catalogue": "Emergency/Lightbars/Code 3"
}
```

The add-on maps that into:

- category: `Emergency`
- subcategory: `Lightbars`
- group: `Code 3`

## 9. Browsing Assets

### Search

The search box matches across:

- display name
- description
- category
- subcategory
- relative path
- tags

### Filters

Available filters:

- `Category`
- `Subcategory`
- `Tags`
- favorites-only

The tag filter accepts comma-separated or semicolon-separated text.

Examples:

- `code3`
- `code3, fire`
- `vehicle; emergency`

### Views

- `Grid`: larger visual preview cards
- `List`: compact list with thumbnail and metadata

### Sorting

- `Name`
- `Category`
- `Recently Modified`
- `Recently Used`
- `Author`

## 10. Selecting Assets

You can select an asset in several ways:

- click the asset name bar on a grid card
- click the item in list view
- use the `Asset` dropdown in `Asset Details`

The `Asset Details` selector is based on the currently filtered list, which is useful when narrowing a large library to a small set of items.

## 11. Importing Assets

The add-on currently exposes two main import modes:

- `Append`
- `Link`

### Append

Copies data into the current `.blend`.

Use append when:

- you want the asset fully editable in the current file
- you do not need a live connection to the source file

### Link

Keeps data linked to the source `.blend`.

Use link when:

- you want to update assets centrally
- you want smaller working files
- you want shared source ownership

### Import Options

#### Make Local

If enabled, linked data is made local after linking.

#### Collection Instance

If the asset resolves to a collection target, this can import it as a collection instance instead of a full appended hierarchy.

#### Namespace

Prefixes imported datablock names to reduce duplicate-name collisions.

## 12. Asset Details And Library Overrides

`Asset Details` shows the selected asset preview, metadata, warnings, and source information.

Inside `Library Overrides` you can change:

- `Name`
- `Category`
- `Subcategory`
- `Tags`

You can either choose an existing category/subcategory or choose `Add New...` to create a new one while saving the override.

### Override Workflow

1. Select an asset.
2. Open `Asset Details`.
3. Change `Name`, `Category`, `Subcategory`, or `Tags`.
4. Click `Save Library Overrides`.

To revert back to source metadata, click `Clear Library Overrides`.

### Where Overrides Are Stored

Overrides are saved beside the source `.blend`:

```text
<blendname>.bgal.json
```

This keeps the library's custom organization with the asset package itself.

## 13. Managing Categories

Open:

- `Libraries > Categories`

The panel shows the category list for the currently targeted library root.

### Add A Category

1. Open `Categories`.
2. Type a new category name into `Name`.
3. Click `Add`.

### Rename A Category

1. Select the category row.
2. Type the new name into `Name`.
3. Click `Update`.

### Delete A Category

1. Select the category row.
2. Click `Delete`.

Deleting a category also clears that category assignment from matching override files within that root.

## 14. Managing Sub-categories

Open:

- `Libraries > Sub-categories`

### Add A Sub-category

1. Select the parent category in `Categories`.
2. Open `Sub-categories`.
3. Type the subcategory name into `Name`.
4. Click `Add`.

### Rename A Sub-category

1. Select the parent category in `Categories`.
2. Select the subcategory row in `Sub-categories`.
3. Type the new name into `Name`.
4. Click `Update`.

### Delete A Sub-category

1. Select the parent category.
2. Select the subcategory row.
3. Click `Delete`.

Deleting a subcategory clears that subcategory assignment from matching override files within that root.

## 15. Managing Tags

Open:

- `Libraries > Tags`

### Add A Tag

1. Type the tag name into `Name`.
2. Click `Add`.

### Rename A Tag

1. Select the tag row.
2. Type the new name into `Name`.
3. Click `Update`.

### Delete A Tag

1. Select the tag row.
2. Click `Delete`.

If you rename or remove a tag, existing matching override files in that root are updated too.

## 16. Assigning Tags To Assets

In `Asset Details > Library Overrides`, the `Tags` field accepts comma-separated or semicolon-separated values.

Examples:

- `code3, fire, lightbar`
- `vehicle; emergency; sign`

When you save overrides:

- the asset gets those tags
- any new tags are added to the root tag registry automatically

## 17. Favorites And Recents

You can mark an asset as a favorite using the favorite action.

Favorites are stored in the add-on UI state and can be filtered from the browser.

Recently used assets are tracked automatically and can be surfaced using the `Recently Used` sort mode.

## 18. Thumbnails And Previews

Thumbnail resolution priority:

1. metadata `thumbnail`
2. common preview filenames next to the `.blend`
3. generated cached preview

Common preview names include:

- `<blend>.png`
- `<blend>_preview.png`
- `preview.png`
- `thumbnail.png`
- `cover.png`

### Regenerate Thumbnail

Use `Regenerate Thumbnail` when:

- the preview image is outdated
- you changed the source package
- a generated preview was bad

Generated previews are stored in Blender's user cache area, not in the library root itself.

## 19. Validation

Use `Validate Asset Package` to check for common problems such as:

- missing entry targets
- missing thumbnails
- missing external textures
- import problems detected during inspection

Warnings appear in `Asset Details` and in the validation report message.

## 20. File Storage Summary

### Beside Each Asset

- `<blendname>.bgal.json`

### In Each Library Root

- `.bgal_categories.json`
- `.bgal_tags.json`

### In Blender User Config

- `asset_index.json`
- `ui_state.json`

### In Blender User Cache

- generated thumbnail PNGs

## 21. Troubleshooting

### Assets Still Show After Removing Library Paths

Current behavior should now be:

- if no library roots are enabled, cached assets are cleared
- removing the last root clears the runtime index
- starting Blender with no roots configured shows an empty browser

If assets still appear:

1. confirm there are no enabled library paths
2. click refresh
3. restart Blender

### A New Category Or Sub-category Will Not Add

Check that:

- you typed the new value into the `Name` field
- for subcategories, the parent category is selected first
- you clicked `Add`, not `Update`

If you are creating categories from `Asset Details`, choose `Add New...` in the dropdown and then fill in the new name field before saving.

### Import Fails

Common causes:

- the source `.blend` is the file currently open in Blender
- the metadata target names do not match the source file
- the target collection/object no longer exists

### Preview Is Missing Or Wrong

Try:

1. confirm a metadata thumbnail path or preview image exists
2. click `Regenerate Thumbnail`
3. rescan the library

## 22. Known Limitations

- Native Asset Browser drag-and-drop is not available for this custom sidebar browser.
- The add-on relies on Blender library loading behavior, so import behavior ultimately follows Blender's append/link rules.
- Importing from the currently open `.blend` into itself is not supported by Blender.
- Very large libraries may still take time on first scan or when many `.blend` files change.

## 23. Best Practices

- Keep one logical package per `.blend` unless you intentionally expose multiple items with metadata.
- Use clean collection or hierarchy structure for no-metadata files.
- Add explicit metadata for important production assets.
- Supply hand-authored preview images when presentation matters.
- Use categories and tags consistently across the whole library.
- Use namespaces when importing repeated assets into the same scene.

## 24. Example Files

Reference files in this repo:

- [README.md](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/README.md)
- [robot.asset.json](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/examples/robot.asset.json)
- [robot.asset.yaml](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/examples/robot.asset.yaml)
- [library_layout.txt](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/examples/library_layout.txt)
