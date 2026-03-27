from __future__ import annotations

from datetime import datetime
import importlib
import json
import re
import threading
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import bpy

from . import constants

RELEASE_URL = getattr(constants, "RELEASE_URL", "https://github.com/paulc1986/File-Asset-Library/releases/tag/Release")
RELEASE_API_URL = getattr(
    constants,
    "RELEASE_API_URL",
    "https://api.github.com/repos/paulc1986/File-Asset-Library/releases/latest",
)
RELEASE_TAG_API_URL = "https://api.github.com/repos/paulc1986/File-Asset-Library/releases/tags/Release"

_VERSION_PATTERN = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")
_RESULT_LOCK = threading.Lock()
_PENDING_RESULT: dict[str, Any] | None = None
_UPDATE_THREAD: threading.Thread | None = None
_STARTUP_CHECK_REQUESTED = False
_NOTIFIED_VERSION = ""


def addon_preferences(context: bpy.types.Context):
    addon = context.preferences.addons.get(constants.ADDON_PACKAGE)
    return addon.preferences if addon else None


def local_version_tuple() -> tuple[int, int, int]:
    try:
        module = importlib.import_module(constants.ADDON_PACKAGE)
        version = module.bl_info.get("version", (1, 0, 0))
        return tuple(int(value) for value in version[:3])
    except Exception:
        return (1, 0, 0)


def local_version_text() -> str:
    return ".".join(str(value) for value in local_version_tuple())


def _parse_version(candidate: str) -> tuple[int, int, int] | None:
    if not candidate:
        return None
    match = _VERSION_PATTERN.search(candidate)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return (major, minor, patch)


def _version_text(version: tuple[int, int, int] | None) -> str:
    if version is None:
        return ""
    return ".".join(str(value) for value in version)


def _pick_release_download(payload: dict[str, Any]) -> str:
    assets = payload.get("assets") or []
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.lower().endswith(".zip"):
            return str(asset.get("browser_download_url", "")).strip()
    return str(payload.get("zipball_url", "")).strip() or str(payload.get("html_url", "")).strip()


def _request_json(url: str, local_version: tuple[int, int, int]) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"GTA000-Custom-Asset-Library/{_version_text(local_version) or '1.0.0'}",
        },
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_latest_release(local_version: tuple[int, int, int]) -> dict[str, Any]:
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        payload = _request_json(RELEASE_TAG_API_URL, local_version)
    except HTTPError as exc:
        if exc.code == 404:
            try:
                payload = _request_json(RELEASE_API_URL, local_version)
            except HTTPError as latest_exc:
                return {
                    "success": False,
                    "checked_at": checked_at,
                    "message": "",
                    "error": (
                        "No published GitHub release was found for the configured update channel."
                        if latest_exc.code == 404
                        else f"GitHub returned HTTP {latest_exc.code} while checking for updates."
                    ),
                    "release_url": RELEASE_URL,
                    "download_url": RELEASE_URL,
                    "version_text": "",
                    "release_name": "",
                    "is_newer": False,
                }
            except URLError as latest_exc:
                return {
                    "success": False,
                    "checked_at": checked_at,
                    "message": "",
                    "error": f"Could not reach GitHub: {latest_exc.reason}",
                    "release_url": RELEASE_URL,
                    "download_url": RELEASE_URL,
                    "version_text": "",
                    "release_name": "",
                    "is_newer": False,
                }
            except Exception as latest_exc:
                return {
                    "success": False,
                    "checked_at": checked_at,
                    "message": "",
                    "error": f"Update check failed: {latest_exc}",
                    "release_url": RELEASE_URL,
                    "download_url": RELEASE_URL,
                    "version_text": "",
                    "release_name": "",
                    "is_newer": False,
                }
        else:
            return {
                "success": False,
                "checked_at": checked_at,
                "message": "",
                "error": f"GitHub returned HTTP {exc.code} while checking for updates.",
                "release_url": RELEASE_URL,
                "download_url": RELEASE_URL,
                "version_text": "",
                "release_name": "",
                "is_newer": False,
            }
    except URLError as exc:
        return {
            "success": False,
            "checked_at": checked_at,
            "message": "",
            "error": f"Could not reach GitHub: {exc.reason}",
            "release_url": RELEASE_URL,
            "download_url": RELEASE_URL,
            "version_text": "",
            "release_name": "",
            "is_newer": False,
        }
    except Exception as exc:
        return {
            "success": False,
            "checked_at": checked_at,
            "message": "",
            "error": f"Update check failed: {exc}",
            "release_url": RELEASE_URL,
            "download_url": RELEASE_URL,
            "version_text": "",
            "release_name": "",
            "is_newer": False,
        }

    release_name = str(payload.get("name", "")).strip() or str(payload.get("tag_name", "")).strip() or "Release"
    version = None
    for candidate in [payload.get("tag_name", ""), payload.get("name", "")]:
        version = _parse_version(str(candidate))
        if version is not None:
            break
    if version is None:
        for asset in payload.get("assets") or []:
            version = _parse_version(str(asset.get("name", "")))
            if version is not None:
                break

    release_url = str(payload.get("html_url", "")).strip() or RELEASE_URL
    download_url = _pick_release_download(payload) or RELEASE_URL
    is_newer = bool(version and version > local_version)
    version_text = _version_text(version)

    if is_newer:
        message = f"Update available: {version_text}"
    elif version_text:
        message = f"Up to date on version {local_version_text()}."
    else:
        message = "Latest release found, but no version number was published."

    return {
        "success": True,
        "checked_at": checked_at,
        "message": message,
        "error": "",
        "release_url": release_url,
        "download_url": download_url,
        "version_text": version_text,
        "release_name": release_name,
        "is_newer": is_newer,
    }


def _worker(local_version: tuple[int, int, int], startup: bool) -> None:
    global _PENDING_RESULT, _UPDATE_THREAD
    result = _fetch_latest_release(local_version)
    result["startup"] = startup
    with _RESULT_LOCK:
        _PENDING_RESULT = result
        _UPDATE_THREAD = None


def _show_update_popup(version_text: str, release_name: str) -> None:
    def draw(self, _context):
        layout = self.layout
        layout.label(text=f"A newer build is available: {version_text}", icon="IMPORT")
        if release_name:
            layout.label(text=release_name, icon="INFO")
        layout.label(text="Open the Information panel to download the update.", icon="URL")

    try:
        bpy.context.window_manager.popup_menu(draw, title="Custom Asset Library Update", icon="INFO")
    except Exception:
        pass


def apply_pending_update_result(context: bpy.types.Context | None = None) -> bool:
    global _PENDING_RESULT, _NOTIFIED_VERSION
    with _RESULT_LOCK:
        result = _PENDING_RESULT
        _PENDING_RESULT = None

    if result is None:
        return False

    context = context or bpy.context
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None or not hasattr(window_manager, "bgal_browser"):
        return False

    browser = window_manager.bgal_browser
    browser.update_check_in_progress = False
    browser.update_available = bool(result.get("is_newer"))
    browser.update_latest_version = str(result.get("version_text", "")).strip()
    browser.update_release_name = str(result.get("release_name", "")).strip()
    browser.update_release_url = str(result.get("release_url", "")).strip() or RELEASE_URL
    browser.update_download_url = str(result.get("download_url", "")).strip() or browser.update_release_url
    browser.update_status_text = str(result.get("message", "")).strip()
    browser.update_error_text = str(result.get("error", "")).strip()
    browser.update_last_checked = str(result.get("checked_at", "")).strip()

    prefs = addon_preferences(context)
    should_notify = bool(getattr(prefs, "notify_update_available", True) if prefs else True)
    if browser.update_available and browser.update_latest_version and should_notify:
        browser.status_text = f"Update available: {browser.update_latest_version}"
        if _NOTIFIED_VERSION != browser.update_latest_version:
            _show_update_popup(browser.update_latest_version, browser.update_release_name)
            _NOTIFIED_VERSION = browser.update_latest_version
    return True


def request_update_check(context: bpy.types.Context | None = None, *, startup: bool = False, force: bool = False) -> bool:
    global _UPDATE_THREAD
    context = context or bpy.context
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None or not hasattr(window_manager, "bgal_browser"):
        return False
    if _UPDATE_THREAD is not None and _UPDATE_THREAD.is_alive() and not force:
        return False

    browser = window_manager.bgal_browser
    browser.update_check_in_progress = True
    browser.update_status_text = "Checking GitHub for updates..."
    browser.update_error_text = ""

    local_version = local_version_tuple()
    _UPDATE_THREAD = threading.Thread(
        target=_worker,
        args=(local_version, startup),
        name="BGALUpdateCheck",
        daemon=True,
    )
    _UPDATE_THREAD.start()
    return True


def _update_timer() -> float | None:
    try:
        context = bpy.context
        prefs = addon_preferences(context)
        if prefs and getattr(prefs, "check_updates_on_startup", True):
            global _STARTUP_CHECK_REQUESTED
            if not _STARTUP_CHECK_REQUESTED:
                if request_update_check(context, startup=True, force=False):
                    _STARTUP_CHECK_REQUESTED = True
        apply_pending_update_result(context)
    except Exception:
        pass

    if _UPDATE_THREAD is not None or _PENDING_RESULT is not None:
        return 1.0
    return 20.0


def ensure_update_timer(_context: bpy.types.Context | None = None) -> None:
    if not bpy.app.timers.is_registered(_update_timer):
        bpy.app.timers.register(_update_timer, first_interval=8.0, persistent=True)


def stop_update_timer() -> None:
    if bpy.app.timers.is_registered(_update_timer):
        bpy.app.timers.unregister(_update_timer)


def reset_update_state(context: bpy.types.Context | None = None) -> None:
    global _PENDING_RESULT, _STARTUP_CHECK_REQUESTED, _NOTIFIED_VERSION
    with _RESULT_LOCK:
        _PENDING_RESULT = None
    _STARTUP_CHECK_REQUESTED = False
    _NOTIFIED_VERSION = ""
    context = context or bpy.context
    window_manager = getattr(context, "window_manager", None)
    if window_manager is None or not hasattr(window_manager, "bgal_browser"):
        return
    browser = window_manager.bgal_browser
    browser.update_available = False
    browser.update_check_in_progress = False
    browser.update_latest_version = ""
    browser.update_release_name = ""
    browser.update_release_url = RELEASE_URL
    browser.update_download_url = RELEASE_URL
    browser.update_status_text = ""
    browser.update_error_text = ""
    browser.update_last_checked = ""
