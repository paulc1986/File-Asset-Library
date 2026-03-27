from __future__ import annotations

from pathlib import Path

from mathutils import Vector

import bpy

from .utils import dedupe_preserve_order, normalized_blend_path


def validate_source_blend(filepath: str) -> str:
    normalized = normalized_blend_path(filepath)
    current_file = normalized_blend_path(bpy.data.filepath) if bpy.data.filepath else ""
    if not normalized:
        raise FileNotFoundError("The asset source file path is empty.")
    normalized = bpy.path.native_pathsep(normalized)
    if not bpy.path.abspath(normalized):
        raise FileNotFoundError(f"Invalid asset source path: {filepath}")
    if not Path(normalized).exists():
        raise FileNotFoundError(f"Asset source file not found: {normalized}")
    if current_file and normalized.casefold() == current_file.casefold():
        raise RuntimeError(
            "Cannot append, link, validate, or render previews from the currently open .blend file. "
            "Open a different working scene, then import this package from the library."
        )
    return normalized


def load_asset_datablocks(
    filepath: str,
    target_kind: str,
    target_names: list[str],
    *,
    link: bool,
) -> dict[str, list]:
    filepath = validate_source_blend(filepath)
    data_to_collections = []
    data_to_objects = []
    data_to_actions = []

    with bpy.data.libraries.load(filepath, link=link) as (data_from, data_to):
        if target_kind == "COLLECTION":
            data_to.collections = list(target_names)
        else:
            names = list(target_names)
            if not names:
                names = list(data_from.objects)
            data_to.objects = names
        data_to.actions = list(data_from.actions)
        data_to_collections = data_to.collections
        data_to_objects = data_to.objects
        data_to_actions = data_to.actions

    return {
        "collections": [item for item in data_to_collections if item is not None],
        "objects": [item for item in data_to_objects if item is not None],
        "actions": [item for item in data_to_actions if item is not None],
    }


def recursive_collection_objects(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    objects = list(collection.objects)
    for child in collection.children:
        objects.extend(recursive_collection_objects(child))
    return dedupe_preserve_order(objects)


def gather_imported_objects(collections: list, objects: list) -> list[bpy.types.Object]:
    combined = list(objects)
    for collection in collections:
        combined.extend(recursive_collection_objects(collection))
    return dedupe_preserve_order(combined)


def link_to_collection(
    destination: bpy.types.Collection,
    collections: list,
    objects: list,
) -> None:
    for collection in collections:
        if destination.children.get(collection.name) is None:
            destination.children.link(collection)
    for obj in objects:
        if not obj.users_collection:
            destination.objects.link(obj)


def root_objects_for_transform(collections: list, objects: list) -> list[bpy.types.Object]:
    imported_objects = gather_imported_objects(collections, objects)
    imported_set = {obj for obj in imported_objects}
    roots = [obj for obj in imported_objects if obj.parent not in imported_set]
    return roots or imported_objects


def imported_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector] | None:
    if not objects:
        return None
    mins = Vector((float("inf"), float("inf"), float("inf")))
    maxs = Vector((float("-inf"), float("-inf"), float("-inf")))
    found = False
    for obj in objects:
        if obj.type == "EMPTY" and obj.instance_collection is None:
            continue
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            mins.x = min(mins.x, world_corner.x)
            mins.y = min(mins.y, world_corner.y)
            mins.z = min(mins.z, world_corner.z)
            maxs.x = max(maxs.x, world_corner.x)
            maxs.y = max(maxs.y, world_corner.y)
            maxs.z = max(maxs.z, world_corner.z)
            found = True
    if not found:
        return None
    return mins, maxs


def offset_root_objects(roots: list[bpy.types.Object], delta: Vector) -> None:
    if delta.length == 0.0:
        return
    for obj in roots:
        obj.location += delta


def gather_related_ids(collections: list, objects: list, actions: list) -> list:
    related = list(collections) + list(objects) + list(actions)
    for obj in gather_imported_objects(collections, objects):
        if obj.data is not None:
            related.append(obj.data)
        for slot in obj.material_slots:
            if slot.material is not None:
                related.append(slot.material)
        if obj.animation_data and obj.animation_data.action is not None:
            related.append(obj.animation_data.action)
    return dedupe_preserve_order(related)
