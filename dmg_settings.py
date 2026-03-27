# dmg_settings.py — Talky DMG layout for dmgbuild
#
# Usage (from repo root, after dist/Talky.app is staged):
#   dmgbuild -s dmg_settings.py \
#     -D stage=/path/to/dmg_stage \
#     -D project_dir=/path/to/talky \
#     "Talky Installer" \
#     release/Talky-x.y-unsigned.dmg
#
# `defines` is injected by dmgbuild from -D key=value (see dmgbuild docs).
#
# Retina note: Finder treats a single PNG’s pixel size as the @2x bitmap for a
# *half-sized* logical window. If window_rect uses the same numbers as the PNG
# pixels (e.g. 1200×800), the art only covers ~¼ of the window on Retina.
# Fix: either ship dmg_bg@2x.png (dmgbuild merges a multi-TIFF) and keep a
# full-size window, or use half the pixel size for window + icon coords when
# only dmg_bg.png exists.

from __future__ import annotations

from pathlib import Path

# `defines` is injected by dmgbuild (-D stage=... -D project_dir=...).
_stage = Path(str(defines["stage"])).resolve()  # noqa: F821
_project = Path(str(defines["project_dir"])).resolve()  # noqa: F821

_APP = _stage / "Talky.app"
if not _APP.is_dir():
    raise FileNotFoundError(f"Staged app not found: {_APP}")

appname = "Talky.app"

# --- Volume output ---
format = "UDZO"
filesystem = "HFS+"

# End-user DMG: only the app + Applications link (no BUILD.txt in the volume root).
files: list[str | tuple[str, str]] = [str(_APP)]

symlinks = {"Applications": "/Applications"}

# --- Background + window (points) ---
_bg_path = _project / "assets" / "dmg_bg.png"
if not _bg_path.is_file():
    raise FileNotFoundError(f"DMG background not found: {_bg_path}")

# Pixel size of dmg_bg.png (design canvas).
_BG_W, _BG_H = 1200, 800

# Optional HiDPI pair (same basename as dmgbuild: name@2x.ext next to name.ext).
_bg_2x = _bg_path.with_name(f"{_bg_path.stem}@2x{_bg_path.suffix}")

if _bg_2x.is_file():
    # dmgbuild will build a multi-resolution TIFF; window matches the 1× layer in points.
    _win_w, _win_h = _BG_W, _BG_H
    _s = 1.0
else:
    # Single PNG: window in points = half of pixel size so the bitmap fills the view on Retina.
    _win_w, _win_h = _BG_W // 2, _BG_H // 2
    _s = 0.5

# WindowBounds include the title bar; the icon-view background is drawn in the content rect below
# it. Matching (w,h) to the PNG 1:1 clips the bottom of the art — add vertical slack for chrome.
_FINDER_FRAME_EXTRA_H = 40

# window_rect: ((x, y), (width, height)); y is bottom-based in screen coords (dmgbuild docs).
window_rect = ((100, 120), (_win_w, _win_h + _FINDER_FRAME_EXTRA_H))
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
default_view = "icon-view"
show_icon_preview = False

background = str(_bg_path)

# --- Icon view ---
icon_size = 128
arrange_by = None
grid_offset = (0, 0)
grid_spacing = 100
scroll_position = (0, 0)
label_pos = "bottom"
text_size = 16

# Icon Iloc y is from the *top* of the window content (larger y = lower on screen), unlike
# window_rect’s bottom-based y. Design coords use the 1200×800 artboard; _scale_pt maps to points.


def _scale_pt(x: float, y: float) -> tuple[int, int]:
    return (int(round(x * _s)), int(round(y * _s)))


icon_locations = {
    appname: _scale_pt(320, 400),
    "Applications": _scale_pt(920, 400),
}

include_icon_view_settings = True

# --- Volume icon (installer branding) ---
_installer_icns = _project / "assets" / "installer.icns"
_installer_png = _project / "assets" / "talky_installer.png"
if _installer_icns.is_file():
    icon = str(_installer_icns)
elif _installer_png.is_file():
    icon = str(_installer_png)
