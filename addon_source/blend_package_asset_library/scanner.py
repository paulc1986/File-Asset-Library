from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
from typing import Any

import bpy

from . import constants, runtime
from .index_store import load_index, load_ui_state, save_index
from .metadata import (
    load_category_registry,
    load_metadata_for_blend,
    load_tag_registry,
    load_user_override_for_asset,
    merge_metadata,
)
from .models import AssetEntry, AssetIndex, InspectionData, ValidationReport
from .preview_cache import preview_manager
from .utils import (
    best_display_name,
    dedupe_preserve_order,
    file_signature,
    normalized_blend_path,
    safe_remove_ids,
    safe_slug,
    stable_asset_id,
    thumbnails_directory,
)


_AUTO_REFRESH_LAST_SIGNATURE = ""
_WATCHED_LIBRARY_SUFFIXES = {
    ".blend",
    ".json",
    ".yaml",
    ".yml",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


def addon_preferences(context: bpy.types.Context):
    addon = context.preferences.addons.get(constants.ADDON_PACKAGE)
    return addon.preferences if addon else None


def _runtime_thumbnail_cache_path(asset_id: str) -> str:
    return str(thumbnails_directory() / f"{asset_id}.png")


def _normalized_cached_entry(entry: AssetEntry) -> AssetEntry:
    normalized = AssetEntry.from_dict(entry.to_dict())
    normalized.thumbnail_cache = _runtime_thumbnail_cache_path(normalized.asset_id)
    return normalized


def _load_merged_category_registry(roots: list[dict[str, str]]) -> dict[str, list[str]]:
    merged: dict[str, set[str]] = defaultdict(set)
    for root in roots:
        root_path = Path(root["path"])
        for category, subcategories in load_category_registry(root_path).items():
            merged[category].update(subcategories)
    return {
        category: sorted(values, key=str.casefold)
        for category, values in sorted(merged.items(), key=lambda item: item[0].casefold())
    }


def _load_merged_tag_registry(roots: list[dict[str, str]]) -> list[str]:
    values: set[str] = set()
    for root in roots:
        root_path = Path(root["path"])
        values.update(load_tag_registry(root_path))
    return sorted(values, key=str.casefold)


def enabled_root_definitions(context: bpy.types.Context) -> list[dict[str, str]]:
    prefs = addon_preferences(context)
    if prefs is None:
        return []
    roots: list[dict[str, str]] = []
    for item in prefs.library_roots:
        directory = Path(bpy.path.abspath(item.directory)).resolve()
        if item.enabled and directory.exists():
            roots.append(
                {
                    "label": item.label.strip() or directory.name,
                    "path": str(directory),
                }
            )
    return roots


def _watched_library_files(root_path: Path):
    for path in sorted(root_path.rglob("*"), key=lambda item: str(item).casefold()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _WATCHED_LIBRARY_SUFFIXES:
            continue
        yield path


def _library_watch_signature(roots: list[dict[str, str]]) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    for root in sorted(roots, key=lambda item: item["path"].casefold()):
        root_path = Path(root["path"])
        digest.update(str(root_path).casefold().encode("utf-8"))
        for path in _watched_library_files(root_path):
            try:
                stat = path.stat()
            except Exception:
                continue
            relative = path.relative_to(root_path).as_posix().casefold()
            digest.update(relative.encode("utf-8"))
            digest.update(str(stat.st_mtime_ns).encode("utf-8"))
            digest.update(str(stat.st_size).encode("utf-8"))
    return digest.hexdigest()


def _inspect_loaded_library(filepath: Path) -> tuple[InspectionData, list[str]]:
    warnings: list[str] = []
    collections = []
    objects = []
    actions = []

    try:
        with bpy.data.libraries.load(str(filepath), link=True) as (data_from, data_to):
            data_to.collections = list(data_from.collections)
            data_to.objects = list(data_from.objects)
            data_to.actions = list(data_from.actions)
        collections = [item for item in data_to.collections if item is not None]
        objects = [item for item in data_to.objects if item is not None]
        actions = [item for item in data_to.actions if item is not None]
    except Exception as exc:
        return InspectionData(), [f"Blend inspection failed: {exc}"]

    try:
        child_collection_names = {
            child.name
            for collection in collections
            for child in collection.children
            if child is not None
        }
        top_level_collections = [
            collection.name for collection in collections if collection.name not in child_collection_names
        ]

        object_hierarchies: dict[str, list[str]] = {}
        root_objects = [obj.name for obj in objects if obj.parent is None]
        armature_roots: list[str] = []

        for obj in objects:
            descendants = [child.name for child in obj.children_recursive]
            if descendants:
                object_hierarchies[obj.name] = dedupe_preserve_order([obj.name] + descendants)

        for obj in objects:
            if obj.type != "ARMATURE":
                continue
            related = []
            for candidate in objects:
                if candidate == obj:
                    continue
                if candidate.parent == obj:
                    related.append(candidate.name)
                    continue
                for modifier in candidate.modifiers:
                    if modifier.type == "ARMATURE" and getattr(modifier, "object", None) == obj:
                        related.append(candidate.name)
                        break
            if related:
                armature_roots.append(obj.name)
                hierarchy = object_hierarchies.get(obj.name, [obj.name])
                object_hierarchies[obj.name] = dedupe_preserve_order(hierarchy + related)

        inspection = InspectionData(
            collections=sorted([collection.name for collection in collections], key=str.casefold),
            top_level_collections=sorted(top_level_collections, key=str.casefold),
            asset_named_collections=sorted(
                [
                    collection.name
                    for collection in collections
                    if collection.name.upper().startswith(constants.ASSET_COLLECTION_PREFIX)
                ],
                key=str.casefold,
            ),
            objects=sorted([obj.name for obj in objects], key=str.casefold),
            root_objects=sorted(root_objects, key=str.casefold),
            armature_roots=sorted(armature_roots, key=str.casefold),
            object_hierarchies=object_hierarchies,
            actions=sorted([action.name for action in actions], key=str.casefold),
        )
        return inspection, warnings
    finally:
        safe_remove_ids(list(actions) + list(objects) + list(collections))


def _package_targets(inspection: InspectionData) -> tuple[str, list[str]]:
    if inspection.top_level_collections:
        return "COLLECTION", list(inspection.top_level_collections)
    if inspection.collections:
        return "COLLECTION", list(inspection.collections)
    if inspection.root_objects:
        names = []
        for root in inspection.root_objects:
            names.extend(inspection.object_hierarchies.get(root, [root]))
        return "OBJECTS", dedupe_preserve_order(names)
    return "OBJECTS", list(inspection.objects)


def resolve_detection(metadata: dict[str, Any], inspection: InspectionData) -> tuple[str, list[str], str]:
    entry_collection = metadata.get("entry_collection", "")
    entry_object = metadata.get("entry_object", "")
    entry_objects = list(metadata.get("entry_objects", []))
    import_mode = metadata.get("import_mode", "AUTO").upper()

    if entry_collection:
        return "COLLECTION", [entry_collection], "Metadata entry_collection"
    if entry_object:
        names = inspection.object_hierarchies.get(entry_object, [entry_object])
        return "OBJECT_HIERARCHY", names, "Metadata entry_object"
    if entry_objects:
        return "OBJECTS", entry_objects, "Metadata entry_objects"
    if import_mode == "BLEND":
        target_kind, names = _package_targets(inspection)
        return target_kind, names, "Metadata import_mode=BLEND"
    if import_mode == "COLLECTION" and inspection.asset_named_collections:
        return "COLLECTION", [inspection.asset_named_collections[0]], "Metadata import_mode=COLLECTION"
    if import_mode == "OBJECT_HIERARCHY" and inspection.armature_roots:
        root = inspection.armature_roots[0]
        return "OBJECT_HIERARCHY", inspection.object_hierarchies.get(root, [root]), "Metadata import_mode=OBJECT_HIERARCHY"

    if inspection.asset_named_collections:
        return "COLLECTION", [inspection.asset_named_collections[0]], "ASSET_ collection"
    if len(inspection.top_level_collections) == 1:
        collection_name = inspection.top_level_collections[0]
        return "COLLECTION", [collection_name], "Single top-level collection"
    if len(inspection.armature_roots) == 1:
        root = inspection.armature_roots[0]
        return "OBJECT_HIERARCHY", inspection.object_hierarchies.get(root, [root]), "Single armature hierarchy"
    if len(inspection.root_objects) == 1:
        root = inspection.root_objects[0]
        return "OBJECT_HIERARCHY", inspection.object_hierarchies.get(root, [root]), "Single root object"

    target_kind, names = _package_targets(inspection)
    return target_kind, names, "Fallback package import"


def _auto_thumbnail(blend_path: Path, metadata: dict[str, Any], target_names: list[str]) -> str:
    if metadata.get("thumbnail"):
        return metadata["thumbnail"]

    search_stems = [blend_path.stem]
    search_stems.extend([safe_slug(name) for name in target_names if name])

    for stem in dedupe_preserve_order(search_stems):
        for pattern in constants.COMMON_PREVIEW_FILENAMES:
            candidate = blend_path.parent / pattern.format(stem=stem)
            if candidate.exists():
                return str(candidate)
    return ""


def _derive_grouping(
    grouping_mode: str,
    root_label: str,
    relative_path: Path,
    metadata: dict[str, Any],
) -> tuple[str, str, str]:
    category = ""
    subcategory = ""
    folder_group = relative_path.parent.as_posix() if relative_path.parent.as_posix() != "." else ""

    parts = [part for part in relative_path.parent.parts if part]
    if grouping_mode == "ROOT":
        category = root_label
    elif grouping_mode == "FOLDER":
        category = parts[0] if parts else root_label
        subcategory = parts[1] if len(parts) > 1 else ""
    elif grouping_mode == "METADATA":
        category = metadata.get("category", "")
        subcategory = metadata.get("subcategory", "")
    else:
        category = metadata.get("category", "") or (parts[0] if parts else root_label)
        subcategory = metadata.get("subcategory", "") or (parts[1] if len(parts) > 1 else "")

    return category, subcategory, folder_group


def _base_asset_payload(
    blend_path: Path,
    root_path: Path,
    root_label: str,
    metadata: dict[str, Any],
    metadata_source: str,
    inspection: InspectionData,
    warnings: list[str],
    grouping_mode: str,
) -> dict[str, Any]:
    relative_path = blend_path.relative_to(root_path)
    category, subcategory, folder_group = _derive_grouping(grouping_mode, root_label, relative_path, metadata)
    mtime, size, signature = file_signature(blend_path)
    display_name = metadata.get("display_name") or best_display_name(blend_path)
    return {
        "file_path": normalized_blend_path(str(blend_path)),
        "root_path": normalized_blend_path(str(root_path)),
        "relative_path": relative_path.as_posix(),
        "display_name": display_name,
        "category": category,
        "subcategory": subcategory,
        "description": metadata.get("description", ""),
        "author": metadata.get("author", ""),
        "version": metadata.get("version", ""),
        "tags": dedupe_preserve_order(metadata.get("tags", [])),
        "enabled": bool(metadata.get("enabled", True)),
        "metadata_source": metadata_source,
        "source_mtime": mtime,
        "source_size": size,
        "source_signature": signature,
        "package_key": stable_asset_id(str(blend_path)),
        "library_label": root_label,
        "folder_group": folder_group,
        "warnings": list(warnings),
        "inspection": inspection,
    }


def _entry_from_metadata(
    blend_path: Path,
    root_path: Path,
    root_label: str,
    metadata: dict[str, Any],
    metadata_source: str,
    inspection: InspectionData,
    warnings: list[str],
    grouping_mode: str,
    item_key: str = "",
) -> AssetEntry:
    payload = _base_asset_payload(
        blend_path=blend_path,
        root_path=root_path,
        root_label=root_label,
        metadata=metadata,
        metadata_source=metadata_source,
        inspection=inspection,
        warnings=warnings,
        grouping_mode=grouping_mode,
    )
    target_kind, target_names, strategy = resolve_detection(metadata, inspection)
    display_name = metadata.get("display_name") or payload["display_name"]
    asset_id = stable_asset_id(str(blend_path), item_key or display_name, "|".join(target_names))
    thumbnail_source = _auto_thumbnail(blend_path, metadata, target_names)
    thumbnail_cache = _runtime_thumbnail_cache_path(asset_id)
    entry = AssetEntry(
        asset_id=asset_id,
        file_path=payload["file_path"],
        root_path=payload["root_path"],
        relative_path=payload["relative_path"],
        display_name=display_name,
        category=payload["category"],
        subcategory=payload["subcategory"],
        base_display_name=display_name,
        base_category=payload["category"],
        base_subcategory=payload["subcategory"],
        base_tags=payload["tags"],
        tags=payload["tags"],
        description=payload["description"],
        author=payload["author"],
        version=payload["version"],
        enabled=payload["enabled"],
        import_mode=metadata.get("import_mode", "AUTO"),
        target_kind=target_kind,
        target_names=target_names,
        detection_strategy=strategy,
        thumbnail_source=thumbnail_source,
        thumbnail_cache=thumbnail_cache,
        metadata_source=metadata_source,
        source_mtime=payload["source_mtime"],
        source_size=payload["source_size"],
        source_signature=payload["source_signature"],
        package_key=payload["package_key"],
        library_label=payload["library_label"],
        folder_group=payload["folder_group"],
        item_key=item_key,
        warnings=payload["warnings"],
        inspection=inspection,
    )
    user_override, _override_source = load_user_override_for_asset(blend_path, item_key)
    if user_override:
        entry.display_name = user_override.get("display_name", "").strip() or entry.base_display_name
        entry.category = user_override.get("category", "").strip()
        entry.subcategory = user_override.get("subcategory", "").strip()
        if "tags" in user_override:
            entry.tags = dedupe_preserve_order(user_override.get("tags", []))
    return entry


def _expanded_items(metadata: dict[str, Any], inspection: InspectionData) -> list[tuple[str, dict[str, Any]]]:
    explicit_items = metadata.get("items", [])
    if explicit_items:
        entries = []
        for index, item in enumerate(explicit_items):
            merged = merge_metadata(metadata, item)
            item_key = str(item.get("id") or item.get("item_key") or index)
            entries.append((item_key, merged))
        return entries

    if len(inspection.asset_named_collections) > 1 and not metadata.get("entry_collection"):
        entries = []
        for name in inspection.asset_named_collections:
            item = merge_metadata(
                metadata,
                {
                    "display_name": name[len(constants.ASSET_COLLECTION_PREFIX) :].replace("_", " ").strip() or name,
                    "entry_collection": name,
                    "import_mode": "COLLECTION",
                },
            )
            entries.append((name, item))
        return entries

    return [("", metadata)]


def _apply_ui_state(entries: list[AssetEntry]) -> None:
    state = load_ui_state()
    favorites = set(state.get("favorites", []))
    recent = list(state.get("recent", []))
    validations = dict(state.get("validations", {}))
    recent_rank = {asset_id: index for index, asset_id in enumerate(recent)}

    for entry in entries:
        entry.is_favorite = entry.asset_id in favorites
        entry.recent_rank = recent_rank.get(entry.asset_id, 99999)
        if entry.asset_id in validations:
            entry.validation = ValidationReport.from_dict(validations[entry.asset_id])


def build_asset_entries_for_file(
    blend_path: Path,
    root_path: Path,
    root_label: str,
    grouping_mode: str,
) -> list[AssetEntry]:
    metadata, metadata_warnings, metadata_source = load_metadata_for_blend(blend_path)
    if metadata and not metadata.get("enabled", True) and not metadata.get("items"):
        return []

    inspection, inspection_warnings = _inspect_loaded_library(blend_path)
    warnings = metadata_warnings + inspection_warnings
    entries: list[AssetEntry] = []
    for item_key, item_metadata in _expanded_items(metadata, inspection):
        if not item_metadata.get("enabled", True):
            continue
        entry = _entry_from_metadata(
            blend_path=blend_path,
            root_path=root_path,
            root_label=root_label,
            metadata=item_metadata,
            metadata_source=metadata_source,
            inspection=inspection,
            warnings=warnings,
            grouping_mode=grouping_mode,
            item_key=item_key,
        )
        entries.append(entry)
    return entries


def scan_libraries(context: bpy.types.Context, force: bool = False) -> AssetIndex:
    global _AUTO_REFRESH_LAST_SIGNATURE
    prefs = addon_preferences(context)
    grouping_mode = getattr(prefs, "grouping_mode", "AUTO") if prefs else "AUTO"
    roots = enabled_root_definitions(context)
    if not roots:
        return clear_runtime_index()
    previous_index = load_index()
    previous_by_file: dict[str, list[AssetEntry]] = defaultdict(list)
    for entry in previous_index.entries:
        previous_by_file[entry.file_path].append(entry)

    entries: list[AssetEntry] = []
    root_payloads = list(roots)
    category_registry = _load_merged_category_registry(root_payloads)
    tag_registry = _load_merged_tag_registry(root_payloads)

    for root in roots:
        root_path = Path(root["path"])
        root_label = root["label"]
        for blend_path in sorted(root_path.rglob("*.blend"), key=lambda item: str(item).casefold()):
            mtime, size, signature = file_signature(blend_path)
            cached_entries = previous_by_file.get(str(blend_path), [])
            if (
                not force
                and cached_entries
                and all(entry.source_signature == signature for entry in cached_entries)
            ):
                entries.extend([_normalized_cached_entry(entry) for entry in cached_entries])
                continue

            entries.extend(
                build_asset_entries_for_file(
                    blend_path=blend_path,
                    root_path=root_path,
                    root_label=root_label,
                    grouping_mode=grouping_mode,
                )
            )

    _apply_ui_state(entries)
    entries.sort(key=lambda entry: (entry.category.casefold(), entry.subcategory.casefold(), entry.display_name.casefold()))

    index = AssetIndex(entries=entries, roots=root_payloads)
    save_index(index)
    runtime.set_index(index)
    runtime.set_category_registry(category_registry)
    runtime.set_tag_registry(tag_registry)
    preview_manager.clear()

    missing_preview_ids = [
        entry.asset_id for entry in index.entries if not entry.thumbnail_source and not Path(entry.thumbnail_cache).exists()
    ]
    if missing_preview_ids:
        from .thumbnail_render import generate_missing_previews

        generate_missing_previews(context, missing_preview_ids)
    _AUTO_REFRESH_LAST_SIGNATURE = _library_watch_signature(root_payloads)
    return index


def clear_runtime_index(persist: bool = True) -> AssetIndex:
    global _AUTO_REFRESH_LAST_SIGNATURE
    index = AssetIndex(entries=[], roots=[])
    if persist:
        save_index(index)
    runtime.set_index(index)
    runtime.set_category_registry({})
    runtime.set_tag_registry([])
    preview_manager.clear()
    _AUTO_REFRESH_LAST_SIGNATURE = ""
    return index


def load_cached_index_into_runtime(context: bpy.types.Context | None = None) -> AssetIndex:
    global _AUTO_REFRESH_LAST_SIGNATURE
    if context is not None and not enabled_root_definitions(context):
        return clear_runtime_index()
    index = load_index()
    if index.entries:
        index.entries = [_normalized_cached_entry(entry) for entry in index.entries]
    runtime.set_index(index)
    runtime.set_category_registry(_load_merged_category_registry(index.roots))
    runtime.set_tag_registry(_load_merged_tag_registry(index.roots))
    roots = enabled_root_definitions(context) if context is not None else index.roots
    _AUTO_REFRESH_LAST_SIGNATURE = _library_watch_signature(roots)
    return index


def _auto_refresh_timer() -> float | None:
    try:
        context = bpy.context
        prefs = addon_preferences(context)
        interval = float(getattr(prefs, "auto_refresh_interval", 20) if prefs else 20)
        interval = max(5.0, interval)
        enabled = bool(getattr(prefs, "auto_refresh_enabled", True) if prefs else True)
        window_manager = getattr(context, "window_manager", None)
        if window_manager is None or not hasattr(window_manager, "bgal_browser"):
            return interval

        roots = enabled_root_definitions(context)
        current_signature = _library_watch_signature(roots)

        global _AUTO_REFRESH_LAST_SIGNATURE
        if not enabled:
            _AUTO_REFRESH_LAST_SIGNATURE = current_signature
            return interval

        if not _AUTO_REFRESH_LAST_SIGNATURE:
            _AUTO_REFRESH_LAST_SIGNATURE = current_signature
            return interval

        if current_signature == _AUTO_REFRESH_LAST_SIGNATURE:
            return interval

        _AUTO_REFRESH_LAST_SIGNATURE = current_signature
        if roots:
            index = scan_libraries(context, force=False)
            from .properties import refresh_visible_assets

            refresh_visible_assets(context)
            window_manager.bgal_browser.status_text = f"Auto-refreshed {len(index.entries)} assets."
        else:
            clear_runtime_index()
            from .properties import refresh_visible_assets

            refresh_visible_assets(context)
            window_manager.bgal_browser.status_text = "No enabled library roots. Cached assets cleared."
    except Exception:
        pass
    prefs = addon_preferences(bpy.context)
    return max(5.0, float(getattr(prefs, "auto_refresh_interval", 20) if prefs else 20))


def ensure_auto_refresh_timer(context: bpy.types.Context | None = None) -> None:
    global _AUTO_REFRESH_LAST_SIGNATURE
    if context is not None:
        _AUTO_REFRESH_LAST_SIGNATURE = _library_watch_signature(enabled_root_definitions(context))
    if not bpy.app.timers.is_registered(_auto_refresh_timer):
        bpy.app.timers.register(_auto_refresh_timer, first_interval=10.0, persistent=True)


def stop_auto_refresh_timer() -> None:
    if bpy.app.timers.is_registered(_auto_refresh_timer):
        bpy.app.timers.unregister(_auto_refresh_timer)
