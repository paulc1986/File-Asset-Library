from __future__ import annotations

import time

from mathutils import Vector

import bpy

from . import runtime
from .index_store import register_recent
from .library_io import (
    gather_imported_objects,
    gather_related_ids,
    imported_bounds,
    link_to_collection,
    load_asset_datablocks,
    offset_root_objects,
    root_objects_for_transform,
)
from .utils import dedupe_preserve_order, safe_slug


def _selected_destination_collection(context: bpy.types.Context) -> bpy.types.Collection:
    return context.collection or context.scene.collection


def _make_id_local(id_block) -> None:
    if id_block is None or getattr(id_block, "library", None) is None:
        return
    try:
        id_block.make_local()
    except Exception:
        pass


def _make_import_local(collections: list, objects: list) -> None:
    related = gather_related_ids(collections, objects, [])
    imported_objects = gather_imported_objects(collections, objects)
    for obj in imported_objects:
        if obj.animation_data and obj.animation_data.action is not None:
            related.append(obj.animation_data.action)
    for item in dedupe_preserve_order(related):
        _make_id_local(item)


def _prefix_id_name(id_block, prefix: str) -> None:
    if id_block is None or getattr(id_block, "library", None) is not None:
        return
    if id_block.name.startswith(prefix):
        return
    id_block.name = f"{prefix}{id_block.name}"


def _apply_namespace(prefix: str, collections: list, objects: list, created_instances: list) -> None:
    if not prefix:
        return
    name_prefix = f"{safe_slug(prefix)}_"
    imported_objects = gather_imported_objects(collections, objects)
    for collection in collections:
        _prefix_id_name(collection, name_prefix)
    for obj in imported_objects:
        _prefix_id_name(obj, name_prefix)
        _prefix_id_name(obj.data, name_prefix)
        if obj.animation_data and obj.animation_data.action is not None:
            _prefix_id_name(obj.animation_data.action, name_prefix)
        for slot in obj.material_slots:
            _prefix_id_name(slot.material, name_prefix)
    for obj in created_instances:
        _prefix_id_name(obj, name_prefix)


def _anchor_center(objects: list[bpy.types.Object]) -> Vector:
    bounds = imported_bounds(objects)
    if bounds is None:
        return Vector((0.0, 0.0, 0.0))
    mins, maxs = bounds
    return (mins + maxs) * 0.5


def _place_at_cursor(context: bpy.types.Context, collections: list, objects: list, created_instances: list) -> None:
    cursor_location = context.scene.cursor.location.copy()
    if created_instances:
        if len(created_instances) == 1:
            created_instances[0].location = cursor_location
            return
        bounds = imported_bounds(created_instances)
        anchor = _anchor_center(created_instances) if bounds else Vector((0.0, 0.0, 0.0))
        delta = cursor_location - anchor
        for obj in created_instances:
            obj.location += delta
        return

    roots = root_objects_for_transform(collections, objects)
    anchor = _anchor_center(roots)
    delta = cursor_location - anchor
    offset_root_objects(roots, delta)


def _create_collection_instances(
    destination: bpy.types.Collection,
    collections: list,
    asset_name: str,
) -> list[bpy.types.Object]:
    if not collections:
        return []
    created: list[bpy.types.Object] = []
    parent = None
    if len(collections) > 1:
        parent = bpy.data.objects.new(f"{asset_name}_Package", None)
        destination.objects.link(parent)
        created.append(parent)
    for collection in collections:
        instance = bpy.data.objects.new(f"{asset_name}_{collection.name}", None)
        instance.instance_type = "COLLECTION"
        instance.instance_collection = collection
        if parent is not None:
            instance.parent = parent
        destination.objects.link(instance)
        created.append(instance)
    return created


def _select_imported(context: bpy.types.Context, objects: list[bpy.types.Object]) -> None:
    for obj in context.selected_objects:
        obj.select_set(False)
    active = None
    for obj in objects:
        if context.view_layer.objects.get(obj.name) is not None:
            obj.select_set(True)
            if active is None:
                active = obj
    if active is not None:
        context.view_layer.objects.active = active


def import_asset(
    context: bpy.types.Context,
    asset_id: str,
    *,
    link_mode: str,
    make_local_after_link: bool,
    namespace_prefix: str,
    place_mode: str,
    place_as_collection_instance: bool,
) -> tuple[bool, str, list[bpy.types.Object]]:
    asset = runtime.get_asset(asset_id)
    if asset is None:
        return False, "Asset not found in the library index.", []

    try:
        imported = load_asset_datablocks(
            asset.file_path,
            asset.target_kind,
            list(asset.target_names),
            link=(link_mode == "LINK"),
        )
    except Exception as exc:
        return False, str(exc), []
    destination = _selected_destination_collection(context)
    created_instances: list[bpy.types.Object] = []
    warnings: list[str] = []

    if place_as_collection_instance and imported["collections"]:
        created_instances = _create_collection_instances(destination, imported["collections"], safe_slug(asset.display_name))
    else:
        link_to_collection(destination, imported["collections"], imported["objects"])

    if link_mode == "LINK" and make_local_after_link:
        _make_import_local(imported["collections"], imported["objects"])
    elif link_mode == "LINK" and namespace_prefix:
        warnings.append("Namespace was only applied to created instance empties because the linked data stayed external.")

    _apply_namespace(namespace_prefix, imported["collections"], imported["objects"], created_instances)

    if place_mode == "CURSOR":
        _place_at_cursor(context, imported["collections"], imported["objects"], created_instances)

    selection = created_instances or root_objects_for_transform(imported["collections"], imported["objects"])
    _select_imported(context, selection)
    register_recent(asset.asset_id)
    asset.last_used_at = time.time()

    if warnings:
        return True, " ".join(warnings), selection
    return True, "", selection
