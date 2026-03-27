from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

from . import constants
from .properties import refresh_visible_assets
from .registration import safe_register_class, safe_unregister_class
from .scanner import clear_runtime_index, scan_libraries


def addon_preferences(context):
    addon = context.preferences.addons.get(constants.ADDON_PACKAGE)
    return addon.preferences if addon else None


class BGAL_OT_RootAdd(Operator):
    bl_idname = "bgal.root_add"
    bl_label = "Add Root Folder"
    bl_description = "Add a package asset library root folder"
    bl_options = {"REGISTER", "INTERNAL"}

    directory: StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        prefs = addon_preferences(context)
        if prefs is None:
            self.report({"ERROR"}, "Addon preferences are unavailable.")
            return {"CANCELLED"}

        directory = Path(bpy.path.abspath(self.directory)).resolve()
        if not directory.exists():
            self.report({"ERROR"}, "Selected folder does not exist.")
            return {"CANCELLED"}

        for item in prefs.library_roots:
            if Path(bpy.path.abspath(item.directory)).resolve() == directory:
                self.report({"INFO"}, "That root folder is already registered.")
                return {"CANCELLED"}

        item = prefs.library_roots.add()
        item.label = directory.name
        item.directory = str(directory)
        item.enabled = True
        prefs.active_root_index = len(prefs.library_roots) - 1
        self.report({"INFO"}, f"Added root folder: {directory}")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class BGAL_OT_RootRemove(Operator):
    bl_idname = "bgal.root_remove"
    bl_label = "Remove Root Folder"
    bl_description = "Remove the selected root folder"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        prefs = addon_preferences(context)
        if prefs is None or not prefs.library_roots:
            return {"CANCELLED"}

        index = max(0, min(prefs.active_root_index, len(prefs.library_roots) - 1))
        prefs.library_roots.remove(index)
        prefs.active_root_index = max(0, min(index, len(prefs.library_roots) - 1))
        if not any(item.enabled and item.directory for item in prefs.library_roots):
            clear_runtime_index()
            refresh_visible_assets(context)
            context.window_manager.bgal_browser.status_text = "Cleared cached assets."
        return {"FINISHED"}


class BGAL_OT_ScanLibraries(Operator):
    bl_idname = "bgal.scan_libraries"
    bl_label = "Scan Asset Libraries"
    bl_description = "Scan the configured package asset roots and refresh the browser index"
    bl_options = {"REGISTER"}

    force: BoolProperty(name="Force Rescan", default=True)

    def execute(self, context):
        prefs = addon_preferences(context)
        if prefs is None or not any(item.enabled for item in prefs.library_roots):
            clear_runtime_index()
            refresh_visible_assets(context)
            context.window_manager.bgal_browser.status_text = "No enabled library roots. Cached assets cleared."
            self.report({"INFO"}, "No enabled library roots. Cached assets cleared.")
            return {"FINISHED"}

        index = scan_libraries(context, force=self.force)
        refresh_visible_assets(context)
        context.window_manager.bgal_browser.status_text = f"Indexed {len(index.entries)} assets."
        self.report({"INFO"}, f"Indexed {len(index.entries)} assets.")
        return {"FINISHED"}


CLASSES = (
    BGAL_OT_RootAdd,
    BGAL_OT_RootRemove,
    BGAL_OT_ScanLibraries,
)


def register() -> None:
    for cls in CLASSES:
        safe_register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
