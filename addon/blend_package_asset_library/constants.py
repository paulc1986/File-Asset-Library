ADDON_PACKAGE = "blend_package_asset_library"
ADDON_ID = "BLEND_PACKAGE_ASSET_LIBRARY"
REPOSITORY_URL = "https://github.com/paulc1986/File-Asset-Library"
RELEASE_URL = "https://github.com/paulc1986/File-Asset-Library/releases/tag/Release"
RELEASE_API_URL = "https://api.github.com/repos/paulc1986/File-Asset-Library/releases/latest"

INDEX_FILE_NAME = "asset_index.json"
STATE_FILE_NAME = "ui_state.json"
THUMBNAIL_CACHE_DIR = "thumbnails"
USER_OVERRIDE_SUFFIX = ".bgal.json"
CATEGORY_REGISTRY_FILE_NAME = ".bgal_categories.json"
TAG_REGISTRY_FILE_NAME = ".bgal_tags.json"

PREVIEW_COLLECTION_NAME = "blend_package_asset_library_previews"
ASSET_COLLECTION_PREFIX = "ASSET_"
ENUM_NONE_IDENTIFIER = "__NONE__"
ENUM_ADD_NEW_CATEGORY_IDENTIFIER = "__ADD_NEW_CATEGORY__"
ENUM_ADD_NEW_SUBCATEGORY_IDENTIFIER = "__ADD_NEW_SUBCATEGORY__"

SUPPORTED_METADATA_FILENAMES = (
    "{stem}.asset.json",
    "{stem}.asset.yaml",
    "{stem}.asset.yml",
    "{stem}.json",
    "{stem}.yaml",
    "{stem}.yml",
    "asset.json",
    "asset.yaml",
    "asset.yml",
)

COMMON_PREVIEW_FILENAMES = (
    "{stem}.png",
    "{stem}.jpg",
    "{stem}.jpeg",
    "{stem}.webp",
    "{stem}_preview.png",
    "{stem}_preview.jpg",
    "{stem}_thumb.png",
    "{stem}_thumb.jpg",
    "preview.png",
    "preview.jpg",
    "preview.jpeg",
    "thumbnail.png",
    "thumbnail.jpg",
    "thumb.png",
    "thumb.jpg",
    "cover.png",
    "cover.jpg",
)

IMPORT_MODE_ITEMS = (
    ("AUTO", "Auto", "Use metadata or detection rules"),
    ("COLLECTION", "Collection", "Import a collection entry"),
    ("OBJECT_HIERARCHY", "Object Hierarchy", "Import one object hierarchy"),
    ("OBJECTS", "Objects", "Import specific objects"),
    ("BLEND", "Whole Blend", "Import the entire package"),
)

LINK_MODE_ITEMS = (
    ("APPEND", "Append", "Append local datablocks"),
    ("LINK", "Link", "Link datablocks from the source blend"),
)

PLACEMENT_MODE_ITEMS = (
    ("ORIGINAL", "Keep Source Transforms", "Keep transforms stored in the package"),
    ("CURSOR", "Place At Cursor", "Offset the imported package to the 3D cursor"),
)

SORT_MODE_ITEMS = (
    ("NAME", "Name", "Sort alphabetically"),
    ("CATEGORY", "Category", "Sort by category then name"),
    ("MODIFIED", "Recently Modified", "Sort by source file modified time"),
    ("RECENT", "Recently Used", "Sort by the most recently placed assets"),
    ("AUTHOR", "Author", "Sort by asset author"),
)

GROUPING_MODE_ITEMS = (
    ("AUTO", "Metadata Then Folder", "Use metadata first, then folder structure"),
    ("FOLDER", "Folder", "Use folder names for categories"),
    ("ROOT", "Root", "Group by root library label"),
    ("METADATA", "Metadata Only", "Only use metadata categories"),
)

VIEW_MODE_ITEMS = (
    ("GRID", "Grid", "Thumbnail grid"),
    ("LIST", "List", "Detailed list"),
)

FILTER_ALL_ITEM = ("ALL", "All", "Show every value")
ENUM_NONE_ITEM = (ENUM_NONE_IDENTIFIER, "None", "No value")
ENUM_ADD_NEW_CATEGORY_ITEM = (
    ENUM_ADD_NEW_CATEGORY_IDENTIFIER,
    "Add New...",
    "Create a new reusable category",
)
ENUM_ADD_NEW_SUBCATEGORY_ITEM = (
    ENUM_ADD_NEW_SUBCATEGORY_IDENTIFIER,
    "Add New...",
    "Create a new reusable subcategory",
)
