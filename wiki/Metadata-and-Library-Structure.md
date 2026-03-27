# Metadata And Library Structure

## Recommended Library Layout

```text
PackageLibrary/
  Emergency/
    Lightbars/
      code3_pursuit_1200mm_fire_sign_c.blend
      code3_pursuit_1200mm_fire_sign_c.asset.json
      preview.png
```

## Supported Metadata Files

- `<blend>.asset.json`
- `<blend>.asset.yaml`
- `<blend>.asset.yml`
- `<blend>.json`
- `<blend>.yaml`
- `<blend>.yml`
- `asset.json`
- `asset.yaml`
- `asset.yml`

## Common Metadata Fields

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

## Detection Order

1. `entry_collection`
2. `entry_object`
3. `entry_objects`
4. `import_mode=BLEND`
5. `ASSET_` collection naming
6. single top-level collection
7. single armature hierarchy
8. single root object hierarchy
9. fallback package import
