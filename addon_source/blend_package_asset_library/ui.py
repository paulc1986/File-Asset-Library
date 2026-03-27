from __future__ import annotations

from pathlib import Path

import bpy
from bpy.types import Menu, Panel, UIList

from . import constants, runtime, updater
from .preview_cache import preview_manager
from .properties import (
    _preview_path_for_asset,
    get_active_asset,
    refresh_category_manager_lists,
    refresh_tag_manager_lists,
    selected_manager_category,
)
from .registration import safe_register_class, safe_unregister_class


def addon_preferences(context):
    addon = context.preferences.addons.get(constants.ADDON_PACKAGE)
    return addon.preferences if addon else None


def category_target(context):
    asset = get_active_asset(context)
    if asset is not None and asset.root_path:
        root_path = Path(asset.root_path)
        return root_path, root_path.name, "Selected asset library"
    prefs = addon_preferences(context)
    if prefs is None or not prefs.library_roots:
        return None, "", ""
    index = max(0, min(prefs.active_root_index, len(prefs.library_roots) - 1))
    root = prefs.library_roots[index]
    if not root.directory:
        return None, "", ""
    root_path = Path(bpy.path.abspath(root.directory)).resolve()
    label = root.label.strip() or root_path.name
    return root_path, label, "Active library root"


def draw_section_title(layout, text: str, icon: str) -> None:
    row = layout.row(align=True)
    row.label(text=text, icon=icon)


def enabled_root_labels(context) -> list[str]:
    prefs = addon_preferences(context)
    if prefs is None:
        return []
    labels = []
    for item in getattr(prefs, "library_roots", []):
        if not getattr(item, "enabled", False) or not getattr(item, "directory", ""):
            continue
        labels.append(item.label.strip() or Path(bpy.path.abspath(item.directory)).name)
    return labels


class BGAL_UL_AssetList(UIList):
    bl_idname = "BGAL_UL_asset_list"

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
        asset = runtime.get_asset(item.asset_id)
        icon_id = preview_manager.icon_id(item.asset_id, _preview_path_for_asset(asset))

        row = layout.row(align=True)
        thumb = row.column()
        thumb.template_icon(icon_value=icon_id, scale=3.0)
        main = row.column(align=True)
        title = main.row(align=True)
        title.label(text=item.display_name, icon="OUTLINER_COLLECTION")
        if item.is_favorite:
            title.label(text="", icon="SOLO_ON")
        if item.warning_count:
            title.label(text="", icon="ERROR")
        subtitle = main.row(align=True)
        subtitle.label(text=item.category or "Uncategorized", icon="FILE_FOLDER")
        if item.subcategory:
            subtitle.label(text=item.subcategory, icon="TRIA_RIGHT")


class BGAL_UL_ManagerCategories(UIList):
    bl_idname = "BGAL_UL_manager_categories"

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
        row.label(text=item.name, icon="FILE_FOLDER")
        row.label(text=str(item.count))


class BGAL_UL_ManagerSubcategories(UIList):
    bl_idname = "BGAL_UL_manager_subcategories"

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
        layout.label(text=item.name, icon="TRIA_RIGHT")


class BGAL_UL_ManagerTags(UIList):
    bl_idname = "BGAL_UL_manager_tags"

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
        layout.label(text=item.name, icon="BOOKMARKS")


class BGAL_MT_AssetActions(Menu):
    bl_idname = "BGAL_MT_asset_actions"
    bl_label = "Asset Actions"

    def draw(self, context):
        layout = self.layout
        asset = get_active_asset(context)
        if asset is None:
            layout.label(text="No asset selected.")
            return
        layout.operator("bgal.toggle_favorite", icon="SOLO_ON").asset_id = asset.asset_id
        layout.separator()
        layout.operator("bgal.validate_asset", icon="CHECKMARK").asset_id = asset.asset_id
        layout.operator("bgal.regenerate_thumbnail", icon="RENDER_STILL").asset_id = asset.asset_id
        layout.separator()
        layout.operator("bgal.reveal_asset", icon="FILE_FOLDER").asset_id = asset.asset_id
        layout.operator("bgal.open_source_blend", icon="BLENDER").asset_id = asset.asset_id


class BGAL_PT_Browser(Panel):
    bl_label = "Custom Asset Library 1.0.0"
    bl_idname = "BGAL_PT_browser"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_order = 0

    def draw_header(self, context):
        self.layout.label(text="", icon="FILEBROWSER")

    @staticmethod
    def draw_asset_card(layout, browser, row, preview_scale: float):
        asset = runtime.get_asset(row.asset_id)
        icon_id = preview_manager.icon_id(row.asset_id, _preview_path_for_asset(asset))
        is_selected = row.asset_id == browser.selected_asset_id

        box = layout.box()
        header = box.row(align=True)
        select_op = header.operator(
            "bgal.select_asset",
            text=row.display_name,
            emboss=True,
            depress=is_selected,
        )
        select_op.asset_id = row.asset_id
        if row.warning_count:
            header.label(text="", icon="ERROR")
        if row.is_favorite:
            header.label(text="", icon="SOLO_ON")

        preview = box.row()
        preview.alignment = "CENTER"
        preview.template_icon(icon_value=icon_id, scale=preview_scale)

        meta = box.row(align=True)
        meta.label(text=row.category or "Uncategorized", icon="FILE_FOLDER")
        if row.subcategory:
            meta.label(text=row.subcategory, icon="TRIA_RIGHT")
        library = box.row(align=True)
        library.label(text=asset.library_label or "Library", icon="DISK_DRIVE")
        footer = box.row(align=True)
        append_op = footer.operator("bgal.import_asset", text="Append")
        append_op.asset_id = row.asset_id
        append_op.mode_override = "APPEND"
        link_op = footer.operator("bgal.import_asset", text="Link")
        link_op.asset_id = row.asset_id
        link_op.mode_override = "LINK"

    def draw(self, context):
        layout = self.layout
        browser = context.window_manager.bgal_browser

        header = layout.row(align=True)
        header.prop(browser, "search_text", text="", icon="VIEWZOOM")
        refresh = header.operator("bgal.scan_libraries", text="", icon="FILE_REFRESH")
        refresh.force = True

        filters_box = layout.box()
        filters_header = filters_box.row(align=True)
        icon = "TRIA_DOWN" if browser.show_browser_filters else "TRIA_RIGHT"
        filters_header.prop(
            browser,
            "show_browser_filters",
            text="Filters",
            emboss=False,
            icon=icon,
        )
        if browser.show_browser_filters:
            filters_box.prop(browser, "category_filter", text="Category")
            filters_box.prop(browser, "subcategory_filter", text="Subcategory")
            filters_box.prop(browser, "tag_filter", text="Tags")
            filters_box.prop(browser, "show_favorites_only", text="Favorites Only")
            filters_box.prop(browser, "view_mode", text="View")
            filters_box.prop(browser, "sort_mode", text="Sort")

        if browser.view_mode == "GRID":
            if browser.visible_assets:
                available_width = max(context.region.width - 28, 240)
                columns = max(1, min(6, available_width // 170))
                preview_scale = 8.5 if columns >= 5 else 9.5 if columns == 4 else 10.5 if columns == 3 else 11.5 if columns == 2 else 13.0
                grid = layout.column(align=True) if columns == 1 else layout.grid_flow(
                    row_major=True,
                    columns=columns,
                    even_columns=True,
                    even_rows=False,
                    align=True,
                )
                for row_item in browser.visible_assets:
                    self.draw_asset_card(grid, browser, row_item, preview_scale)
            else:
                empty = layout.box()
                empty.label(text="No assets match the current filters.", icon="INFO")
        else:
            layout.template_list(
                "BGAL_UL_asset_list",
                "",
                browser,
                "visible_assets",
                browser,
                "visible_asset_index",
                rows=10,
            )


class BGAL_PT_BrowserInfo(Panel):
    bl_label = "Information"
    bl_idname = "BGAL_PT_browser_info"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 30

    def draw_header(self, context):
        self.layout.label(text="", icon="INFO")

    def draw(self, context):
        layout = self.layout
        browser = context.window_manager.bgal_browser
        asset = get_active_asset(context)
        local_version = updater.local_version_text()

        layout.label(text=f"Installed Version: {local_version}", icon="BLENDER")
        layout.label(text=f"Indexed {len(runtime.all_assets())} assets", icon="OUTLINER")
        layout.label(text=f"Showing {len(browser.visible_assets)} assets", icon="VIEWZOOM")
        if asset is not None:
            layout.label(text=f"Selected: {asset.display_name}", icon="RESTRICT_SELECT_OFF")

        roots = enabled_root_labels(context)
        if roots:
            layout.label(text=f"Libraries: {', '.join(roots[:2])}" + (" ..." if len(roots) > 2 else ""), icon="FILE_FOLDER")
        else:
            layout.label(text="Libraries: No enabled asset library paths", icon="FILE_FOLDER")

        if browser.status_text:
            status_box = layout.box()
            status_box.label(text=browser.status_text, icon="INFO")

        update_box = layout.box()
        draw_section_title(update_box, "Update Status", "IMPORT")
        if browser.update_check_in_progress:
            update_box.label(text="Checking GitHub for updates...", icon="TIME")
        elif browser.update_available and browser.update_latest_version:
            alert = update_box.row()
            alert.alert = True
            alert.label(text=f"Update available: {browser.update_latest_version}", icon="IMPORT")
        elif browser.update_error_text:
            error = update_box.row()
            error.alert = True
            error.label(text=browser.update_error_text, icon="ERROR")
        elif browser.update_status_text:
            update_box.label(text=browser.update_status_text, icon="CHECKMARK")
        else:
            update_box.label(text="No update check has run yet this session.", icon="INFO")

        if browser.update_release_name:
            update_box.label(text=f"Release: {browser.update_release_name}", icon="URL")
        if browser.update_last_checked:
            update_box.label(text=f"Last checked: {browser.update_last_checked}", icon="SORTTIME")

        actions = update_box.row(align=True)
        actions.operator("bgal.check_for_updates", text="Check Now", icon="FILE_REFRESH")
        if browser.update_available:
            update_op = actions.operator("bgal.open_update_release", text="Update Add-on", icon="IMPORT")
            update_op.use_download_url = True
        else:
            update_op = actions.operator("bgal.open_update_release", text="Open Release", icon="URL")
            update_op.use_download_url = False


class BGAL_PT_BrowserImportOptions(Panel):
    bl_label = "Import Options"
    bl_idname = "BGAL_PT_browser_import_options"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_parent_id = "BGAL_PT_browser"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 2

    def draw_header(self, context):
        self.layout.label(text="", icon="TOOL_SETTINGS")

    def draw(self, context):
        layout = self.layout
        browser = context.window_manager.bgal_browser

        layout.prop(browser, "make_local_after_link")
        layout.prop(browser, "place_as_collection_instance")
        namespace_row = layout.row(align=True)
        namespace_row.prop(browser, "use_namespace")
        namespace_value = namespace_row.row(align=True)
        namespace_value.enabled = browser.use_namespace
        namespace_value.prop(browser, "namespace_prefix", text="")


class BGAL_PT_Details(Panel):
    bl_label = "Asset Details"
    bl_idname = "BGAL_PT_details"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_order = 10

    def draw_header(self, context):
        self.layout.label(text="", icon="INFO")

    def draw(self, context):
        layout = self.layout
        asset = get_active_asset(context)
        browser = context.window_manager.bgal_browser
        if asset is None:
            layout.label(text="Select an asset to see details.", icon="INFO")
            return

        selector = layout.box()
        draw_section_title(selector, "Selected Asset", "RESTRICT_SELECT_OFF")
        selector.prop(browser, "details_asset_selection", text="Asset")

        icon_id = preview_manager.icon_id(asset.asset_id, _preview_path_for_asset(asset))
        preview = layout.row()
        preview.alignment = "CENTER"
        preview.template_icon(icon_value=icon_id, scale=10.0)
        layout.label(text=asset.display_name)

        quick_import = layout.box()
        draw_section_title(quick_import, "Quick Import", "IMPORT")
        actions = quick_import.row(align=True)
        append_op = actions.operator("bgal.import_asset", text="Append")
        append_op.asset_id = asset.asset_id
        append_op.mode_override = "APPEND"
        link_op = actions.operator("bgal.import_asset", text="Link")
        link_op.asset_id = asset.asset_id
        link_op.mode_override = "LINK"

        edits = layout.box()
        draw_section_title(edits, "Library Overrides", "GREASEPENCIL")
        edits.prop(browser, "editor_display_name", text="Name")
        edits.prop(browser, "editor_category", text="Category")
        if browser.editor_category == constants.ENUM_ADD_NEW_CATEGORY_IDENTIFIER:
            edits.prop(browser, "editor_new_category_name", text="New Category")
        subcategory_row = edits.row()
        subcategory_row.enabled = browser.editor_category != constants.ENUM_NONE_IDENTIFIER
        subcategory_row.prop(browser, "editor_subcategory", text="Subcategory")
        if (
            browser.editor_category == constants.ENUM_ADD_NEW_CATEGORY_IDENTIFIER
            or browser.editor_subcategory == constants.ENUM_ADD_NEW_SUBCATEGORY_IDENTIFIER
        ):
            edits.prop(browser, "editor_new_subcategory_name", text="New Subcategory")
        edits.prop(browser, "editor_tags", text="Tags")
        edit_actions = edits.row(align=True)
        edit_actions.operator("bgal.save_asset_overrides", text="Save Overrides", icon="CHECKMARK").asset_id = asset.asset_id
        edit_actions.operator("bgal.clear_asset_overrides", text="Reset", icon="LOOP_BACK").asset_id = asset.asset_id

        buttons = layout.box()
        draw_section_title(buttons, "Asset Actions", "TOOL_SETTINGS")
        action_col = buttons.column(align=True)
        action_col.operator("bgal.toggle_favorite", text="Toggle Favorite", icon="SOLO_ON").asset_id = asset.asset_id
        action_col.operator("bgal.validate_asset", text="Validate Package", icon="CHECKMARK").asset_id = asset.asset_id
        action_col.operator("bgal.regenerate_thumbnail", text="Regenerate Thumbnail", icon="RENDER_STILL").asset_id = asset.asset_id
        action_col.operator("bgal.reveal_asset", text="Reveal In Folder", icon="FILE_FOLDER").asset_id = asset.asset_id
        action_col.operator("bgal.open_source_blend", text="Open Source Blend", icon="BLENDER").asset_id = asset.asset_id

        meta = layout.box()
        draw_section_title(meta, "Package Summary", "OUTLINER_COLLECTION")
        meta.label(text=f"Category: {asset.category or 'Uncategorized'}")
        if asset.subcategory:
            meta.label(text=f"Subcategory: {asset.subcategory}")
        meta.label(text=f"Import Target: {asset.target_kind}")
        meta.label(text=f"Detection: {asset.detection_strategy}")
        if asset.author:
            meta.label(text=f"Author: {asset.author}")
        if asset.version:
            meta.label(text=f"Version: {asset.version}")
        if asset.tags:
            meta.label(text=f"Tags: {', '.join(asset.tags)}")

        path_box = layout.box()
        draw_section_title(path_box, "Source File", "BLENDER")
        path_box.label(text=Path(asset.file_path).name, icon="BLENDER")
        path_box.label(text=asset.relative_path, icon="FILE_FOLDER")

        if asset.description:
            desc_box = layout.box()
            draw_section_title(desc_box, "Description", "TEXT")
            for line in asset.description.splitlines():
                desc_box.label(text=line)

        warnings = list(asset.warnings) + list(asset.validation.warnings)
        if warnings:
            warn_box = layout.box()
            draw_section_title(warn_box, "Warnings", "ERROR")
            for warning in warnings[:8]:
                warn_box.label(text=warning)


class BGAL_PT_Roots(Panel):
    bl_label = "Asset Library Paths"
    bl_idname = "BGAL_PT_roots"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 20
    bl_parent_id = "BGAL_PT_libraries"

    def draw_header(self, context):
        self.layout.label(text="", icon="OUTLINER_COLLECTION")

    def draw(self, context):
        layout = self.layout
        prefs = addon_preferences(context)
        if prefs is None:
            layout.label(text="Addon preferences unavailable.", icon="ERROR")
            return

        draw_section_title(layout, "Registered Library Roots", "FILE_FOLDER")

        row = layout.row()
        row.template_list(
            "BGAL_UL_library_roots",
            "",
            prefs,
            "library_roots",
            prefs,
            "active_root_index",
            rows=4,
        )
        buttons = row.column(align=True)
        buttons.operator("bgal.root_add", text="", icon="ADD")
        buttons.operator("bgal.root_remove", text="", icon="REMOVE")
        buttons.separator()
        refresh = buttons.operator("bgal.scan_libraries", text="", icon="FILE_REFRESH")
        refresh.force = True

        if prefs.library_roots:
            active_index = max(0, min(prefs.active_root_index, len(prefs.library_roots) - 1))
            active_root = prefs.library_roots[active_index]
            box = layout.box()
            draw_section_title(box, "Active Root", "DISK_DRIVE")
            box.prop(active_root, "label")
            box.prop(active_root, "directory")
            box.prop(active_root, "enabled")


class BGAL_PT_Categories(Panel):
    bl_label = "Categories"
    bl_idname = "BGAL_PT_categories"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_parent_id = "BGAL_PT_libraries"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 0

    def draw_header(self, context):
        self.layout.label(text="", icon="FILE_FOLDER")

    def draw(self, context):
        layout = self.layout
        browser = context.window_manager.bgal_browser
        root_path, label, source_label = category_target(context)
        refresh_category_manager_lists(context)

        if root_path is None:
            layout.label(text="Add or select a library root first.", icon="INFO")
            return

        draw_section_title(layout, "Category Library", "FILE_FOLDER")
        layout.label(text=f"Library: {label}", icon="DISK_DRIVE")
        layout.label(text=source_label, icon="INFO")
        layout.template_list(
            "BGAL_UL_manager_categories",
            "",
            browser,
            "manager_categories",
            browser,
            "manager_category_index",
            rows=5,
        )

        box = layout.box()
        draw_section_title(box, "Category Editor", "GREASEPENCIL")
        box.prop(browser, "manager_category_input", text="Name")
        actions = box.row(align=True)
        add_text = actions.operator("bgal.add_category_definition", text="Add New", icon="ADD")
        add_text.root_path = str(root_path)
        rename_op = actions.operator("bgal.rename_category_definition", text="Rename", icon="GREASEPENCIL")
        rename_op.root_path = str(root_path)
        delete_op = actions.operator("bgal.remove_category_definition", text="Delete", icon="TRASH")
        delete_op.root_path = str(root_path)


class BGAL_PT_Subcategories(Panel):
    bl_label = "Sub-categories"
    bl_idname = "BGAL_PT_subcategories"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_parent_id = "BGAL_PT_libraries"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 1

    def draw_header(self, context):
        self.layout.label(text="", icon="TRIA_RIGHT")

    def draw(self, context):
        layout = self.layout
        browser = context.window_manager.bgal_browser
        root_path, label, source_label = category_target(context)
        refresh_category_manager_lists(context)

        if root_path is None:
            layout.label(text="Add or select a library root first.", icon="INFO")
            return

        active_category = selected_manager_category(browser)
        draw_section_title(layout, "Sub-category Library", "TRIA_RIGHT")
        layout.label(text=f"Library: {label}", icon="DISK_DRIVE")
        layout.label(text=source_label, icon="INFO")
        if not active_category:
            layout.label(text="Select a category first.", icon="INFO")
            return

        layout.label(text=f"Category: {active_category}", icon="FILE_FOLDER")
        layout.template_list(
            "BGAL_UL_manager_subcategories",
            "",
            browser,
            "manager_subcategories",
            browser,
            "manager_subcategory_index",
            rows=5,
        )

        box = layout.box()
        draw_section_title(box, "Sub-category Editor", "GREASEPENCIL")
        box.prop(browser, "manager_subcategory_input", text="Name")
        actions = box.row(align=True)
        add_text = actions.operator("bgal.add_subcategory_definition", text="Add New", icon="ADD")
        add_text.root_path = str(root_path)
        rename_op = actions.operator("bgal.rename_subcategory_definition", text="Rename", icon="GREASEPENCIL")
        rename_op.root_path = str(root_path)
        delete_op = actions.operator("bgal.remove_subcategory_definition", text="Delete", icon="TRASH")
        delete_op.root_path = str(root_path)


class BGAL_PT_Tags(Panel):
    bl_label = "Tags"
    bl_idname = "BGAL_PT_tags"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_parent_id = "BGAL_PT_libraries"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 2

    def draw_header(self, context):
        self.layout.label(text="", icon="BOOKMARKS")

    def draw(self, context):
        layout = self.layout
        browser = context.window_manager.bgal_browser
        root_path, label, source_label = category_target(context)
        refresh_tag_manager_lists(context)

        if root_path is None:
            layout.label(text="Add or select a library root first.", icon="INFO")
            return

        draw_section_title(layout, "Tag Library", "BOOKMARKS")
        layout.label(text=f"Library: {label}", icon="DISK_DRIVE")
        layout.label(text=source_label, icon="INFO")
        layout.template_list(
            "BGAL_UL_manager_tags",
            "",
            browser,
            "manager_tags",
            browser,
            "manager_tag_index",
            rows=6,
        )
        box = layout.box()
        draw_section_title(box, "Tag Editor", "GREASEPENCIL")
        box.prop(browser, "manager_tag_input", text="Name")
        actions = box.row(align=True)
        add_text = actions.operator("bgal.add_tag_definition", text="Add New", icon="ADD")
        add_text.root_path = str(root_path)
        rename_op = actions.operator("bgal.rename_tag_definition", text="Rename", icon="GREASEPENCIL")
        rename_op.root_path = str(root_path)
        delete_op = actions.operator("bgal.remove_tag_definition", text="Delete", icon="TRASH")
        delete_op.root_path = str(root_path)


class BGAL_PT_Libraries(Panel):
    bl_label = "Libraries"
    bl_idname = "BGAL_PT_libraries"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Custom Asset Library"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 20

    def draw_header(self, context):
        self.layout.label(text="", icon="FILE_FOLDER")

    def draw(self, context):
        layout = self.layout
        info = layout.box()
        draw_section_title(info, "Library Management", "TOOL_SETTINGS")
        info.label(text="Manage roots, categories, sub-categories, and tags.", icon="INFO")


CLASSES = (
    BGAL_UL_AssetList,
    BGAL_UL_ManagerCategories,
    BGAL_UL_ManagerSubcategories,
    BGAL_UL_ManagerTags,
    BGAL_MT_AssetActions,
    BGAL_PT_Browser,
    BGAL_PT_BrowserInfo,
    BGAL_PT_BrowserImportOptions,
    BGAL_PT_Details,
    BGAL_PT_Libraries,
    BGAL_PT_Roots,
    BGAL_PT_Categories,
    BGAL_PT_Subcategories,
    BGAL_PT_Tags,
)


def register() -> None:
    for cls in CLASSES:
        safe_register_class(cls)


def unregister() -> None:
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
