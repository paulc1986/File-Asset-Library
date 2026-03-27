from __future__ import annotations

import time
from pathlib import Path

import bpy

from . import runtime
from .index_store import store_validation
from .library_io import gather_imported_objects, gather_related_ids, validate_source_blend
from .models import ValidationReport
from .utils import safe_remove_ids


def validate_asset(asset_id: str) -> ValidationReport:
    asset = runtime.get_asset(asset_id)
    if asset is None:
        return ValidationReport(status="ERROR", warnings=["Asset not found."], checked_at=time.time())

    warnings: list[str] = []
    collections = []
    objects = []
    materials = []
    images = []
    actions = []

    try:
        source_path = validate_source_blend(asset.file_path)
        with bpy.data.libraries.load(source_path, link=True) as (data_from, data_to):
            data_to.collections = list(data_from.collections)
            data_to.objects = list(data_from.objects)
            data_to.materials = list(data_from.materials)
            data_to.images = list(data_from.images)
            data_to.actions = list(data_from.actions)
        collections = [item for item in data_to.collections if item is not None]
        objects = [item for item in data_to.objects if item is not None]
        materials = [item for item in data_to.materials if item is not None]
        images = [item for item in data_to.images if item is not None]
        actions = [item for item in data_to.actions if item is not None]

        collection_names = {collection.name for collection in collections}
        object_names = {obj.name for obj in objects}
        for name in asset.target_names:
            if asset.target_kind == "COLLECTION" and name not in collection_names:
                warnings.append(f"Missing target collection: {name}")
            if asset.target_kind != "COLLECTION" and name not in object_names:
                warnings.append(f"Missing target object: {name}")

        imported_objects = gather_imported_objects(collections, objects)
        relevant_objects = imported_objects
        if asset.target_kind != "COLLECTION" and asset.target_names:
            target_set = set(asset.target_names)
            relevant_objects = [obj for obj in imported_objects if obj.name in target_set]

        for obj in relevant_objects:
            if obj.type in {"MESH", "CURVE", "SURFACE", "FONT"} and not obj.material_slots:
                warnings.append(f"Object has no material slots: {obj.name}")

        for image in images:
            if image.source not in {"FILE", "SEQUENCE", "MOVIE"}:
                continue
            resolved = bpy.path.abspath(image.filepath, library=image.library)
            if resolved and not Path(resolved).exists():
                warnings.append(f"Missing external texture: {Path(resolved).name}")

        if not asset.thumbnail_source and not Path(asset.thumbnail_cache).exists():
            warnings.append("No preview image found or generated.")
    except Exception as exc:
        warnings.append(f"Validation failed: {exc}")
    finally:
        cleanup_ids = gather_related_ids(collections, objects, actions) + materials + images
        safe_remove_ids(cleanup_ids)

    status = "OK" if not warnings else "WARN"
    report = ValidationReport(status=status, warnings=warnings, checked_at=time.time())
    asset.validation = report
    store_validation(asset.asset_id, report.to_dict())
    return report
