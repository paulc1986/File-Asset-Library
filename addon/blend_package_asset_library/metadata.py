from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from . import constants
from .utils import dedupe_preserve_order, normalize_tags, resolve_relative_path, safe_slug


def find_metadata_file(blend_path: Path) -> Path | None:
    for pattern in constants.SUPPORTED_METADATA_FILENAMES:
        candidate = blend_path.parent / pattern.format(stem=blend_path.stem)
        if candidate.exists():
            return candidate
    return None


def override_file_path(blend_path: Path) -> Path:
    return blend_path.parent / f"{blend_path.stem}{constants.USER_OVERRIDE_SUFFIX}"


def override_item_key(item_key: str) -> str:
    return safe_slug(item_key or "default")


def category_registry_file_path(root_path: Path) -> Path:
    return root_path / constants.CATEGORY_REGISTRY_FILE_NAME


def tag_registry_file_path(root_path: Path) -> Path:
    return root_path / constants.TAG_REGISTRY_FILE_NAME


def _write_category_registry(root_path: Path, registry: dict[str, list[str]]) -> str:
    path = category_registry_file_path(root_path)
    payload = {
        "version": 1,
        "categories": [
            {
                "name": name,
                "subcategories": dedupe_preserve_order(registry[name]),
            }
            for name in sorted(registry, key=str.casefold)
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return str(path)


def _write_tag_registry(root_path: Path, tags: list[str]) -> str:
    path = tag_registry_file_path(root_path)
    payload = {
        "version": 1,
        "tags": dedupe_preserve_order(tags),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return str(path)


def _override_file_paths_in_root(root_path: Path) -> list[Path]:
    pattern = f"*{constants.USER_OVERRIDE_SUFFIX}"
    return sorted(root_path.rglob(pattern), key=lambda path: str(path).casefold())


def _write_or_delete_override_payload(path: Path, payload: dict[str, Any]) -> None:
    default_value = payload.get("default")
    items_value = payload.get("items")
    has_default = isinstance(default_value, dict) and bool(default_value)
    has_items = isinstance(items_value, dict) and bool(items_value)
    if not has_default and not has_items:
        try:
            path.unlink()
        except Exception:
            pass
        return
    payload.setdefault("version", 1)
    payload.setdefault("items", {})
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _mutate_override_payloads(root_path: Path, mutator) -> None:
    for path in _override_file_paths_in_root(root_path):
        payload, _warnings = parse_metadata_file(path)
        if not isinstance(payload, dict):
            continue
        changed = False
        default_value = payload.get("default")
        if isinstance(default_value, dict):
            changed = mutator(default_value) or changed
        items_value = payload.get("items", {})
        if isinstance(items_value, dict):
            for item_payload in items_value.values():
                if isinstance(item_payload, dict):
                    changed = mutator(item_payload) or changed
        if changed:
            _write_or_delete_override_payload(path, payload)


def _strip_yaml_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        stripped = raw_line.lstrip()
        if stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(stripped)
        lines.append((indent, stripped.rstrip()))
    return lines


def _split_key_value(content: str) -> tuple[str, str]:
    key, _, value = content.partition(":")
    return key.strip(), value.strip()


def _parse_inline_list(content: str) -> list[Any]:
    inner = content[1:-1].strip()
    if not inner:
        return []
    result: list[Any] = []
    current = []
    depth = 0
    quote = ""
    for char in inner:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        if char == "," and depth == 0:
            result.append(_parse_scalar("".join(current).strip()))
            current = []
            continue
        current.append(char)
    if current:
        result.append(_parse_scalar("".join(current).strip()))
    return result


def _parse_inline_dict(content: str) -> dict[str, Any]:
    inner = content[1:-1].strip()
    if not inner:
        return {}
    result: dict[str, Any] = {}
    parts = _parse_inline_list(f"[{inner}]")
    for item in parts:
        if isinstance(item, str) and ":" in item:
            key, value = _split_key_value(item)
            result[key] = _parse_scalar(value)
    return result


def _parse_scalar(content: str) -> Any:
    if content == "":
        return ""
    lowered = content.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if content.startswith("[") and content.endswith("]"):
        return _parse_inline_list(content)
    if content.startswith("{") and content.endswith("}"):
        return _parse_inline_dict(content)
    if content.startswith(("'", '"')) and content.endswith(("'", '"')):
        try:
            return ast.literal_eval(content)
        except Exception:
            return content[1:-1]
    try:
        return int(content)
    except Exception:
        pass
    try:
        return float(content)
    except Exception:
        return content


def _parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index

    current_indent, current_content = lines[index]
    if current_indent < indent:
        return {}, index

    if current_content.startswith("- "):
        items: list[Any] = []
        i = index
        while i < len(lines):
            line_indent, content = lines[i]
            if line_indent != current_indent or not content.startswith("- "):
                break
            item_content = content[2:].strip()
            if not item_content:
                value, i = _parse_yaml_block(lines, i + 1, current_indent + 2)
                items.append(value)
                continue

            if ":" in item_content and not item_content.startswith(("[", "{")):
                key, value_text = _split_key_value(item_content)
                item: dict[str, Any] = {}
                if value_text:
                    item[key] = _parse_scalar(value_text)
                    i += 1
                else:
                    value, i = _parse_yaml_block(lines, i + 1, current_indent + 2)
                    item[key] = value
                while i < len(lines):
                    next_indent, next_content = lines[i]
                    if next_indent < current_indent + 2:
                        break
                    if next_indent == current_indent and next_content.startswith("- "):
                        break
                    extra, i = _parse_yaml_block(lines, i, current_indent + 2)
                    if isinstance(extra, dict):
                        item.update(extra)
                    else:
                        break
                items.append(item)
            else:
                items.append(_parse_scalar(item_content))
                i += 1
        return items, i

    mapping: dict[str, Any] = {}
    i = index
    while i < len(lines):
        line_indent, content = lines[i]
        if line_indent < indent:
            break
        if line_indent > indent:
            break
        if content.startswith("- "):
            break
        key, value_text = _split_key_value(content)
        if not key:
            i += 1
            continue
        if value_text:
            mapping[key] = _parse_scalar(value_text)
            i += 1
        else:
            if i + 1 < len(lines) and lines[i + 1][0] > line_indent:
                value, i = _parse_yaml_block(lines, i + 1, lines[i + 1][0])
                mapping[key] = value
            else:
                mapping[key] = None
                i += 1
    return mapping, i


def parse_yaml(text: str) -> Any:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        pass
    lines = _strip_yaml_lines(text)
    if not lines:
        return {}
    result, _ = _parse_yaml_block(lines, 0, lines[0][0])
    return result


def parse_metadata_file(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {}, [f"Failed to read metadata: {exc}"]

    try:
        if path.suffix.lower() == ".json":
            payload = json.loads(raw)
        else:
            payload = parse_yaml(raw)
    except Exception as exc:
        return {}, [f"Failed to parse metadata: {exc}"]

    if not isinstance(payload, dict):
        warnings.append("Metadata root must be a mapping/dictionary.")
        return {}, warnings
    return payload, warnings


def _resolve_thumbnail(value: str, source_path: Path) -> str:
    if not value:
        return ""
    return resolve_relative_path(source_path, value)


def normalize_metadata(payload: dict[str, Any], source_path: Path) -> dict[str, Any]:
    data = dict(payload)
    data["display_name"] = str(data.get("display_name", "")).strip()
    category = str(data.get("category", "")).strip()
    subcategory = str(data.get("subcategory", "")).strip()
    group = str(data.get("group", "")).strip()
    catalogue = str(
        data.get("catalogue_path", "")
        or data.get("catalogue", "")
        or data.get("catalog", "")
    ).strip()
    if catalogue:
        parts = [part.strip() for part in catalogue.replace(">", "/").replace("|", "/").split("/") if part.strip()]
        if not category and parts:
            category = parts[0]
        if not subcategory and len(parts) > 1:
            subcategory = parts[1]
        if not group and len(parts) > 2:
            group = " / ".join(parts[2:])
    data["category"] = category
    data["subcategory"] = subcategory
    data["description"] = str(data.get("description", "")).strip()
    data["author"] = str(data.get("author", "")).strip()
    data["version"] = str(data.get("version", "")).strip()
    data["enabled"] = bool(data.get("enabled", True))
    data["import_mode"] = str(data.get("import_mode", "AUTO")).upper()
    data["entry_object"] = str(data.get("entry_object", "")).strip()
    data["entry_collection"] = str(data.get("entry_collection", "")).strip()
    entry_objects = data.get("entry_objects") or data.get("objects") or []
    data["entry_objects"] = dedupe_preserve_order([str(item).strip() for item in entry_objects if str(item).strip()])
    data["thumbnail"] = _resolve_thumbnail(str(data.get("thumbnail", "")).strip(), source_path)
    data["tags"] = normalize_tags(data.get("tags"))
    data["group"] = group
    data["catalogue"] = catalogue

    normalized_items: list[dict[str, Any]] = []
    for item in data.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        normalized_items.append(normalize_metadata(item, source_path))
    data["items"] = normalized_items
    return data


def load_metadata_for_blend(blend_path: Path) -> tuple[dict[str, Any], list[str], str]:
    metadata_path = find_metadata_file(blend_path)
    if metadata_path is None:
        return {}, [], ""
    payload, warnings = parse_metadata_file(metadata_path)
    return normalize_metadata(payload, metadata_path), warnings, str(metadata_path)


def load_user_override_for_asset(blend_path: Path, item_key: str) -> tuple[dict[str, Any], str]:
    path = override_file_path(blend_path)
    if not path.exists():
        return {}, str(path)
    payload, _warnings = parse_metadata_file(path)
    if not isinstance(payload, dict):
        return {}, str(path)
    items = payload.get("items", {}) if isinstance(payload.get("items", {}), dict) else {}
    override = {}
    key = override_item_key(item_key)
    if item_key and isinstance(items.get(key), dict):
        override = dict(items[key])
    elif isinstance(payload.get("default"), dict):
        override = dict(payload["default"])
    elif isinstance(items.get(key), dict):
        override = dict(items[key])
    return normalize_metadata(override, path) if override else {}, str(path)


def save_user_override_for_asset(
    blend_path: Path,
    item_key: str,
    payload: dict[str, Any],
) -> str:
    path = override_file_path(blend_path)
    existing, _warnings = parse_metadata_file(path) if path.exists() else ({}, [])
    if not isinstance(existing, dict):
        existing = {}
    existing.setdefault("version", 1)
    existing.setdefault("items", {})

    cleaned = {
        "display_name": str(payload.get("display_name", "")).strip(),
        "category": str(payload.get("category", "")).strip(),
        "subcategory": str(payload.get("subcategory", "")).strip(),
        "tags": normalize_tags(payload.get("tags")),
    }

    key = override_item_key(item_key)
    if item_key:
        items = dict(existing.get("items", {}))
        items[key] = cleaned
        existing["items"] = items
    else:
        existing["default"] = cleaned

    path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def clear_user_override_for_asset(blend_path: Path, item_key: str) -> str:
    path = override_file_path(blend_path)
    if not path.exists():
        return str(path)
    existing, _warnings = parse_metadata_file(path)
    if not isinstance(existing, dict):
        try:
            path.unlink()
        except Exception:
            pass
        return str(path)

    key = override_item_key(item_key)
    if item_key:
        items = dict(existing.get("items", {}))
        items.pop(key, None)
        if items:
            existing["items"] = items
        else:
            existing.pop("items", None)
    else:
        existing.pop("default", None)

    if not existing.get("default") and not existing.get("items"):
        try:
            path.unlink()
        except Exception:
            pass
    else:
        path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def load_category_registry(root_path: Path) -> dict[str, list[str]]:
    path = category_registry_file_path(root_path)
    if not path.exists():
        return {}
    payload, _warnings = parse_metadata_file(path)
    if not isinstance(payload, dict):
        return {}

    registry: dict[str, list[str]] = {}
    raw_categories = payload.get("categories", [])
    if isinstance(raw_categories, dict):
        for category, subcategories in raw_categories.items():
            category_name = str(category).strip()
            if not category_name:
                continue
            values = normalize_tags(subcategories)
            registry[category_name] = dedupe_preserve_order(values)
        return registry

    if not isinstance(raw_categories, list):
        return {}

    for item in raw_categories:
        if not isinstance(item, dict):
            continue
        category_name = str(item.get("name", "")).strip()
        if not category_name:
            continue
        registry[category_name] = dedupe_preserve_order(normalize_tags(item.get("subcategories")))
    return registry


def load_tag_registry(root_path: Path) -> list[str]:
    path = tag_registry_file_path(root_path)
    if not path.exists():
        return []
    payload, _warnings = parse_metadata_file(path)
    if not isinstance(payload, dict):
        return []
    return dedupe_preserve_order(normalize_tags(payload.get("tags")))


def save_category_registry_entry(root_path: Path, category: str, subcategory: str = "") -> str:
    category_name = str(category).strip()
    subcategory_name = str(subcategory).strip()
    if not category_name:
        raise ValueError("Category name is required.")

    path = category_registry_file_path(root_path)
    registry = load_category_registry(root_path)
    values = list(registry.get(category_name, []))
    if subcategory_name and subcategory_name not in values:
        values.append(subcategory_name)
    registry[category_name] = dedupe_preserve_order(values)

    return _write_category_registry(root_path, registry)


def save_tag_registry_entry(root_path: Path, tag_name: str) -> str:
    value = str(tag_name).strip()
    if not value:
        raise ValueError("A tag name is required.")
    tags = load_tag_registry(root_path)
    if value not in tags:
        tags.append(value)
    return _write_tag_registry(root_path, tags)


def rename_category_registry_entry(root_path: Path, old_name: str, new_name: str) -> str:
    old_value = str(old_name).strip()
    new_value = str(new_name).strip()
    if not old_value or not new_value:
        raise ValueError("Both the old and new category names are required.")

    registry = load_category_registry(root_path)
    existing = list(registry.get(old_value, []))
    if old_value not in registry:
        raise ValueError(f"Category '{old_value}' was not found in this library.")

    merged = dedupe_preserve_order(list(registry.get(new_value, [])) + existing)
    registry.pop(old_value, None)
    registry[new_value] = merged

    def _mutate(payload: dict[str, Any]) -> bool:
        if str(payload.get("category", "")).strip() != old_value:
            return False
        payload["category"] = new_value
        return True

    _mutate_override_payloads(root_path, _mutate)
    return _write_category_registry(root_path, registry)


def remove_category_registry_entry(root_path: Path, category_name: str) -> str:
    target = str(category_name).strip()
    if not target:
        raise ValueError("A category name is required.")

    registry = load_category_registry(root_path)
    if target not in registry:
        raise ValueError(f"Category '{target}' was not found in this library.")
    registry.pop(target, None)

    def _mutate(payload: dict[str, Any]) -> bool:
        if str(payload.get("category", "")).strip() != target:
            return False
        payload["category"] = ""
        payload["subcategory"] = ""
        return True

    _mutate_override_payloads(root_path, _mutate)
    return _write_category_registry(root_path, registry)


def rename_subcategory_registry_entry(root_path: Path, category_name: str, old_name: str, new_name: str) -> str:
    category_value = str(category_name).strip()
    old_value = str(old_name).strip()
    new_value = str(new_name).strip()
    if not category_value or not old_value or not new_value:
        raise ValueError("Category, old subcategory, and new subcategory are required.")

    registry = load_category_registry(root_path)
    values = list(registry.get(category_value, []))
    if old_value not in values:
        raise ValueError(f"Subcategory '{old_value}' was not found under '{category_value}'.")
    values = [new_value if value == old_value else value for value in values]
    registry[category_value] = dedupe_preserve_order(values)

    def _mutate(payload: dict[str, Any]) -> bool:
        if str(payload.get("category", "")).strip() != category_value:
            return False
        if str(payload.get("subcategory", "")).strip() != old_value:
            return False
        payload["subcategory"] = new_value
        return True

    _mutate_override_payloads(root_path, _mutate)
    return _write_category_registry(root_path, registry)


def remove_subcategory_registry_entry(root_path: Path, category_name: str, subcategory_name: str) -> str:
    category_value = str(category_name).strip()
    target = str(subcategory_name).strip()
    if not category_value or not target:
        raise ValueError("Category and subcategory are required.")

    registry = load_category_registry(root_path)
    values = [value for value in registry.get(category_value, []) if value != target]
    if category_value not in registry:
        raise ValueError(f"Category '{category_value}' was not found in this library.")
    registry[category_value] = values

    def _mutate(payload: dict[str, Any]) -> bool:
        if str(payload.get("category", "")).strip() != category_value:
            return False
        if str(payload.get("subcategory", "")).strip() != target:
            return False
        payload["subcategory"] = ""
        return True

    _mutate_override_payloads(root_path, _mutate)
    return _write_category_registry(root_path, registry)


def rename_tag_registry_entry(root_path: Path, old_name: str, new_name: str) -> str:
    old_value = str(old_name).strip()
    new_value = str(new_name).strip()
    if not old_value or not new_value:
        raise ValueError("Both the old and new tag names are required.")

    tags = load_tag_registry(root_path)
    if old_value not in tags:
        raise ValueError(f"Tag '{old_value}' was not found in this library.")
    tags = [new_value if value == old_value else value for value in tags]
    tags = dedupe_preserve_order(tags)

    def _mutate(payload: dict[str, Any]) -> bool:
        current = normalize_tags(payload.get("tags"))
        if old_value not in current:
            return False
        payload["tags"] = [new_value if value == old_value else value for value in current]
        payload["tags"] = dedupe_preserve_order(payload["tags"])
        return True

    _mutate_override_payloads(root_path, _mutate)
    return _write_tag_registry(root_path, tags)


def remove_tag_registry_entry(root_path: Path, tag_name: str) -> str:
    target = str(tag_name).strip()
    if not target:
        raise ValueError("A tag name is required.")

    tags = [value for value in load_tag_registry(root_path) if value != target]

    def _mutate(payload: dict[str, Any]) -> bool:
        current = normalize_tags(payload.get("tags"))
        if target not in current:
            return False
        payload["tags"] = [value for value in current if value != target]
        return True

    _mutate_override_payloads(root_path, _mutate)
    return _write_tag_registry(root_path, tags)


def merge_metadata(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "items":
            continue
        if key == "tags":
            merged[key] = dedupe_preserve_order(list(base.get("tags", [])) + list(value))
        elif value not in (None, "", []):
            merged[key] = value
    return merged
