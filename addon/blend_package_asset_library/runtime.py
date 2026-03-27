from __future__ import annotations

from collections import defaultdict

from .models import AssetEntry, AssetIndex


_asset_index = AssetIndex()
_asset_map: dict[str, AssetEntry] = {}
_category_registry: dict[str, set[str]] = {}
_tag_registry: set[str] = set()


def set_index(index: AssetIndex) -> None:
    global _asset_index, _asset_map
    _asset_index = index
    _asset_map = {entry.asset_id: entry for entry in index.entries}


def set_category_registry(registry: dict[str, list[str] | set[str]]) -> None:
    global _category_registry
    merged: dict[str, set[str]] = {}
    for category, subcategories in registry.items():
        name = str(category).strip()
        if not name:
            continue
        merged[name] = {str(value).strip() for value in subcategories if str(value).strip()}
    _category_registry = merged


def set_tag_registry(values) -> None:
    global _tag_registry
    _tag_registry = {str(value).strip() for value in values if str(value).strip()}


def category_registry() -> dict[str, list[str]]:
    return {
        category: sorted(values, key=str.casefold)
        for category, values in sorted(_category_registry.items(), key=lambda item: item[0].casefold())
    }


def get_index() -> AssetIndex:
    return _asset_index


def all_assets() -> list[AssetEntry]:
    return list(_asset_index.entries)


def get_asset(asset_id: str) -> AssetEntry | None:
    return _asset_map.get(asset_id)


def categories() -> list[str]:
    values = {entry.category for entry in _asset_index.entries if entry.category}
    values.update(_category_registry.keys())
    return sorted(values, key=str.casefold)


def subcategories(category: str = "") -> list[str]:
    values = {
        entry.subcategory
        for entry in _asset_index.entries
        if entry.subcategory and (not category or entry.category == category)
    }
    if category:
        values.update(_category_registry.get(category, set()))
    else:
        for subcategories in _category_registry.values():
            values.update(subcategories)
    return sorted(values, key=str.casefold)


def tags() -> list[str]:
    values: set[str] = set()
    for entry in _asset_index.entries:
        values.update(entry.tags)
    values.update(_tag_registry)
    return sorted(values, key=str.casefold)


def grouped_counts() -> dict[str, int]:
    counts = defaultdict(int)
    for entry in _asset_index.entries:
        label = entry.category or "Uncategorized"
        counts[label] += 1
    return dict(counts)
