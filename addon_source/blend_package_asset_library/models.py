from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ValidationReport:
    status: str = "UNKNOWN"
    warnings: list[str] = field(default_factory=list)
    checked_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ValidationReport":
        payload = payload or {}
        return cls(
            status=payload.get("status", "UNKNOWN"),
            warnings=list(payload.get("warnings", [])),
            checked_at=float(payload.get("checked_at", 0.0)),
        )


@dataclass
class InspectionData:
    collections: list[str] = field(default_factory=list)
    top_level_collections: list[str] = field(default_factory=list)
    asset_named_collections: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    root_objects: list[str] = field(default_factory=list)
    armature_roots: list[str] = field(default_factory=list)
    object_hierarchies: dict[str, list[str]] = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)
    author: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "InspectionData":
        payload = payload or {}
        return cls(
            collections=list(payload.get("collections", [])),
            top_level_collections=list(payload.get("top_level_collections", [])),
            asset_named_collections=list(payload.get("asset_named_collections", [])),
            objects=list(payload.get("objects", [])),
            root_objects=list(payload.get("root_objects", [])),
            armature_roots=list(payload.get("armature_roots", [])),
            object_hierarchies=dict(payload.get("object_hierarchies", {})),
            actions=list(payload.get("actions", [])),
            author=payload.get("author", ""),
        )


@dataclass
class AssetEntry:
    asset_id: str
    file_path: str
    root_path: str
    relative_path: str
    display_name: str
    category: str = ""
    subcategory: str = ""
    base_display_name: str = ""
    base_category: str = ""
    base_subcategory: str = ""
    base_tags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    author: str = ""
    version: str = ""
    enabled: bool = True
    import_mode: str = "AUTO"
    target_kind: str = "BLEND"
    target_names: list[str] = field(default_factory=list)
    detection_strategy: str = ""
    thumbnail_source: str = ""
    thumbnail_cache: str = ""
    metadata_source: str = ""
    source_mtime: float = 0.0
    source_size: int = 0
    source_signature: str = ""
    package_key: str = ""
    library_label: str = ""
    folder_group: str = ""
    item_key: str = ""
    warnings: list[str] = field(default_factory=list)
    validation: ValidationReport = field(default_factory=ValidationReport)
    inspection: InspectionData = field(default_factory=InspectionData)
    is_favorite: bool = False
    recent_rank: int = 0
    last_used_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["validation"] = self.validation.to_dict()
        payload["inspection"] = self.inspection.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AssetEntry":
        data = dict(payload)
        data["validation"] = ValidationReport.from_dict(data.get("validation"))
        data["inspection"] = InspectionData.from_dict(data.get("inspection"))
        data["base_display_name"] = data.get("base_display_name", data.get("display_name", ""))
        data["base_category"] = data.get("base_category", data.get("category", ""))
        data["base_subcategory"] = data.get("base_subcategory", data.get("subcategory", ""))
        data["base_tags"] = list(data.get("base_tags", data.get("tags", [])))
        data["tags"] = list(data.get("tags", []))
        data["warnings"] = list(data.get("warnings", []))
        data["target_names"] = list(data.get("target_names", []))
        return cls(**data)


@dataclass
class AssetIndex:
    version: int = 1
    scanned_at: float = 0.0
    entries: list[AssetEntry] = field(default_factory=list)
    roots: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "scanned_at": self.scanned_at,
            "entries": [entry.to_dict() for entry in self.entries],
            "roots": list(self.roots),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "AssetIndex":
        payload = payload or {}
        return cls(
            version=int(payload.get("version", 1)),
            scanned_at=float(payload.get("scanned_at", 0.0)),
            entries=[AssetEntry.from_dict(entry) for entry in payload.get("entries", [])],
            roots=list(payload.get("roots", [])),
        )
