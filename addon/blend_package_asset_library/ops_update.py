from __future__ import annotations

import bpy
from bpy.types import Operator

from . import constants, updater
from .registration import safe_register_class, safe_unregister_class

RELEASE_URL = getattr(constants, "RELEASE_URL", "https://github.com/paulc1986/File-Asset-Library/releases/tag/Release")


class BGAL_OT_CheckForUpdates(Operator):
    bl_idname = "bgal.check_for_updates"
    bl_label = "Check For Updates"
    bl_description = "Check GitHub for a newer add-on release"

    def execute(self, context):
        started = updater.request_update_check(context, startup=False, force=True)
        if not started:
            self.report({"INFO"}, "An update check is already in progress.")
            return {"CANCELLED"}
        self.report({"INFO"}, "Checking GitHub for updates...")
        return {"FINISHED"}


class BGAL_OT_OpenUpdateRelease(Operator):
    bl_idname = "bgal.open_update_release"
    bl_label = "Open Release Page"
    bl_description = "Open the add-on release page in your web browser"

    use_download_url: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        browser = getattr(context.window_manager, "bgal_browser", None)
        url = RELEASE_URL
        if browser is not None:
            if self.use_download_url:
                url = browser.update_download_url or browser.update_release_url or RELEASE_URL
            else:
                url = browser.update_release_url or browser.update_download_url or RELEASE_URL
        bpy.ops.wm.url_open(url=url)
        return {"FINISHED"}


CLASSES = (
    BGAL_OT_CheckForUpdates,
    BGAL_OT_OpenUpdateRelease,
)


def register() -> None:
    for cls in CLASSES:
        safe_register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
