# GTA 000 - Custom Asset Library

`GTA 000 - Custom Asset Library` is a Blender add-on that indexes whole `.blend` files as reusable asset packages.

Instead of forcing every reusable part to be marked as a separate native asset, this add-on lets a package entry represent:

- an entire `.blend` file
- a specific collection inside a `.blend`
- a detected rig/object hierarchy
- multiple named package items from one `.blend` via metadata

## Documentation

- Quick start: [docs/QUICK_START.md](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/docs/QUICK_START.md)
- Full user guide: [docs/USER_GUIDE.md](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/docs/USER_GUIDE.md)
- Wiki source files: [Wiki Files](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/Wiki%20Files)
- Live wiki URL: [Blender File Asset Library Wiki](https://github.com/paulc1986/Blender-File-Asset-Library/wiki)

## Add-on Folder Structure

```text
blend_package_asset_library/
  __init__.py
  constants.py
  importer.py
  index_store.py
  library_io.py
  metadata.py
  models.py
  ops_asset.py
  ops_library.py
  preferences.py
  preview_cache.py
  properties.py
  runtime.py
  scanner.py
  thumbnail_render.py
  ui.py
  utils.py
  validator.py
examples/
  library_layout.txt
  robot.asset.json
  robot.asset.yaml
```

## Recommended Asset Library Layout

See [examples/library_layout.txt](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/examples/library_layout.txt).

Typical layout:

```text
PackageLibrary/
  Characters/
    Robots/
      Robot_Mk01.blend
      Robot_Mk01.asset.json
      Robot_Mk01.png
  Vehicles/
    Trucks/
      CargoTruck.blend
      CargoTruck.asset.yaml
      preview.png
  Environments/
    SciFiCorridor.blend
```

## Metadata Format

Supported sidecars:

- `<blend>.asset.json`
- `<blend>.asset.yaml`
- `<blend>.asset.yml`
- `<blend>.json`
- `<blend>.yaml`
- `<blend>.yml`
- `asset.json`
- `asset.yaml`
- `asset.yml`

Supported fields:

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

Examples:

- [robot.asset.json](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/examples/robot.asset.json)
- [robot.asset.yaml](/E:/ChatGPT/Blender%20Grouped%20Assets%20Library/examples/robot.asset.yaml)

`catalogue` and `catalogue_path` are aliases that let you define a path-like grouping such as `Emergency/Signs/Code 3`. The add-on maps that path into category/subcategory/group metadata for the custom browser.

## Detection Pipeline

For each `.blend`, the scanner:

1. Loads metadata if present.
2. Inspects linked collections, objects, and actions without permanently importing them.
3. Builds one or more browser entries.
4. Resolves the import target using this priority:
   - metadata `entry_collection`
   - metadata `entry_object`
   - metadata `entry_objects`
   - metadata `import_mode=BLEND`
   - collections named `ASSET_*`
   - a single top-level collection
   - a single armature-root hierarchy
   - a single root object hierarchy
   - fallback package import
5. Resolves a thumbnail from metadata, auto-detected preview files, or cached rendered previews.

## Import Pipeline

When an entry is placed, the add-on:

1. Appends or links the resolved collection/object package from the source `.blend`.
2. Links imported root collections or objects into the active scene collection.
3. Optionally instantiates collections as collection instances.
4. Optionally makes linked data local.
5. Optionally namespaces imported local datablocks.
6. Optionally offsets the imported package to the 3D cursor.
7. Records the asset as recently used.

Dependencies such as materials, images, actions, armatures, hierarchy, modifiers, and constraints come in through Blender's standard library loading behavior for the imported collection/object set.

## Install

1. Zip the `blend_package_asset_library` folder or install it directly from Blender's add-on installer.
2. In Blender, open `Edit > Preferences > Add-ons > Install...`.
3. Enable `GTA 000 - Custom Asset Library`.
4. Add one or more root folders in the add-on preferences or the `Custom Asset Library` sidebar.
5. Click `Scan Libraries`.

## Use

1. Open the `Custom Asset Library` tab in the 3D View sidebar.
2. Search or filter assets by category, subcategory, tags, and favorites.
3. Switch between grid and list view.
4. Choose append or link mode, namespace, and collection-instance mode.
5. Use `Append` or `Link` from the browser.
6. In `Asset Details`, rename the asset for your own library and assign custom category/subcategory/tag overrides.
7. Use the actions menu to validate packages, reveal files, open source `.blend` files, or regenerate thumbnails.

## Notes And Limitations

- The add-on is implemented against Blender's Python API conventions and smoke-tested in a Blender 5.0 environment. It is intended for Blender 4.x and should be reviewed in the exact 4.x version you deploy.
- Blender does not expose a full custom Asset Browser drag-and-drop API for third-party package browsers, so the add-on provides placement/import operators rather than native drag from the built-in Asset Browser.
- The custom browser replaces Blender's `template_icon_view` popup behavior with direct card-style controls.
- Blender also does not allow appending or linking from the currently open `.blend` file into itself. Use a separate working scene file when importing a package from the library.
- YAML support is built in for common metadata structures and also uses `PyYAML` automatically if it is available.
- Very large first-time scans can still take time because changed `.blend` files are inspected deeply for hierarchy detection.
- Automatic preview generation uses a temporary render scene and is best treated as a cached utility, not a replacement for hand-authored thumbnails in every workflow.
- Auto-refresh can be enabled in add-on preferences so newly added or changed assets appear without a manual refresh click.
