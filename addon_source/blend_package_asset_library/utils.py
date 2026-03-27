from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

import bpy

from . import constants


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_directory() -> Path:
    try:
        base = bpy.utils.user_resource("CONFIG", path=constants.ADDON_PACKAGE, create=False)
        return ensure_directory(Path(base))
    except Exception:
        base = str(Path(tempfile.gettempdir()) / constants.ADDON_PACKAGE / "config")
        return ensure_directory(Path(base))


def cache_directory() -> Path:
    try:
        base = bpy.utils.user_resource("CACHE", path=constants.ADDON_PACKAGE, create=False)
        return ensure_directory(Path(base))
    except Exception:
        base = str(Path(tempfile.gettempdir()) / constants.ADDON_PACKAGE / "cache")
        return ensure_directory(Path(base))


def thumbnails_directory() -> Path:
    return ensure_directory(cache_directory() / constants.THUMBNAIL_CACHE_DIR)


def index_file_path() -> Path:
    return config_directory() / constants.INDEX_FILE_NAME


def state_file_path() -> Path:
    return config_directory() / constants.STATE_FILE_NAME


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def file_signature(path: Path) -> tuple[float, int, str]:
    stat = path.stat()
    signature = f"{stat.st_mtime_ns}:{stat.st_size}"
    return stat.st_mtime, stat.st_size, signature


def stable_asset_id(*parts: str) -> str:
    raw = "::".join(parts).encode("utf-8")
    return hashlib.sha1(raw, usedforsecurity=False).hexdigest()[:16]


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    slug = slug.strip("_")
    return slug or "asset"


def sanitize_name(value: str) -> str:
    return value.replace("\\", "/").strip()


def dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def split_tag_text(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[;,]", value)
    return [part.strip() for part in parts if part.strip()]


def normalize_tags(values: Iterable[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return split_tag_text(values)
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            result.append(text)
    return dedupe_preserve_order(result)


def resolve_relative_path(source: Path, value: str) -> str:
    if not value:
        return ""
    candidate = Path(value)
    if candidate.is_absolute():
        return normalized_blend_path(str(candidate))
    return normalized_blend_path(str((source.parent / candidate).resolve()))


def normalized_blend_path(value: str) -> str:
    if not value:
        return ""
    try:
        return str(Path(value).expanduser().resolve())
    except Exception:
        return str(Path(value))


def best_display_name(filepath: Path) -> str:
    return filepath.stem.replace("_", " ").replace("-", " ").strip() or filepath.stem


def open_in_file_browser(path: str) -> tuple[bool, str]:
    target = Path(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target if target.is_dir() else target.parent))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target if target.is_dir() else target.parent)])
    except Exception as exc:
        return False, str(exc)
    return True, ""


def open_blend_in_new_instance(filepath: str) -> tuple[bool, str]:
    try:
        subprocess.Popen([bpy.app.binary_path, filepath])
    except Exception as exc:
        return False, str(exc)
    return True, ""


def path_exists(value: str) -> bool:
    return bool(value) and Path(value).exists()


def readable_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for suffix in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or suffix == "TB":
            return f"{value:.1f} {suffix}"
        value /= 1024.0
    return f"{num_bytes} B"


def safe_remove_ids(ids_to_remove: Iterable[Any]) -> None:
    unique = []
    seen: set[int] = set()
    for item in ids_to_remove:
        if item is None:
            continue
        pointer = item.as_pointer()
        if pointer in seen:
            continue
        seen.add(pointer)
        unique.append(item)
    if not unique:
        return
    try:
        bpy.data.batch_remove(unique)
    except Exception:
        for item in reversed(unique):
            try:
                item.user_clear()
            except Exception:
                pass
            try:
                id_collection = getattr(bpy.data, item.__class__.__name__.lower() + "s", None)
                if id_collection is not None:
                    id_collection.remove(item)
            except Exception:
                pass
