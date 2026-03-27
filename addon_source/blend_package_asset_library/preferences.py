from __future__ import annotations

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty
from bpy.types import AddonPreferences, UIList

from . import constants
from .properties import BGAL_PG_LibraryRoot
from .registration import safe_register_class, safe_unregister_class


class BGAL_UL_LibraryRoots(UIList):
    bl_idname = "BGAL_UL_library_roots"

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index=0,
        flt_flag=0,
    ):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        column = row.column(align=True)
        column.prop(item, "label", text="", emboss=False)
        column.prop(item, "directory", text="", emboss=False)


class BGAL_AddonPreferences(AddonPreferences):
    bl_idname = constants.ADDON_PACKAGE

    library_roots: CollectionProperty(type=BGAL_PG_LibraryRoot)
    active_root_index: IntProperty(default=0)
    grouping_mode: EnumProperty(name="Grouping", items=constants.GROUPING_MODE_ITEMS, default="AUTO")
    auto_generate_missing_previews: BoolProperty(
        name="Auto Generate Missing Previews",
        description="Render cached previews for entries that do not provide a thumbnail image",
        default=True,
    )
    auto_refresh_enabled: BoolProperty(
        name="Auto Refresh Libraries",
        description="Periodically check enabled roots for new, removed, or changed library files and rescan only when needed",
        default=True,
    )
    auto_refresh_interval: IntProperty(
        name="Auto Refresh Interval (Seconds)",
        description="How often to check enabled library roots for changes",
        default=20,
        min=5,
        soft_max=300,
    )
    check_updates_on_startup: BoolProperty(
        name="Check For Updates On Startup",
        description="Check GitHub for a newer release when Blender starts",
        default=True,
    )
    notify_update_available: BoolProperty(
        name="Notify When Updates Are Available",
        description="Show an in-app notification when a newer release is detected",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="GTA 000 - Custom Asset Library", icon="FILE_FOLDER")

        row = layout.row()
        row.template_list(
            "BGAL_UL_library_roots",
            "",
            self,
            "library_roots",
            self,
            "active_root_index",
            rows=4,
        )
        buttons = row.column(align=True)
        buttons.operator("bgal.root_add", text="", icon="ADD")
        buttons.operator("bgal.root_remove", text="", icon="REMOVE")
        buttons.operator("bgal.scan_libraries", text="", icon="FILE_REFRESH").force = True

        box = layout.box()
        box.label(text="Scanning And Refresh", icon="FILE_REFRESH")
        box.prop(self, "grouping_mode")
        box.prop(self, "auto_generate_missing_previews")
        box.prop(self, "auto_refresh_enabled")
        interval = box.row()
        interval.enabled = self.auto_refresh_enabled
        interval.prop(self, "auto_refresh_interval")

        updates = layout.box()
        updates.label(text="Updates", icon="IMPORT")
        updates.prop(self, "check_updates_on_startup")
        notify_row = updates.row()
        notify_row.enabled = self.check_updates_on_startup
        notify_row.prop(self, "notify_update_available")
        actions = updates.row(align=True)
        actions.operator("bgal.check_for_updates", text="Check Now", icon="FILE_REFRESH")
        actions.operator("bgal.open_update_release", text="Open Release", icon="URL")

        support = layout.box()
        support.label(text="Project", icon="INFO")
        support.label(text="Maintainer: GTA 000 using Codex")

        website = support.box()
        website.label(text="Website", icon="URL")
        website.label(text="GTA 000")
        open_site = website.operator("wm.url_open", text="Open gta000.net", icon="URL")
        open_site.url = "https://gta000.net/"

        instructions = support.box()
        instructions.label(text="Instructions", icon="HELP")
        instructions.label(text="GitHub Wiki")
        open_wiki = instructions.operator("wm.url_open", text="Open Wiki", icon="HELP")
        open_wiki.url = "https://github.com/paulc1986/File-Asset-Library/wiki"

        if not self.library_roots:
            info = layout.box()
            info.label(text="Add one or more root folders to start indexing .blend packages.", icon="INFO")


CLASSES = (
    BGAL_UL_LibraryRoots,
    BGAL_AddonPreferences,
)


def register() -> None:
    for cls in CLASSES:
        safe_register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
