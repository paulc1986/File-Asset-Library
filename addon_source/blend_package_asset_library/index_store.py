from __future__ import annotations

import time
from typing import Any

from .models import AssetIndex
from .utils import index_file_path, load_json, save_json, state_file_path


def load_index() -> AssetIndex:
    payload = load_json(index_file_path(), {})
    return AssetIndex.from_dict(payload)


def save_index(index: AssetIndex) -> None:
    index.scanned_at = time.time()
    save_json(index_file_path(), index.to_dict())


def load_ui_state() -> dict[str, Any]:
    default_state = {
        "favorites": [],
        "recent": [],
        "validations": {},
        "overrides": {},
    }
    payload = load_json(state_file_path(), default_state)
    if not isinstance(payload, dict):
        return default_state
    return {
        "favorites": list(payload.get("favorites", [])),
        "recent": list(payload.get("recent", [])),
        "validations": dict(payload.get("validations", {})),
        "overrides": dict(payload.get("overrides", {})),
    }


def save_ui_state(state: dict[str, Any]) -> None:
    save_json(state_file_path(), state)


def toggle_favorite(asset_id: str) -> bool:
    state = load_ui_state()
    favorites = list(state.get("favorites", []))
    if asset_id in favorites:
        favorites.remove(asset_id)
        favorite = False
    else:
        favorites.append(asset_id)
        favorite = True
    state["favorites"] = favorites
    save_ui_state(state)
    return favorite


def register_recent(asset_id: str, limit: int = 32) -> None:
    state = load_ui_state()
    recent = [item for item in state.get("recent", []) if item != asset_id]
    recent.insert(0, asset_id)
    state["recent"] = recent[:limit]
    save_ui_state(state)


def store_validation(asset_id: str, validation_payload: dict[str, Any]) -> None:
    state = load_ui_state()
    validations = dict(state.get("validations", {}))
    validations[asset_id] = validation_payload
    state["validations"] = validations
    save_ui_state(state)


def store_asset_override(asset_id: str, override_payload: dict[str, Any]) -> None:
    state = load_ui_state()
    overrides = dict(state.get("overrides", {}))
    cleaned = {
        "display_name": str(override_payload.get("display_name", "")).strip(),
        "category": str(override_payload.get("category", "")).strip(),
        "subcategory": str(override_payload.get("subcategory", "")).strip(),
    }
    overrides[asset_id] = cleaned
    state["overrides"] = overrides
    save_ui_state(state)


def clear_asset_override(asset_id: str) -> None:
    state = load_ui_state()
    overrides = dict(state.get("overrides", {}))
    overrides.pop(asset_id, None)
    state["overrides"] = overrides
    save_ui_state(state)
