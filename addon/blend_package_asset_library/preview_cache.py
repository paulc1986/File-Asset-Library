from __future__ import annotations

import base64
from pathlib import Path

import bpy.utils.previews

from .utils import ensure_directory, thumbnails_directory


PLACEHOLDER_PNG = (
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+"
    b"Em0AAAAASUVORK5CYII="
)


class PreviewManager:
    def __init__(self) -> None:
        self._collection = None
        self._paths: dict[str, str] = {}
        self._placeholder_path = ""

    def register(self) -> None:
        if self._collection is None:
            self._collection = bpy.utils.previews.new()

    def unregister(self) -> None:
        if self._collection is not None:
            bpy.utils.previews.remove(self._collection)
            self._collection = None
        self._paths.clear()

    def clear(self) -> None:
        if self._collection is None:
            return
        self._collection.clear()
        self._paths.clear()

    def _ensure_placeholder(self) -> str:
        if self._placeholder_path:
            return self._placeholder_path
        directory = ensure_directory(thumbnails_directory())
        path = directory / "_placeholder.png"
        if not path.exists():
            path.write_bytes(base64.b64decode(PLACEHOLDER_PNG))
        self._placeholder_path = str(path)
        return self._placeholder_path

    def _resolve_source(self, image_path: str) -> str:
        candidate = Path(image_path) if image_path else None
        if candidate and candidate.exists():
            return str(candidate)
        return self._ensure_placeholder()

    def icon_id(self, asset_id: str, image_path: str) -> int:
        self.register()
        assert self._collection is not None
        source = self._resolve_source(image_path)
        previous = self._paths.get(asset_id)
        if previous == source and asset_id in self._collection:
            return self._collection[asset_id].icon_id
        if asset_id in self._collection:
            del self._collection[asset_id]
        thumb = self._collection.load(asset_id, source, "IMAGE")
        self._paths[asset_id] = source
        return thumb.icon_id

    def invalidate(self, asset_id: str) -> None:
        if self._collection is None:
            return
        if asset_id in self._collection:
            del self._collection[asset_id]
        self._paths.pop(asset_id, None)


preview_manager = PreviewManager()
