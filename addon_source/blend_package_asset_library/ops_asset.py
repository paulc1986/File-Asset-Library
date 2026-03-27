from __future__ import annotations

from mathutils import Vector
from pathlib import Path

import bpy
from bpy_extras import view3d_utils
from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator

from . import runtime
from .importer import import_asset
from .index_store import toggle_favorite
from .metadata import (
    clear_user_override_for_asset,
    remove_category_registry_entry,
    remove_subcategory_registry_entry,
    remove_tag_registry_entry,
    rename_category_registry_entry,
    rename_subcategory_registry_entry,
    rename_tag_registry_entry,
    save_category_registry_entry,
    save_tag_registry_entry,
    save_user_override_for_asset,
)
from .properties import (
    get_active_asset,
    refresh_category_manager_lists,
    refresh_tag_manager_lists,
    refresh_visible_assets,
    selected_manager_category,
    selected_manager_subcategory,
    selected_manager_tag,
    set_active_asset_id,
    sync_editor_fields,
)
from .registration import safe_register_class, safe_unregister_class
from .scanner import scan_libraries
from .thumbnail_render import render_thumbnail_for_asset
from .utils import open_blend_in_new_instance, open_in_file_browser
from .validator import validate_asset
from . import constants
from .utils import normalize_tags


def _resolve_asset_id(context: bpy.types.Context, operator_asset_id: str) -> str:
    if operator_asset_id:
        return operator_asset_id
    asset = get_active_asset(context)
    return asset.asset_id if asset else ""


def _addon_preferences(context: bpy.types.Context):
    addon = context.preferences.addons.get(constants.ADDON_PACKAGE)
    return addon.preferences if addon else None


def _resolve_category_root(context: bpy.types.Context, explicit_root_path: str, asset) -> Path | None:
    if explicit_root_path:
        return Path(bpy.path.abspath(explicit_root_path)).resolve()
    if asset is not None and asset.root_path:
        return Path(asset.root_path)
    prefs = _addon_preferences(context)
    if prefs is None or not prefs.library_roots:
        return None
    index = max(0, min(prefs.active_root_index, len(prefs.library_roots) - 1))
    directory = prefs.library_roots[index].directory
    if not directory:
        return None
    return Path(bpy.path.abspath(directory)).resolve()


def _refresh_after_category_change(context: bpy.types.Context) -> None:
    scan_libraries(context, force=True)
    refresh_visible_assets(context)
    refresh_category_manager_lists(context)
    refresh_tag_manager_lists(context)


def _ensure_tags_in_registry(root_path: Path, tags: list[str]) -> None:
    for tag in tags:
        if tag:
            save_tag_registry_entry(root_path, tag)


def _select_manager_category_by_name(browser, name: str) -> None:
    for index, item in enumerate(browser.manager_categories):
        if item.name == name:
            browser.manager_category_index = index
            break


def _select_manager_subcategory_by_name(browser, name: str) -> None:
    for index, item in enumerate(browser.manager_subcategories):
        if item.name == name:
            browser.manager_subcategory_index = index
            break


def _select_manager_tag_by_name(browser, name: str) -> None:
    for index, item in enumerate(browser.manager_tags):
        if item.name == name:
            browser.manager_tag_index = index
            break


def _browser_import_settings(context: bpy.types.Context, asset) -> tuple[str, bool, str, bool]:
    browser = context.window_manager.bgal_browser
    namespace_prefix = ""
    if browser.use_namespace:
        namespace_prefix = browser.namespace_prefix.strip() or asset.display_name
    return (
        browser.link_mode,
        browser.make_local_after_link,
        namespace_prefix,
        browser.place_as_collection_instance,
    )


def _view3d_context_from_window(window: bpy.types.Window, mouse_x: int, mouse_y: int):
    screen = window.screen
    if screen is None:
        return None, None, None
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        if not (area.x <= mouse_x < area.x + area.width and area.y <= mouse_y < area.y + area.height):
            continue
        for region in area.regions:
            if region.type != "WINDOW":
                continue
            if region.x <= mouse_x < region.x + region.width and region.y <= mouse_y < region.y + region.height:
                return area, region, area.spaces.active.region_3d
    return None, None, None


def _placement_location(context: bpy.types.Context, mouse_x: int, mouse_y: int) -> Vector | None:
    area, region, region_3d = _view3d_context_from_window(context.window, mouse_x, mouse_y)
    if area is None or region is None or region_3d is None:
        return None
    coord = (mouse_x - region.x, mouse_y - region.y)
    depsgraph = context.evaluated_depsgraph_get()
    origin = view3d_utils.region_2d_to_origin_3d(region, region_3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, region_3d, coord)
    hit, location, _normal, _index, _obj, _matrix = context.scene.ray_cast(depsgraph, origin, direction)
    if hit:
        return location

    plane_origin = context.scene.cursor.location.copy()
    plane_normal = Vector((0.0, 0.0, 1.0))
    denominator = direction.dot(plane_normal)
    if abs(denominator) < 1e-6:
        return plane_origin
    distance = (plane_origin - origin).dot(plane_normal) / denominator
    if distance < 0.0:
        return plane_origin
    return origin + direction * distance


class BGAL_OT_ImportAsset(Operator):
    bl_idname = "bgal.import_asset"
    bl_label = "Import Asset"
    bl_description = "Append or link the selected asset package into the current scene"
    bl_options = {"REGISTER", "UNDO"}

    asset_id: StringProperty()
    mode_override: EnumProperty(
        name="Mode",
        items=(
            ("USE_BROWSER", "Use Browser Setting", ""),
            ("APPEND", "Append", ""),
            ("LINK", "Link", ""),
        ),
        default="USE_BROWSER",
    )

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        browser = context.window_manager.bgal_browser
        if asset is None:
            self.report({"WARNING"}, "Select an asset first.")
            return {"CANCELLED"}

        link_mode = browser.link_mode if self.mode_override == "USE_BROWSER" else self.mode_override
        namespace_prefix = ""
        if browser.use_namespace:
            namespace_prefix = browser.namespace_prefix.strip() or asset.display_name

        success, message, _selection = import_asset(
            context,
            asset_id,
            link_mode=link_mode,
            make_local_after_link=browser.make_local_after_link,
            namespace_prefix=namespace_prefix,
            place_mode=browser.placement_mode,
            place_as_collection_instance=browser.place_as_collection_instance,
        )
        refresh_visible_assets(context)
        browser.status_text = message or f"Imported {asset.display_name}"
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        if message:
            self.report({"INFO"}, message)
        return {"FINISHED"}


class BGAL_OT_SelectAsset(Operator):
    bl_idname = "bgal.select_asset"
    bl_label = "Select Asset"
    bl_description = "Select this asset in the package browser"
    bl_options = {"INTERNAL"}

    asset_id: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        if not asset_id:
            return {"CANCELLED"}
        set_active_asset_id(context, asset_id)
        return {"FINISHED"}


class BGAL_OT_SaveAssetOverrides(Operator):
    bl_idname = "bgal.save_asset_overrides"
    bl_label = "Save Library Overrides"
    bl_description = "Rename this asset for your library and assign custom category values"
    bl_options = {"REGISTER", "UNDO"}

    asset_id: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        browser = context.window_manager.bgal_browser
        if asset is None:
            return {"CANCELLED"}

        display_name = browser.editor_display_name.strip() or asset.base_display_name
        if browser.editor_category == constants.ENUM_ADD_NEW_CATEGORY_IDENTIFIER:
            category = browser.editor_new_category_name.strip()
            if not category:
                self.report({"ERROR"}, "Enter a new category name before saving.")
                return {"CANCELLED"}
        else:
            category = "" if browser.editor_category == constants.ENUM_NONE_IDENTIFIER else browser.editor_category

        if browser.editor_subcategory == constants.ENUM_ADD_NEW_SUBCATEGORY_IDENTIFIER or (
            browser.editor_category == constants.ENUM_ADD_NEW_CATEGORY_IDENTIFIER and browser.editor_new_subcategory_name.strip()
        ):
            subcategory = browser.editor_new_subcategory_name.strip()
            if browser.editor_subcategory == constants.ENUM_ADD_NEW_SUBCATEGORY_IDENTIFIER and not subcategory:
                self.report({"ERROR"}, "Enter a new subcategory name before saving.")
                return {"CANCELLED"}
        else:
            subcategory = "" if browser.editor_subcategory == constants.ENUM_NONE_IDENTIFIER else browser.editor_subcategory

        if category and (
            browser.editor_category == constants.ENUM_ADD_NEW_CATEGORY_IDENTIFIER
            or browser.editor_subcategory == constants.ENUM_ADD_NEW_SUBCATEGORY_IDENTIFIER
        ):
            save_category_registry_entry(Path(asset.root_path), category, subcategory)
            registry = runtime.category_registry()
            values = list(registry.get(category, []))
            if subcategory and subcategory not in values:
                values.append(subcategory)
            registry[category] = values
            runtime.set_category_registry(registry)

        tags = normalize_tags(browser.editor_tags)
        if tags:
            _ensure_tags_in_registry(Path(asset.root_path), tags)
            runtime.set_tag_registry(sorted(set(runtime.tags()) | set(tags), key=str.casefold))

        save_user_override_for_asset(Path(asset.file_path), asset.item_key, {
            "display_name": display_name,
            "category": category,
            "subcategory": subcategory,
            "tags": tags,
        })
        asset.display_name = display_name
        asset.category = category
        asset.subcategory = subcategory
        asset.tags = tags
        browser.editor_new_category_name = ""
        browser.editor_new_subcategory_name = ""
        refresh_visible_assets(context)
        set_active_asset_id(context, asset_id)
        self.report({"INFO"}, "Saved library overrides for the selected asset.")
        return {"FINISHED"}


class BGAL_OT_ClearAssetOverrides(Operator):
    bl_idname = "bgal.clear_asset_overrides"
    bl_label = "Clear Library Overrides"
    bl_description = "Revert the selected asset back to its source metadata"
    bl_options = {"REGISTER", "UNDO"}

    asset_id: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        if asset is None:
            return {"CANCELLED"}

        clear_user_override_for_asset(Path(asset.file_path), asset.item_key)
        asset.display_name = asset.base_display_name
        asset.category = asset.base_category
        asset.subcategory = asset.base_subcategory
        asset.tags = list(asset.base_tags)
        refresh_visible_assets(context)
        set_active_asset_id(context, asset_id)
        self.report({"INFO"}, "Cleared library overrides for the selected asset.")
        return {"FINISHED"}


class BGAL_OT_AddCategoryDefinition(Operator):
    bl_idname = "bgal.add_category_definition"
    bl_label = "Add Category"
    bl_description = "Add a reusable category and optional subcategory to this library root"
    bl_options = {"REGISTER", "UNDO"}

    asset_id: StringProperty()
    root_path: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id) if asset_id else None
        browser = context.window_manager.bgal_browser
        root_path = _resolve_category_root(context, self.root_path, asset)
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}

        category = browser.manager_category_input.strip() or browser.new_category_name.strip()
        subcategory = ""

        if not category:
            self.report({"ERROR"}, "Enter a category name before adding it to the library.")
            return {"CANCELLED"}

        try:
            save_category_registry_entry(root_path, category, subcategory)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        registry = runtime.category_registry()
        values = list(registry.get(category, []))
        if subcategory and subcategory not in values:
            values.append(subcategory)
        registry[category] = values
        runtime.set_category_registry(registry)
        browser.new_category_name = ""
        browser.new_subcategory_name = ""
        _refresh_after_category_change(context)
        _select_manager_category_by_name(browser, category)
        browser.editor_category = category
        browser.editor_subcategory = constants.ENUM_NONE_IDENTIFIER
        browser.manager_category_input = ""
        browser.manager_subcategory_input = ""
        self.report({"INFO"}, f"Added category '{category}' to {root_path.name}.")
        return {"FINISHED"}


class BGAL_OT_AddSubcategoryDefinition(Operator):
    bl_idname = "bgal.add_subcategory_definition"
    bl_label = "Add Subcategory"
    bl_description = "Add a reusable subcategory under the selected category"
    bl_options = {"REGISTER", "UNDO"}

    root_path: StringProperty()

    def execute(self, context):
        browser = context.window_manager.bgal_browser
        category_name = selected_manager_category(browser)
        subcategory = browser.manager_subcategory_input.strip()
        root_path = _resolve_category_root(context, self.root_path, get_active_asset(context))
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}
        if not category_name:
            self.report({"ERROR"}, "Choose a category first.")
            return {"CANCELLED"}
        if not subcategory:
            self.report({"ERROR"}, "Enter a subcategory name before adding it.")
            return {"CANCELLED"}
        try:
            save_category_registry_entry(root_path, category_name, subcategory)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh_after_category_change(context)
        _select_manager_category_by_name(browser, category_name)
        _select_manager_subcategory_by_name(browser, subcategory)
        browser.manager_subcategory_input = ""
        self.report({"INFO"}, f"Added subcategory '{subcategory}' to '{category_name}'.")
        return {"FINISHED"}


class BGAL_OT_RenameCategoryDefinition(Operator):
    bl_idname = "bgal.rename_category_definition"
    bl_label = "Rename Category"
    bl_description = "Rename the selected reusable category in the target library"
    bl_options = {"REGISTER", "UNDO"}

    root_path: StringProperty()

    def execute(self, context):
        browser = context.window_manager.bgal_browser
        old_name = selected_manager_category(browser)
        new_name = browser.manager_category_input.strip()
        root_path = _resolve_category_root(context, self.root_path, get_active_asset(context))
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}
        if not old_name or old_name == constants.ENUM_NONE_IDENTIFIER:
            self.report({"ERROR"}, "Choose a category to rename.")
            return {"CANCELLED"}
        if not new_name:
            self.report({"ERROR"}, "Enter the new category name first.")
            return {"CANCELLED"}
        try:
            rename_category_registry_entry(root_path, old_name, new_name)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh_after_category_change(context)
        _select_manager_category_by_name(browser, new_name)
        browser.manager_category_input = new_name
        browser.manager_subcategory_input = ""
        self.report({"INFO"}, f"Renamed category '{old_name}' to '{new_name}'.")
        return {"FINISHED"}


class BGAL_OT_RemoveCategoryDefinition(Operator):
    bl_idname = "bgal.remove_category_definition"
    bl_label = "Remove Category"
    bl_description = "Remove the selected reusable category from the target library"
    bl_options = {"REGISTER", "UNDO"}

    root_path: StringProperty()

    def execute(self, context):
        browser = context.window_manager.bgal_browser
        category_name = selected_manager_category(browser)
        root_path = _resolve_category_root(context, self.root_path, get_active_asset(context))
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}
        if not category_name or category_name == constants.ENUM_NONE_IDENTIFIER:
            self.report({"ERROR"}, "Choose a category to remove.")
            return {"CANCELLED"}
        try:
            remove_category_registry_entry(root_path, category_name)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh_after_category_change(context)
        browser.manager_category_input = ""
        browser.manager_subcategory_input = ""
        self.report({"INFO"}, f"Removed category '{category_name}'.")
        return {"FINISHED"}


class BGAL_OT_RenameSubcategoryDefinition(Operator):
    bl_idname = "bgal.rename_subcategory_definition"
    bl_label = "Rename Subcategory"
    bl_description = "Rename the selected reusable subcategory in the target library"
    bl_options = {"REGISTER", "UNDO"}

    root_path: StringProperty()

    def execute(self, context):
        browser = context.window_manager.bgal_browser
        category_name = selected_manager_category(browser)
        old_name = selected_manager_subcategory(browser)
        new_name = browser.manager_subcategory_input.strip()
        root_path = _resolve_category_root(context, self.root_path, get_active_asset(context))
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}
        if not category_name or category_name == constants.ENUM_NONE_IDENTIFIER:
            self.report({"ERROR"}, "Choose a category first.")
            return {"CANCELLED"}
        if not old_name or old_name == constants.ENUM_NONE_IDENTIFIER:
            self.report({"ERROR"}, "Choose a subcategory to rename.")
            return {"CANCELLED"}
        if not new_name:
            self.report({"ERROR"}, "Enter the new subcategory name first.")
            return {"CANCELLED"}
        try:
            rename_subcategory_registry_entry(root_path, category_name, old_name, new_name)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh_after_category_change(context)
        _select_manager_category_by_name(browser, category_name)
        _select_manager_subcategory_by_name(browser, new_name)
        browser.manager_subcategory_input = new_name
        self.report({"INFO"}, f"Renamed subcategory '{old_name}' to '{new_name}'.")
        return {"FINISHED"}


class BGAL_OT_RemoveSubcategoryDefinition(Operator):
    bl_idname = "bgal.remove_subcategory_definition"
    bl_label = "Remove Subcategory"
    bl_description = "Remove the selected reusable subcategory from the target library"
    bl_options = {"REGISTER", "UNDO"}

    root_path: StringProperty()

    def execute(self, context):
        browser = context.window_manager.bgal_browser
        category_name = selected_manager_category(browser)
        subcategory_name = selected_manager_subcategory(browser)
        root_path = _resolve_category_root(context, self.root_path, get_active_asset(context))
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}
        if not category_name or category_name == constants.ENUM_NONE_IDENTIFIER:
            self.report({"ERROR"}, "Choose a category first.")
            return {"CANCELLED"}
        if not subcategory_name or subcategory_name == constants.ENUM_NONE_IDENTIFIER:
            self.report({"ERROR"}, "Choose a subcategory to remove.")
            return {"CANCELLED"}
        try:
            remove_subcategory_registry_entry(root_path, category_name, subcategory_name)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh_after_category_change(context)
        browser.manager_subcategory_input = ""
        self.report({"INFO"}, f"Removed subcategory '{subcategory_name}'.")
        return {"FINISHED"}


class BGAL_OT_AddTagDefinition(Operator):
    bl_idname = "bgal.add_tag_definition"
    bl_label = "Add Tag"
    bl_description = "Add a reusable tag to the target library"
    bl_options = {"REGISTER", "UNDO"}

    root_path: StringProperty()

    def execute(self, context):
        browser = context.window_manager.bgal_browser
        tag_name = browser.manager_tag_input.strip()
        root_path = _resolve_category_root(context, self.root_path, get_active_asset(context))
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}
        if not tag_name:
            self.report({"ERROR"}, "Enter a tag name before adding it.")
            return {"CANCELLED"}
        try:
            save_tag_registry_entry(root_path, tag_name)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh_after_category_change(context)
        _select_manager_tag_by_name(browser, tag_name)
        browser.manager_tag_input = ""
        self.report({"INFO"}, f"Added tag '{tag_name}'.")
        return {"FINISHED"}


class BGAL_OT_RenameTagDefinition(Operator):
    bl_idname = "bgal.rename_tag_definition"
    bl_label = "Rename Tag"
    bl_description = "Rename the selected reusable tag in the target library"
    bl_options = {"REGISTER", "UNDO"}

    root_path: StringProperty()

    def execute(self, context):
        browser = context.window_manager.bgal_browser
        old_name = selected_manager_tag(browser)
        new_name = browser.manager_tag_input.strip()
        root_path = _resolve_category_root(context, self.root_path, get_active_asset(context))
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}
        if not old_name:
            self.report({"ERROR"}, "Choose a tag to rename.")
            return {"CANCELLED"}
        if not new_name:
            self.report({"ERROR"}, "Enter the new tag name first.")
            return {"CANCELLED"}
        try:
            rename_tag_registry_entry(root_path, old_name, new_name)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh_after_category_change(context)
        _select_manager_tag_by_name(browser, new_name)
        browser.manager_tag_input = new_name
        self.report({"INFO"}, f"Renamed tag '{old_name}' to '{new_name}'.")
        return {"FINISHED"}


class BGAL_OT_RemoveTagDefinition(Operator):
    bl_idname = "bgal.remove_tag_definition"
    bl_label = "Remove Tag"
    bl_description = "Remove the selected reusable tag from the target library"
    bl_options = {"REGISTER", "UNDO"}

    root_path: StringProperty()

    def execute(self, context):
        browser = context.window_manager.bgal_browser
        tag_name = selected_manager_tag(browser)
        root_path = _resolve_category_root(context, self.root_path, get_active_asset(context))
        if root_path is None:
            self.report({"WARNING"}, "Select or configure a target library root first.")
            return {"CANCELLED"}
        if not tag_name:
            self.report({"ERROR"}, "Choose a tag to remove.")
            return {"CANCELLED"}
        try:
            remove_tag_registry_entry(root_path, tag_name)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        _refresh_after_category_change(context)
        browser.manager_tag_input = ""
        self.report({"INFO"}, f"Removed tag '{tag_name}'.")
        return {"FINISHED"}


class BGAL_OT_PlaceAssetInteractive(Operator):
    bl_idname = "bgal.place_asset_interactive"
    bl_label = "Place Asset In View"
    bl_description = "Click in a 3D View to place the selected asset package"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    asset_id: StringProperty()

    def _finish(self, context):
        if context.workspace:
            context.workspace.status_text_set(None)

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        if asset is None:
            self.report({"WARNING"}, "Select an asset first.")
            return {"CANCELLED"}
        link_mode, make_local_after_link, namespace_prefix, place_as_collection_instance = _browser_import_settings(
            context, asset
        )
        success, message, _selection = import_asset(
            context,
            asset_id,
            link_mode=link_mode,
            make_local_after_link=make_local_after_link,
            namespace_prefix=namespace_prefix,
            place_mode="CURSOR",
            place_as_collection_instance=place_as_collection_instance,
        )
        context.window_manager.bgal_browser.status_text = message or f"Placed {asset.display_name} at the cursor"
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        if message:
            self.report({"INFO"}, message)
        refresh_visible_assets(context)
        sync_editor_fields(context)
        return {"FINISHED"}

    def invoke(self, context, event):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        if asset is None:
            self.report({"WARNING"}, "Select an asset first.")
            return {"CANCELLED"}
        self.asset_id = asset_id
        if context.workspace:
            context.workspace.status_text_set("Click inside a 3D View to place the asset. Esc cancels.")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"}:
            self._finish(context)
            return {"CANCELLED"}

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            asset = runtime.get_asset(self.asset_id)
            if asset is None:
                self._finish(context)
                return {"CANCELLED"}

            location = _placement_location(context, event.mouse_x, event.mouse_y)
            if location is None:
                self.report({"INFO"}, "Move the cursor over a 3D View and click to place the asset.")
                return {"RUNNING_MODAL"}

            browser = context.window_manager.bgal_browser
            link_mode, make_local_after_link, namespace_prefix, place_as_collection_instance = _browser_import_settings(
                context, asset
            )
            original_cursor = context.scene.cursor.location.copy()
            try:
                context.scene.cursor.location = location
                success, message, _selection = import_asset(
                    context,
                    self.asset_id,
                    link_mode=link_mode,
                    make_local_after_link=make_local_after_link,
                    namespace_prefix=namespace_prefix,
                    place_mode="CURSOR",
                    place_as_collection_instance=place_as_collection_instance,
                )
            finally:
                context.scene.cursor.location = original_cursor

            self._finish(context)
            refresh_visible_assets(context)
            sync_editor_fields(context)
            browser.status_text = message or f"Placed {asset.display_name}"
            if not success:
                self.report({"ERROR"}, message)
                return {"CANCELLED"}
            if message:
                self.report({"INFO"}, message)
            return {"FINISHED"}

        return {"RUNNING_MODAL"}


class BGAL_OT_ToggleFavorite(Operator):
    bl_idname = "bgal.toggle_favorite"
    bl_label = "Toggle Favorite"
    bl_description = "Mark the selected asset as a favorite"
    bl_options = {"REGISTER", "UNDO"}

    asset_id: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        if asset is None:
            return {"CANCELLED"}
        asset.is_favorite = toggle_favorite(asset_id)
        refresh_visible_assets(context)
        return {"FINISHED"}


class BGAL_OT_RevealAsset(Operator):
    bl_idname = "bgal.reveal_asset"
    bl_label = "Reveal In Explorer"
    bl_description = "Reveal the source file or folder in the system file browser"

    asset_id: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        if asset is None:
            return {"CANCELLED"}
        success, message = open_in_file_browser(asset.file_path)
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        return {"FINISHED"}


class BGAL_OT_OpenSourceBlend(Operator):
    bl_idname = "bgal.open_source_blend"
    bl_label = "Open Source Blend"
    bl_description = "Open the source .blend file in a new Blender instance"

    asset_id: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        if asset is None:
            return {"CANCELLED"}
        success, message = open_blend_in_new_instance(asset.file_path)
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        return {"FINISHED"}


class BGAL_OT_ValidateAsset(Operator):
    bl_idname = "bgal.validate_asset"
    bl_label = "Validate Asset Package"
    bl_description = "Check the asset package for missing targets, previews, and external textures"

    asset_id: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        if asset is None:
            return {"CANCELLED"}
        report = validate_asset(asset_id)
        refresh_visible_assets(context)
        if report.warnings:
            self.report({"WARNING"}, "; ".join(report.warnings[:4]))
        else:
            self.report({"INFO"}, f"{asset.display_name} validated successfully.")
        return {"FINISHED"}


class BGAL_OT_RegenerateThumbnail(Operator):
    bl_idname = "bgal.regenerate_thumbnail"
    bl_label = "Regenerate Thumbnail"
    bl_description = "Render and cache a fresh preview thumbnail for the selected asset"

    asset_id: StringProperty()

    def execute(self, context):
        asset_id = _resolve_asset_id(context, self.asset_id)
        asset = runtime.get_asset(asset_id)
        if asset is None:
            return {"CANCELLED"}
        if asset.thumbnail_cache and Path(asset.thumbnail_cache).exists():
            try:
                Path(asset.thumbnail_cache).unlink()
            except Exception:
                pass
        success, message = render_thumbnail_for_asset(context, asset_id)
        refresh_visible_assets(context)
        if not success:
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        self.report({"INFO"}, f"Thumbnail regenerated for {asset.display_name}.")
        return {"FINISHED"}


CLASSES = (
    BGAL_OT_ImportAsset,
    BGAL_OT_SelectAsset,
    BGAL_OT_SaveAssetOverrides,
    BGAL_OT_ClearAssetOverrides,
    BGAL_OT_AddCategoryDefinition,
    BGAL_OT_AddSubcategoryDefinition,
    BGAL_OT_RenameCategoryDefinition,
    BGAL_OT_RemoveCategoryDefinition,
    BGAL_OT_RenameSubcategoryDefinition,
    BGAL_OT_RemoveSubcategoryDefinition,
    BGAL_OT_AddTagDefinition,
    BGAL_OT_RenameTagDefinition,
    BGAL_OT_RemoveTagDefinition,
    BGAL_OT_ToggleFavorite,
    BGAL_OT_RevealAsset,
    BGAL_OT_OpenSourceBlend,
    BGAL_OT_ValidateAsset,
    BGAL_OT_RegenerateThumbnail,
)


def register() -> None:
    for cls in CLASSES:
        safe_register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
