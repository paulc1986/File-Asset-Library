bl_info = {
    "name": "GTA 000 - Custom Asset Library",
    "author": "GTA 000 using Codex",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Custom Asset Library",
    "description": "Browse, validate, preview, and import whole .blend packages as reusable assets.",
    "doc_url": "https://github.com/paulc1986/File-Asset-Library/wiki",
    "category": "Asset Management",
}


import bpy

from . import ops_asset, ops_library, ops_update, preferences, properties, scanner, ui, updater
from .preview_cache import preview_manager


def _safe_call(func, *args, **kwargs):
    if not callable(func):
        return None
    try:
        return func(*args, **kwargs)
    except Exception:
        return None


def _pre_register_cleanup():
    cleanup_steps = (
        getattr(updater, "stop_update_timer", None),
        getattr(scanner, "stop_auto_refresh_timer", None),
        getattr(ui, "unregister", None),
        getattr(ops_update, "unregister", None),
        getattr(ops_asset, "unregister", None),
        getattr(ops_library, "unregister", None),
        getattr(preferences, "unregister", None),
        getattr(properties, "unregister", None),
        getattr(preview_manager, "unregister", None),
    )
    for step in cleanup_steps:
        if not callable(step):
            continue
        try:
            step()
        except Exception:
            pass


def register():
    _pre_register_cleanup()
    preview_manager.register()
    properties.register()
    preferences.register()
    ops_library.register()
    ops_asset.register()
    ops_update.register()
    ui.register()
    _safe_call(getattr(scanner, "load_cached_index_into_runtime", None), bpy.context)
    _safe_call(getattr(scanner, "ensure_auto_refresh_timer", None), bpy.context)
    _safe_call(getattr(updater, "reset_update_state", None), bpy.context)
    _safe_call(getattr(updater, "ensure_update_timer", None), bpy.context)
    try:
        if hasattr(bpy.context.window_manager, "bgal_browser"):
            properties.refresh_visible_assets(bpy.context)
    except Exception:
        pass


def unregister():
    _safe_call(getattr(updater, "stop_update_timer", None))
    _safe_call(getattr(scanner, "stop_auto_refresh_timer", None))
    _safe_call(getattr(ui, "unregister", None))
    _safe_call(getattr(ops_update, "unregister", None))
    _safe_call(getattr(ops_asset, "unregister", None))
    _safe_call(getattr(ops_library, "unregister", None))
    _safe_call(getattr(preferences, "unregister", None))
    _safe_call(getattr(properties, "unregister", None))
    _safe_call(getattr(preview_manager, "unregister", None))
