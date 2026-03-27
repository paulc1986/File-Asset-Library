from __future__ import annotations

from math import radians
from pathlib import Path

from mathutils import Vector

import bpy

from .library_io import gather_imported_objects, gather_related_ids, imported_bounds, link_to_collection, load_asset_datablocks
from .preview_cache import preview_manager
from . import runtime
from .utils import ensure_directory, safe_remove_ids


def _crop_transparent_borders(output_path: Path, padding: int = 8) -> None:
    image = None
    cropped = None
    try:
        image = bpy.data.images.load(str(output_path), check_existing=False)
        width, height = image.size
        pixels = list(image.pixels[:])
        if not pixels or width <= 0 or height <= 0:
            return

        min_x = width
        min_y = height
        max_x = -1
        max_y = -1
        for y in range(height):
            row_offset = y * width * 4
            for x in range(width):
                alpha = pixels[row_offset + x * 4 + 3]
                if alpha <= 0.01:
                    continue
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

        if max_x < min_x or max_y < min_y:
            return

        min_x = max(min_x - padding, 0)
        min_y = max(min_y - padding, 0)
        max_x = min(max_x + padding, width - 1)
        max_y = min(max_y + padding, height - 1)
        crop_w = max_x - min_x + 1
        crop_h = max_y - min_y + 1

        if crop_w == width and crop_h == height:
            return

        cropped_pixels = [0.0] * (crop_w * crop_h * 4)
        for y in range(crop_h):
            src_y = min_y + y
            src_start = (src_y * width + min_x) * 4
            src_end = src_start + crop_w * 4
            dst_start = y * crop_w * 4
            cropped_pixels[dst_start : dst_start + crop_w * 4] = pixels[src_start:src_end]

        cropped = bpy.data.images.new(f"{image.name}_cropped", width=crop_w, height=crop_h, alpha=True)
        cropped.pixels = cropped_pixels
        cropped.filepath_raw = str(output_path)
        cropped.file_format = "PNG"
        cropped.save()
    finally:
        safe_remove_ids([cropped, image])


def _look_at_rotation(camera_location: Vector, target: Vector):
    direction = (target - camera_location).normalized()
    return direction.to_track_quat("-Z", "Y").to_euler()


def _build_preview_scene(name: str) -> tuple[bpy.types.Scene, bpy.types.Collection, list]:
    scene = bpy.data.scenes.new(name)
    root_collection = bpy.data.collections.new(f"{name}_Root")
    scene.collection.children.link(root_collection)

    camera_data = bpy.data.cameras.new(f"{name}_Camera")
    camera_data.type = "ORTHO"
    camera_data.clip_end = 1000.0
    camera = bpy.data.objects.new(camera_data.name, camera_data)
    root_collection.objects.link(camera)
    scene.camera = camera

    key_light = bpy.data.lights.new(f"{name}_Key", type="AREA")
    key_light.energy = 4000.0
    key_object = bpy.data.objects.new(key_light.name, key_light)
    root_collection.objects.link(key_object)

    fill_light = bpy.data.lights.new(f"{name}_Fill", type="SUN")
    fill_light.energy = 1.6
    fill_object = bpy.data.objects.new(fill_light.name, fill_light)
    root_collection.objects.link(fill_object)

    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = True
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        pass

    return scene, root_collection, [camera, camera_data, key_object, key_light, fill_object, fill_light]


def _frame_camera(scene: bpy.types.Scene, root_collection: bpy.types.Collection, imported_objects: list[bpy.types.Object]) -> None:
    camera = scene.camera
    if camera is None:
        return
    renderable_objects = [
        obj
        for obj in imported_objects
        if obj.type in {"MESH", "CURVE", "SURFACE", "FONT", "META", "VOLUME"}
        or obj.instance_collection is not None
    ]
    bounds = imported_bounds(renderable_objects or imported_objects)
    if bounds is None:
        camera.location = Vector((4.0, -4.0, 3.0))
        camera.rotation_euler = (radians(60.0), 0.0, radians(45.0))
        return

    mins, maxs = bounds
    center = (mins + maxs) * 0.5
    size = max(maxs.x - mins.x, maxs.y - mins.y, maxs.z - mins.z, 0.25)
    distance = size * 1.15 + 0.35

    camera.location = center + Vector((-distance, distance, distance * 0.72))
    camera.rotation_euler = _look_at_rotation(camera.location, center)

    camera_local = camera.matrix_world.inverted()
    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")
    found = False
    for obj in renderable_objects or imported_objects:
        for corner in obj.bound_box:
            local = camera_local @ (obj.matrix_world @ Vector(corner))
            min_x = min(min_x, local.x)
            max_x = max(max_x, local.x)
            min_y = min(min_y, local.y)
            max_y = max(max_y, local.y)
            found = True
    if found:
        width = max_x - min_x
        height = max_y - min_y
        camera.data.ortho_scale = max(max(width, height) * 1.08, 0.35)
    else:
        camera.data.ortho_scale = max(size * 1.15, 0.35)

    key_object = root_collection.objects.get(f"{scene.name}_Key")
    if key_object is not None:
        key_object.location = center + Vector((-distance * 0.95, distance * 0.45, distance * 1.15))
        key_object.rotation_euler = (radians(55.0), 0.0, radians(-145.0))

    fill_object = root_collection.objects.get(f"{scene.name}_Fill")
    if fill_object is not None:
        fill_object.rotation_euler = (radians(35.0), 0.0, radians(35.0))


def render_thumbnail_for_asset(context: bpy.types.Context, asset_id: str) -> tuple[bool, str]:
    asset = runtime.get_asset(asset_id)
    if asset is None:
        return False, "Asset not found in the runtime index."

    output_path = Path(asset.thumbnail_cache)
    ensure_directory(output_path.parent)

    scene = None
    root_collection = None
    preview_ids = []
    cleanup_ids = []
    imported = {"collections": [], "objects": [], "actions": []}
    original_scene = context.window.scene if context.window else None

    try:
        scene, root_collection, preview_ids = _build_preview_scene(f"BGALPreview_{asset.asset_id}")
        imported = load_asset_datablocks(
            asset.file_path,
            asset.target_kind,
            list(asset.target_names),
            link=False,
        )
        link_to_collection(root_collection, imported["collections"], imported["objects"])

        imported_objects = gather_imported_objects(imported["collections"], imported["objects"])
        _frame_camera(scene, root_collection, imported_objects)
        scene.render.filepath = str(output_path)

        if context.window:
            context.window.scene = scene
        bpy.ops.render.render(write_still=True, use_viewport=False)
        _crop_transparent_borders(output_path)
        preview_manager.invalidate(asset.asset_id)
    except Exception as exc:
        return False, str(exc)
    finally:
        if context.window and original_scene is not None:
            context.window.scene = original_scene
        cleanup_ids.extend(gather_related_ids(imported["collections"], imported["objects"], imported["actions"]))
        if scene is not None:
            cleanup_ids.extend(preview_ids)
            cleanup_ids.append(root_collection)
            cleanup_ids.append(scene)
        safe_remove_ids(cleanup_ids)

    return output_path.exists(), ("" if output_path.exists() else "Thumbnail render did not create an output file.")


def generate_missing_previews(context: bpy.types.Context, asset_ids: list[str]) -> int:
    generated = 0
    for asset_id in asset_ids:
        asset = runtime.get_asset(asset_id)
        if asset is None:
            continue
        cache_path = Path(asset.thumbnail_cache)
        if cache_path.exists():
            continue
        success, _message = render_thumbnail_for_asset(context, asset_id)
        if success:
            generated += 1
    return generated
