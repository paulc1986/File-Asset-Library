# GTA 000 - Custom Asset Library Quick Start

This guide is the fastest way to get `GTA 000 - Custom Asset Library` running in Blender and importing package-based assets from whole `.blend` files.

## What This Add-on Does

Blender's native Asset Browser is great for single marked assets, but it can be awkward for complex rigs, hierarchies, collection-based packages, and multi-part objects.

`GTA 000 - Custom Asset Library` treats a whole `.blend` file, or a specific collection/object set inside it, as one reusable package entry.

## 1. Install The Add-on

1. Open Blender.
2. Go to `Edit > Preferences > Add-ons`.
3. Click `Install...`.
4. Select [blend_package_asset_library.zip](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/blend_package_asset_library.zip).
5. Enable `GTA 000 - Custom Asset Library`.

After enabling it, the browser appears in the 3D View sidebar under the `Custom Asset Library` tab.

## 2. Add Your Library Folder

1. Open the `Custom Asset Library` sidebar panel.
2. Expand `Libraries`.
3. Expand `Asset Library Paths`.
4. Click `+`.
5. Choose the root folder that contains your asset `.blend` files.
6. Click the refresh button.

The add-on scans that folder recursively and builds a package index from all `.blend` files it finds.

If `Auto Refresh Libraries` is enabled in the add-on preferences, the add-on also checks for new or changed assets automatically at the configured interval.

## 3. Browse Your Assets

Use the main `Custom Asset Library` panel to:

- search by name
- filter by `Category`, `Subcategory`, or `Tags`
- switch between `Grid` and `List`
- sort by `Name`, `Category`, `Recently Modified`, `Recently Used`, or `Author`
- show only favorites

Click the asset name bar on a card, or select it in list view, to make it active.

## 4. Import An Asset

Choose one of the two main import modes:

- `Append`: copies datablocks into the current file
- `Link`: links datablocks from the source `.blend`

Then click:

- `Append` on the asset card
- `Link` on the asset card
- or use the global `Append` / `Link` buttons below the browser

Useful import options:

- `Make Local`: makes linked data local after linking
- `Collection Instance`: places collection targets as collection instances where supported
- `Namespace`: prefixes imported datablock names to reduce naming collisions

## 5. Review Asset Details

Expand `Asset Details` to see:

- a large preview
- the currently selected asset
- source file information
- warnings
- import target and detection strategy
- author/version info when supplied by metadata

You can also switch the active asset from the `Asset` dropdown at the top of `Asset Details`.

## 6. Rename Or Organize An Asset

In `Asset Details > Library Overrides` you can:

- rename the asset for your own library
- assign an existing category
- assign an existing subcategory
- assign tags
- create a new category or subcategory by choosing `Add New...`

Click `Save Library Overrides` when finished.

These overrides are stored beside the source `.blend` file in a sidecar file:

- `<blendname>.bgal.json`

Example:

```text
code3_pursuit_1200mm_fire_sign_c.blend
code3_pursuit_1200mm_fire_sign_c.bgal.json
```

## 7. Manage Shared Categories, Sub-categories, And Tags

Under `Libraries` you will find:

- `Categories`
- `Sub-categories`
- `Tags`

These are shared library-level registries for the selected library root.

Basic workflow:

1. Select the relevant row in the list if you want to update or delete an existing item.
2. Type a name into the `Name` field.
3. Click `Add`, `Update`, or `Delete`.

For subcategories:

1. Select the parent category first in `Categories`.
2. Open `Sub-categories`.
3. Type the new subcategory name.
4. Click `Add`.

These registries are saved in the library root:

- `.bgal_categories.json`
- `.bgal_tags.json`

## 8. Use Metadata For Better Results

You can place a metadata file next to a `.blend` to control display names, grouping, tags, thumbnails, and import targets.

Supported names include:

- `<blend>.asset.json`
- `<blend>.asset.yaml`
- `<blend>.json`
- `asset.json`

Example:

```json
{
  "display_name": "Code 3 Pursuit Fire Sign",
  "category": "Emergency",
  "subcategory": "Lightbars",
  "tags": ["sign", "code3", "fire"],
  "entry_collection": "Collection",
  "thumbnail": "preview.png"
}
```

## 9. Common Actions

Use the asset actions menu or buttons in `Asset Details` to:

- toggle favorite
- validate asset package
- regenerate thumbnail
- reveal in Explorer/Finder
- open the source `.blend`

## 10. Important Limitations

- This add-on does not provide true native Asset Browser drag-and-drop into the viewport.
- You cannot append or link a `.blend` package from the currently open `.blend` into itself.
- If no library roots are enabled, the browser now starts empty and clears old cached entries.

## Next Step

For the full walkthrough, troubleshooting, metadata reference, and workflow advice, read [USER_GUIDE.md](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/docs/USER_GUIDE.md).
