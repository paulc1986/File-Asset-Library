from __future__ import annotations

import bpy
import gc


def _lookup_registered_class(cls, identifier: str):
    existing = getattr(bpy.types, identifier, None)
    if isinstance(existing, type):
        return existing

    for base in cls.__mro__[1:]:
        lookup = getattr(base, "bl_rna_get_subclass_py", None)
        if not callable(lookup):
            continue
        try:
            existing = lookup(identifier, None)
        except TypeError:
            try:
                existing = lookup(identifier)
            except Exception:
                existing = None
        except Exception:
            existing = None
        if isinstance(existing, type):
            return existing
    return None


def _candidate_registered_classes(cls):
    candidates: list[type] = []
    identifiers = [cls.__name__]
    bl_idname = getattr(cls, "bl_idname", "")
    if bl_idname:
        identifiers.append(bl_idname)

    for identifier in identifiers:
        existing = _lookup_registered_class(cls, identifier)
        if isinstance(existing, type) and existing not in candidates:
            candidates.append(existing)

    for obj in gc.get_objects():
        if not isinstance(obj, type):
            continue
        if obj is cls:
            candidates.append(obj)
            continue
        same_name = obj.__name__ == cls.__name__
        same_module = getattr(obj, "__module__", "") == getattr(cls, "__module__", "")
        same_idname = bool(bl_idname) and getattr(obj, "bl_idname", "") == bl_idname
        if (same_name and same_module) or same_idname:
            if obj not in candidates:
                candidates.append(obj)
    return candidates


def _unregister_candidates(cls) -> None:
    for candidate in _candidate_registered_classes(cls):
        try:
            bpy.utils.unregister_class(candidate)
        except Exception:
            pass


def safe_register_class(cls) -> None:
    last_error = None
    for _ in range(3):
        _unregister_candidates(cls)
        gc.collect()
        try:
            bpy.utils.register_class(cls)
            return
        except (RuntimeError, ValueError) as exc:
            message = str(exc)
            if "already registered as a subclass" not in message and "already registered" not in message:
                raise
            last_error = exc
    if last_error is not None:
        raise last_error


def safe_unregister_class(cls) -> None:
    _unregister_candidates(cls)


def safe_remove_property(owner, name: str) -> None:
    if hasattr(owner, name):
        try:
            delattr(owner, name)
        except Exception:
            pass


def safe_assign_property(owner, name: str, value) -> None:
    safe_remove_property(owner, name)
    setattr(owner, name, value)
