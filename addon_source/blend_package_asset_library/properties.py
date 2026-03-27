from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import PropertyGroup

from . import constants, runtime
from .metadata import load_category_registry, load_tag_registry
from .preview_cache import preview_manager
from .registration import safe_assign_property, safe_register_class, safe_remove_property, safe_unregister_class
from .utils import normalize_tags

_SELECTION_SYNC_ACTIVE = False
_EDITOR_SYNC_ACTIVE = False
_MANAGER_SYNC_ACTIVE = False


def _selection_sync_enter() -> bool:
    global _SELECTION_SYNC_ACTIVE
    if _SELECTION_SYNC_ACTIVE:
        return False
    _SELECTION_SYNC_ACTIVE = True
    return True


def _selection_sync_exit() -> None:
    global _SELECTION_SYNC_ACTIVE
    _SELECTION_SYNC_ACTIVE = False


def _editor_sync_enter() -> bool:
    global _EDITOR_SYNC_ACTIVE
    if _EDITOR_SYNC_ACTIVE:
        return False
    _EDITOR_SYNC_ACTIVE = True
    return True


def _editor_sync_exit() -> None:
    global _EDITOR_SYNC_ACTIVE
    _EDITOR_SYNC_ACTIVE = False


def _manager_sync_enter() -> bool:
    global _MANAGER_SYNC_ACTIVE
    if _MANAGER_SYNC_ACTIVE:
        return False
    _MANAGER_SYNC_ACTIVE = True
    return True


def _manager_sync_exit() -> None:
    global _MANAGER_SYNC_ACTIVE
    _MANAGER_SYNC_ACTIVE = False


def _preview_path_for_asset(asset) -> str:
    if asset is None:
        return ""
    if asset.thumbnail_source and Path(asset.thumbnail_source).exists():
        return asset.thumbnail_source
    if asset.thumbnail_cache and Path(asset.thumbnail_cache).exists():
        return asset.thumbnail_cache
    return ""


def _enum_value_or_none(value: str) -> str:
    return value if value else constants.ENUM_NONE_IDENTIFIER


def _string_from_enum(value: str) -> str:
    return "" if value == constants.ENUM_NONE_IDENTIFIER else value


def _is_add_new_category(value: str) -> bool:
    return value == constants.ENUM_ADD_NEW_CATEGORY_IDENTIFIER


def _is_add_new_subcategory(value: str) -> bool:
    return value == constants.ENUM_ADD_NEW_SUBCATEGORY_IDENTIFIER


def _matches_search(asset, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        [
            asset.display_name,
            asset.description,
            asset.category,
            asset.subcategory,
            asset.relative_path,
            " ".join(asset.tags),
        ]
    ).casefold()
    return query.casefold() in haystack


def _matches_tags(asset, tag_filter: str) -> bool:
    if not tag_filter.strip():
        return True
    active = [token.casefold() for token in tag_filter.replace(";", ",").split(",") if token.strip()]
    asset_tags = {tag.casefold() for tag in asset.tags}
    return all(token.strip() in asset_tags for token in active)


def get_active_asset(context: bpy.types.Context):
    browser = context.window_manager.bgal_browser
    asset_id = browser.selected_asset_id or browser.asset_grid_selection
    if asset_id == "__empty__":
        asset_id = ""
    if not asset_id and browser.visible_assets and 0 <= browser.visible_asset_index < len(browser.visible_assets):
        asset_id = browser.visible_assets[browser.visible_asset_index].asset_id
    return runtime.get_asset(asset_id)


def resolve_category_manager_root(context: bpy.types.Context):
    asset = get_active_asset(context)
    if asset is not None and asset.root_path:
        return Path(asset.root_path)
    prefs = context.preferences.addons.get(constants.ADDON_PACKAGE)
    if prefs is None:
        return None
    addon_prefs = prefs.preferences
    if not addon_prefs.library_roots:
        return None
    index = max(0, min(addon_prefs.active_root_index, len(addon_prefs.library_roots) - 1))
    directory = addon_prefs.library_roots[index].directory
    if not directory:
        return None
    return Path(bpy.path.abspath(directory)).resolve()


def selected_manager_category(browser) -> str:
    if browser.manager_categories and 0 <= browser.manager_category_index < len(browser.manager_categories):
        return browser.manager_categories[browser.manager_category_index].name
    return ""


def selected_manager_subcategory(browser) -> str:
    if browser.manager_subcategories and 0 <= browser.manager_subcategory_index < len(browser.manager_subcategories):
        return browser.manager_subcategories[browser.manager_subcategory_index].name
    return ""


def selected_manager_tag(browser) -> str:
    if browser.manager_tags and 0 <= browser.manager_tag_index < len(browser.manager_tags):
        return browser.manager_tags[browser.manager_tag_index].name
    return ""


def refresh_category_manager_lists(context: bpy.types.Context, preserve_selection: bool = True) -> None:
    browser = context.window_manager.bgal_browser
    root_path = resolve_category_manager_root(context)
    root_key = str(root_path) if root_path else ""
    previous_category = selected_manager_category(browser) if preserve_selection else ""
    previous_subcategory = selected_manager_subcategory(browser) if preserve_selection else ""
    registry = load_category_registry(root_path) if root_path else {}

    if not _manager_sync_enter():
        return
    try:
        browser.manager_root_path = root_key
        browser.manager_categories.clear()
        category_names = sorted(registry.keys(), key=str.casefold)
        for category_name in category_names:
            row = browser.manager_categories.add()
            row.name = category_name
            row.count = len(registry.get(category_name, []))

        category_index = 0
        if category_names and previous_category in category_names:
            category_index = category_names.index(previous_category)
        browser.manager_category_index = category_index if category_names else 0
        active_category = category_names[category_index] if category_names else ""

        browser.manager_subcategories.clear()
        subcategory_names = list(registry.get(active_category, []))
        for subcategory_name in subcategory_names:
            row = browser.manager_subcategories.add()
            row.name = subcategory_name

        subcategory_index = 0
        if subcategory_names and previous_subcategory in subcategory_names:
            subcategory_index = subcategory_names.index(previous_subcategory)
        browser.manager_subcategory_index = subcategory_index if subcategory_names else 0
    finally:
        _manager_sync_exit()


def refresh_tag_manager_lists(context: bpy.types.Context, preserve_selection: bool = True) -> None:
    browser = context.window_manager.bgal_browser
    root_path = resolve_category_manager_root(context)
    previous_tag = selected_manager_tag(browser) if preserve_selection else ""
    values = load_tag_registry(root_path) if root_path else []

    if not _manager_sync_enter():
        return
    try:
        browser.manager_tags.clear()
        for value in values:
            row = browser.manager_tags.add()
            row.name = value

        index = 0
        if values and previous_tag in values:
            index = values.index(previous_tag)
        browser.manager_tag_index = index if values else 0
    finally:
        _manager_sync_exit()


def sync_editor_fields(context: bpy.types.Context) -> None:
    browser = context.window_manager.bgal_browser
    asset = get_active_asset(context)
    if not _editor_sync_enter():
        return
    try:
        if asset is None:
            if browser.details_asset_selection != "__empty__" and _selection_sync_enter():
                try:
                    browser.details_asset_selection = "__empty__"
                finally:
                    _selection_sync_exit()
            browser.editor_display_name = ""
            browser.editor_category = constants.ENUM_NONE_IDENTIFIER
            browser.editor_subcategory = constants.ENUM_NONE_IDENTIFIER
            browser.editor_tags = ""
            browser.editor_new_category_name = ""
            browser.editor_new_subcategory_name = ""
            return
        if browser.details_asset_selection != asset.asset_id and _selection_sync_enter():
            try:
                browser.details_asset_selection = asset.asset_id
            finally:
                _selection_sync_exit()
        browser.editor_display_name = asset.display_name
        browser.editor_category = _enum_value_or_none(asset.category)
        browser.editor_subcategory = _enum_value_or_none(asset.subcategory)
        browser.editor_tags = ", ".join(asset.tags)
        browser.editor_new_category_name = ""
        browser.editor_new_subcategory_name = ""
    finally:
        _editor_sync_exit()
    refresh_category_manager_lists(context)
    refresh_tag_manager_lists(context)


def set_active_asset_id(context: bpy.types.Context, asset_id: str) -> None:
    browser = context.window_manager.bgal_browser
    if not _selection_sync_enter():
        return
    try:
        browser.selected_asset_id = asset_id
        browser.asset_grid_selection = asset_id or "__empty__"
        browser.details_asset_selection = asset_id or "__empty__"
        target_index = 0
        for index, item in enumerate(browser.visible_assets):
            if item.asset_id == asset_id:
                target_index = index
                break
        browser.visible_asset_index = target_index
    finally:
        _selection_sync_exit()
    sync_editor_fields(context)
    screen = getattr(context, "screen", None)
    if screen is not None:
        for area in screen.areas:
            area.tag_redraw()


def refresh_visible_assets(context: bpy.types.Context) -> None:
    browser = context.window_manager.bgal_browser
    selected_asset_id = browser.selected_asset_id
    active_category = browser.category_filter or "ALL"
    active_subcategory = browser.subcategory_filter or "ALL"
    visible = []
    for asset in runtime.all_assets():
        if not asset.enabled:
            continue
        if browser.show_favorites_only and not asset.is_favorite:
            continue
        if active_category != "ALL" and asset.category != active_category:
            continue
        if active_subcategory != "ALL" and asset.subcategory != active_subcategory:
            continue
        if not _matches_search(asset, browser.search_text):
            continue
        if not _matches_tags(asset, browser.tag_filter):
            continue
        visible.append(asset)

    if browser.sort_mode == "CATEGORY":
        visible.sort(key=lambda item: (item.category.casefold(), item.subcategory.casefold(), item.display_name.casefold()))
    elif browser.sort_mode == "MODIFIED":
        visible.sort(key=lambda item: (-item.source_mtime, item.display_name.casefold()))
    elif browser.sort_mode == "RECENT":
        visible.sort(key=lambda item: (item.recent_rank, item.display_name.casefold()))
    elif browser.sort_mode == "AUTHOR":
        visible.sort(key=lambda item: (item.author.casefold(), item.display_name.casefold()))
    else:
        visible.sort(key=lambda item: item.display_name.casefold())

    browser.visible_assets.clear()
    for asset in visible:
        row = browser.visible_assets.add()
        row.asset_id = asset.asset_id
        row.display_name = asset.display_name
        row.category = asset.category
        row.subcategory = asset.subcategory
        row.description = asset.description
        row.file_path = asset.file_path
        row.tags = ", ".join(asset.tags)
        row.is_favorite = asset.is_favorite
        row.warning_count = len(asset.warnings) + len(asset.validation.warnings)

    new_index = 0
    if not _selection_sync_enter():
        return
    try:
        if browser.visible_assets:
            for index, item in enumerate(browser.visible_assets):
                if item.asset_id == selected_asset_id:
                    new_index = index
                    break
            browser.visible_asset_index = min(new_index, len(browser.visible_assets) - 1)
            browser.selected_asset_id = browser.visible_assets[browser.visible_asset_index].asset_id
            browser.asset_grid_selection = browser.selected_asset_id
            browser.details_asset_selection = browser.selected_asset_id
        else:
            browser.visible_asset_index = 0
            browser.selected_asset_id = ""
            browser.asset_grid_selection = "__empty__"
            browser.details_asset_selection = "__empty__"
    finally:
        _selection_sync_exit()
    sync_editor_fields(context)
    refresh_category_manager_lists(context)
    refresh_tag_manager_lists(context)


def _filters_updated(self, context: bpy.types.Context) -> None:
    available_subcategories = {item[0] for item in subcategory_enum_items(self, context)}
    if self.subcategory_filter not in available_subcategories:
        self.subcategory_filter = "ALL"
    refresh_visible_assets(context)


def _editor_category_updated(self, context: bpy.types.Context) -> None:
    if _EDITOR_SYNC_ACTIVE:
        return
    if self.editor_category == constants.ENUM_NONE_IDENTIFIER:
        self.editor_new_category_name = ""
        self.editor_subcategory = constants.ENUM_NONE_IDENTIFIER
        self.editor_new_subcategory_name = ""
        return
    if _is_add_new_category(self.editor_category):
        self.editor_subcategory = constants.ENUM_NONE_IDENTIFIER
        self.editor_new_subcategory_name = ""
        return
    category = _string_from_enum(self.editor_category)
    available = {item[0] for item in _editor_subcategory_items_for_category(category)}
    if self.editor_subcategory not in available:
        self.editor_subcategory = constants.ENUM_NONE_IDENTIFIER
    if self.editor_subcategory != constants.ENUM_ADD_NEW_SUBCATEGORY_IDENTIFIER:
        self.editor_new_subcategory_name = ""


def _editor_subcategory_updated(self, context: bpy.types.Context) -> None:
    if _EDITOR_SYNC_ACTIVE:
        return
    if not _is_add_new_subcategory(self.editor_subcategory):
        self.editor_new_subcategory_name = ""


def _manager_category_updated(self, context: bpy.types.Context) -> None:
    available = {item[0] for item in manager_subcategory_items(self, context)}
    if self.manager_subcategory not in available:
        self.manager_subcategory = constants.ENUM_NONE_IDENTIFIER


def _manager_category_index_updated(self, context: bpy.types.Context) -> None:
    if _MANAGER_SYNC_ACTIVE:
        return
    refresh_category_manager_lists(context)


def _manager_subcategory_index_updated(self, context: bpy.types.Context) -> None:
    if _MANAGER_SYNC_ACTIVE:
        return
    return


def _manager_tag_index_updated(self, context: bpy.types.Context) -> None:
    if _MANAGER_SYNC_ACTIVE:
        return
    return


def _visible_index_updated(self, context: bpy.types.Context) -> None:
    if _SELECTION_SYNC_ACTIVE:
        return
    if not _selection_sync_enter():
        return
    try:
        if not self.visible_assets:
            self.selected_asset_id = ""
            self.asset_grid_selection = "__empty__"
            self.details_asset_selection = "__empty__"
            return
        index = max(0, min(self.visible_asset_index, len(self.visible_assets) - 1))
        self.selected_asset_id = self.visible_assets[index].asset_id
        self.asset_grid_selection = self.selected_asset_id
        self.details_asset_selection = self.selected_asset_id
    finally:
        _selection_sync_exit()
    sync_editor_fields(context)


def _grid_selection_updated(self, context: bpy.types.Context) -> None:
    if _SELECTION_SYNC_ACTIVE:
        return
    selected_id = self.asset_grid_selection
    if not selected_id or selected_id == "__empty__":
        return
    if not _selection_sync_enter():
        return
    try:
        self.selected_asset_id = selected_id
        self.details_asset_selection = selected_id
        for index, item in enumerate(self.visible_assets):
            if item.asset_id == selected_id:
                self.visible_asset_index = index
                break
    finally:
        _selection_sync_exit()
    sync_editor_fields(context)


def _details_asset_updated(self, context: bpy.types.Context) -> None:
    if _SELECTION_SYNC_ACTIVE:
        return
    asset_id = self.details_asset_selection
    if not asset_id or asset_id == "__empty__":
        return
    set_active_asset_id(context, asset_id)


def category_enum_items(self, context: bpy.types.Context):
    items = [constants.FILTER_ALL_ITEM]
    items.extend((value, value, f"Filter by {value}") for value in runtime.categories())
    return items


def subcategory_enum_items(self, context: bpy.types.Context):
    category = context.window_manager.bgal_browser.category_filter if context else ""
    items = [constants.FILTER_ALL_ITEM]
    items.extend((value, value, f"Filter by {value}") for value in runtime.subcategories("" if category == "ALL" else category))
    return items


def editor_category_items(self, context: bpy.types.Context):
    items = [constants.ENUM_NONE_ITEM]
    items.extend((value, value, f"Assign {value}") for value in runtime.categories())
    items.append(constants.ENUM_ADD_NEW_CATEGORY_ITEM)
    return items


def _editor_subcategory_items_for_category(category: str):
    items = [constants.ENUM_NONE_ITEM]
    items.extend((value, value, f"Assign {value}") for value in runtime.subcategories(category))
    items.append(constants.ENUM_ADD_NEW_SUBCATEGORY_ITEM)
    return items


def editor_subcategory_items(self, context: bpy.types.Context):
    if _is_add_new_category(self.editor_category):
        return [constants.ENUM_NONE_ITEM, constants.ENUM_ADD_NEW_SUBCATEGORY_ITEM]
    category = _string_from_enum(self.editor_category)
    return _editor_subcategory_items_for_category(category)


def manager_category_items(self, context: bpy.types.Context):
    items = [constants.ENUM_NONE_ITEM]
    items.extend((value, value, f"Manage {value}") for value in runtime.categories())
    return items


def manager_subcategory_items(self, context: bpy.types.Context):
    category = _string_from_enum(self.manager_category)
    items = [constants.ENUM_NONE_ITEM]
    if category:
        items.extend((value, value, f"Manage {value}") for value in runtime.subcategories(category))
    return items


def grid_asset_items(self, context: bpy.types.Context):
    items = []
    browser = context.window_manager.bgal_browser if context else self
    for index, row in enumerate(browser.visible_assets):
        asset = runtime.get_asset(row.asset_id)
        icon_id = preview_manager.icon_id(row.asset_id, _preview_path_for_asset(asset))
        description = asset.description if asset else row.display_name
        items.append((row.asset_id, row.display_name, description, icon_id, index))
    if not items:
        items.append(("__empty__", "No Assets", "Rescan the library or widen the filters.", 0, 0))
    return items


def details_asset_items(self, context: bpy.types.Context):
    items = []
    browser = context.window_manager.bgal_browser if context else self
    for index, row in enumerate(browser.visible_assets):
        label = row.display_name
        description = row.category or "Uncategorized"
        if row.subcategory:
            description = f"{description} / {row.subcategory}"
        items.append((row.asset_id, label, description, index))
    if not items:
        items.append(("__empty__", "No Assets", "Rescan the library or widen the filters.", 0))
    return items


class BGAL_PG_LibraryRoot(PropertyGroup):
    label: StringProperty(name="Label")
    directory: StringProperty(name="Directory", subtype="DIR_PATH")
    enabled: BoolProperty(name="Enabled", default=True)


class BGAL_PG_VisibleAsset(PropertyGroup):
    asset_id: StringProperty()
    display_name: StringProperty()
    category: StringProperty()
    subcategory: StringProperty()
    description: StringProperty()
    file_path: StringProperty()
    tags: StringProperty()
    is_favorite: BoolProperty(default=False)
    warning_count: IntProperty(default=0)


class BGAL_PG_ManagerCategory(PropertyGroup):
    name: StringProperty()
    count: IntProperty(default=0)


class BGAL_PG_ManagerSubcategory(PropertyGroup):
    name: StringProperty()


class BGAL_PG_ManagerTag(PropertyGroup):
    name: StringProperty()


class BGAL_PG_BrowserState(PropertyGroup):
    search_text: StringProperty(name="Search", update=_filters_updated)
    category_filter: EnumProperty(name="Category", items=category_enum_items, update=_filters_updated)
    subcategory_filter: EnumProperty(name="Subcategory", items=subcategory_enum_items, update=_filters_updated)
    tag_filter: StringProperty(name="Tags", update=_filters_updated)
    sort_mode: EnumProperty(name="Sort", items=constants.SORT_MODE_ITEMS, default="NAME", update=_filters_updated)
    view_mode: EnumProperty(name="View", items=constants.VIEW_MODE_ITEMS, default="GRID")
    show_favorites_only: BoolProperty(name="Favorites Only", default=False, update=_filters_updated)
    show_browser_filters: BoolProperty(name="Show Filters", default=True)

    selected_asset_id: StringProperty()
    asset_grid_selection: EnumProperty(name="Assets", items=grid_asset_items, update=_grid_selection_updated)
    details_asset_selection: EnumProperty(name="Asset", items=details_asset_items, update=_details_asset_updated)
    visible_assets: CollectionProperty(type=BGAL_PG_VisibleAsset)
    visible_asset_index: IntProperty(update=_visible_index_updated)

    link_mode: EnumProperty(name="Import", items=constants.LINK_MODE_ITEMS, default="APPEND")
    make_local_after_link: BoolProperty(name="Make Local", default=False)
    use_namespace: BoolProperty(name="Namespace", default=False)
    namespace_prefix: StringProperty(name="Prefix")
    placement_mode: EnumProperty(name="Placement", items=constants.PLACEMENT_MODE_ITEMS, default="ORIGINAL")
    place_as_collection_instance: BoolProperty(name="Collection Instance", default=False)
    status_text: StringProperty(name="Status")
    update_available: BoolProperty(name="Update Available", default=False)
    update_check_in_progress: BoolProperty(name="Update Check In Progress", default=False)
    update_latest_version: StringProperty(name="Latest Version")
    update_release_name: StringProperty(name="Release Name")
    update_release_url: StringProperty(name="Release URL")
    update_download_url: StringProperty(name="Download URL")
    update_status_text: StringProperty(name="Update Status")
    update_error_text: StringProperty(name="Update Error")
    update_last_checked: StringProperty(name="Update Last Checked")
    editor_display_name: StringProperty(name="Library Name")
    editor_category: EnumProperty(name="Category", items=editor_category_items, update=_editor_category_updated)
    editor_subcategory: EnumProperty(name="Subcategory", items=editor_subcategory_items, update=_editor_subcategory_updated)
    editor_tags: StringProperty(name="Tags")
    editor_new_category_name: StringProperty(name="New Category")
    editor_new_subcategory_name: StringProperty(name="New Subcategory")
    new_category_name: StringProperty(name="New Category")
    new_subcategory_name: StringProperty(name="New Subcategory")
    manager_root_path: StringProperty(name="Manager Root")
    manager_categories: CollectionProperty(type=BGAL_PG_ManagerCategory)
    manager_category_index: IntProperty(update=_manager_category_index_updated)
    manager_category_input: StringProperty(name="Category Name")
    manager_subcategories: CollectionProperty(type=BGAL_PG_ManagerSubcategory)
    manager_subcategory_index: IntProperty(update=_manager_subcategory_index_updated)
    manager_subcategory_input: StringProperty(name="Subcategory Name")
    manager_tags: CollectionProperty(type=BGAL_PG_ManagerTag)
    manager_tag_index: IntProperty(update=_manager_tag_index_updated)
    manager_tag_input: StringProperty(name="Tag Name")
    show_categories_section: BoolProperty(name="Show Categories", default=True)
    show_subcategories_section: BoolProperty(name="Show Subcategories", default=True)
    show_tags_section: BoolProperty(name="Show Tags", default=True)
    manager_category: EnumProperty(name="Manage Category", items=manager_category_items, update=_manager_category_updated)
    manager_subcategory: EnumProperty(name="Manage Subcategory", items=manager_subcategory_items)
    manager_rename_category_name: StringProperty(name="Rename Category")
    manager_rename_subcategory_name: StringProperty(name="Rename Subcategory")


CLASSES = (
    BGAL_PG_LibraryRoot,
    BGAL_PG_VisibleAsset,
    BGAL_PG_ManagerCategory,
    BGAL_PG_ManagerSubcategory,
    BGAL_PG_ManagerTag,
    BGAL_PG_BrowserState,
)


def register() -> None:
    for cls in CLASSES:
        safe_register_class(cls)
    safe_assign_property(bpy.types.WindowManager, "bgal_browser", PointerProperty(type=BGAL_PG_BrowserState))


def unregister() -> None:
    safe_remove_property(bpy.types.WindowManager, "bgal_browser")
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
