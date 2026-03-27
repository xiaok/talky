#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

APP_NAME="Talky"
APP_BUNDLE_ID="com.talky.app"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"
DMG_DIR="$PROJECT_DIR/release"
STAGE_DIR="$BUILD_DIR/dmg_stage"
ICON_PATH="$PROJECT_DIR/assets/app.icns"
ENTITLEMENTS_PATH="$BUILD_DIR/entitlements.plist"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  VERSION="$(date +%Y.%m.%d)-$(git rev-parse --short HEAD 2>/dev/null || echo dev)"
fi

# Unique per packaging run (same VERSION can be rebuilt many times).

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required."
  exit 1
fi

# Avoid tr|head under pipefail: tr gets SIGPIPE (exit 141) and the script would exit before any echo.
BUILD_ID="$(python3 -c "import secrets,string as s; a=s.ascii_letters+s.digits; print(''.join(secrets.choice(a) for _ in range(6)), end='')")"
if [[ -n "${TALKY_BUILD_ID_OVERRIDE:-}" ]]; then
  BUILD_ID="${TALKY_BUILD_ID_OVERRIDE}"
fi

DMG_NAME="${APP_NAME}-${VERSION}-unsigned.dmg"
DMG_PATH="$DMG_DIR/$DMG_NAME"
TMP_DMG_PATH="$BUILD_DIR/${APP_NAME}-tmp.dmg"
# Set TALKY_DMG_FANCY=1 for legacy path (UDRW + AppleScript + convert) — rarely needed now that dmgbuild exists.
# Default: if repo-root dmg_settings.py exists, run dmgbuild (Finder background + icon layout), then UDZO.
# Set TALKY_DMG_SIMPLE=1 to skip dmgbuild and use plain hdiutil create -srcfolder <dmg_stage> -format UDZO.
# By default, dmg_stage is copied to /tmp/.../dmg_stage (ASCII); set TALKY_DMG_SKIP_TMP_HDIUTIL=1 for in-repo path.
# Set TALKY_HDIUTIL_VERBOSE=1 for hdiutil -verbose.
# Set TALKY_BUILD_ID_OVERRIDE=... to replace the default build_id (6 chars A–Z a–z 0–9).

echo "==> Building unsigned DMG for ${APP_NAME}"
echo "==> Version: ${VERSION}"
echo "==> Build ID: ${BUILD_ID} (embedded in app Info.plist; override: TALKY_BUILD_ID_OVERRIDE)"

if [[ ! -d ".venv" ]]; then
  echo "==> Creating virtual environment..."
  python3 -m venv .venv
fi
source ".venv/bin/activate"

echo "==> Installing runtime dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null

if ! python -m pip show pyinstaller >/dev/null 2>&1; then
  echo "==> Installing pyinstaller..."
  python -m pip install pyinstaller >/dev/null
fi

if [[ "${TALKY_DMG_SIMPLE:-}" != "1" ]] && [[ -f "$PROJECT_DIR/dmg_settings.py" ]] && [[ "${TALKY_DMG_FANCY:-}" != "1" ]]; then
  if ! python -m pip show dmgbuild >/dev/null 2>&1; then
    echo "==> Installing dmgbuild (DMG layout)..."
    python -m pip install dmgbuild >/dev/null
  fi
fi

echo "==> Cleaning old artifacts..."
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$DMG_DIR" "$STAGE_DIR"
export PYINSTALLER_CONFIG_DIR="$BUILD_DIR/pyinstaller-cache"

# Bundle local Whisper runtime deps so DMG users can speak immediately after setup.
EXTRA_PYI_ARGS=()
TRAY_ICON_DIR="$PROJECT_DIR/assets"
if [[ -f "$TRAY_ICON_DIR/tray_icon.png" ]]; then
  EXTRA_PYI_ARGS+=(--add-data "$TRAY_ICON_DIR/tray_icon.png:assets")
  EXTRA_PYI_ARGS+=(--add-data "$TRAY_ICON_DIR/tray_icon@2x.png:assets")
fi
if [[ -f "$TRAY_ICON_DIR/talky-logo.png" ]]; then
  EXTRA_PYI_ARGS+=(--add-data "$TRAY_ICON_DIR/talky-logo.png:assets")
fi

RUNTIME_HOOK="$PROJECT_DIR/scripts/pyinstaller_hooks/runtime_hook_stubs.py"
VERSION_FILE="$PROJECT_DIR/talky/version_checker.py"

echo "==> Stamping build version into $VERSION_FILE..."
sed -i '' "s/^CURRENT_VERSION = .*/CURRENT_VERSION = \"${APP_NAME}-${VERSION}-unsigned\"/" "$VERSION_FILE"
sed -i '' "s/^CURRENT_BUILD_ID = .*/CURRENT_BUILD_ID = \"${BUILD_ID}\"/" "$VERSION_FILE"

echo "==> Building ${APP_NAME}.app with PyInstaller..."
python -m PyInstaller \
  --noconfirm \
  --windowed \
  --specpath "$BUILD_DIR" \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --hidden-import "AVFoundation" \
  --hidden-import "AppKit" \
  --hidden-import "talky.macos_ui" \
  --hidden-import "huggingface_hub" \
  --hidden-import "numpy" \
  --exclude-module mlx \
  --exclude-module mlx_whisper \
  --exclude-module torch \
  --exclude-module llvmlite \
  --exclude-module scipy \
  --exclude-module numba \
  --runtime-hook "$RUNTIME_HOOK" \
  "${EXTRA_PYI_ARGS[@]}" \
  main.py

if [[ ! -d "$DIST_DIR/${APP_NAME}.app" ]]; then
  echo "Error: expected app bundle not found at $DIST_DIR/${APP_NAME}.app"
  exit 1
fi

echo "==> Self-check packaged runtime imports (numpy/mlx/mlx_whisper)..."
if ! TALKY_SELF_CHECK_IMPORTS=1 "$DIST_DIR/${APP_NAME}.app/Contents/MacOS/${APP_NAME}"; then
  echo "Error: packaged import self-check failed."
  echo "Fix PyInstaller hidden imports/excludes before creating DMG."
  exit 1
fi

APP_PLIST="$DIST_DIR/${APP_NAME}.app/Contents/Info.plist"
if [[ -f "$APP_PLIST" ]]; then
  echo "==> Injecting macOS privacy usage descriptions..."
  /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $APP_BUNDLE_ID" "$APP_PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string $APP_BUNDLE_ID" "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$APP_PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :NSMicrophoneUsageDescription Talky needs microphone access for hold-to-talk recording." "$APP_PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :NSMicrophoneUsageDescription string Talky needs microphone access for hold-to-talk recording." "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :NSInputMonitoringUsageDescription Talky needs input monitoring to listen for global hotkeys." "$APP_PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :NSInputMonitoringUsageDescription string Talky needs input monitoring to listen for global hotkeys." "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :NSSupportsAutomaticTermination false" "$APP_PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :NSSupportsAutomaticTermination bool false" "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :NSSupportsSuddenTermination false" "$APP_PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :NSSupportsSuddenTermination bool false" "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :TalkyBuildId $BUILD_ID" "$APP_PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Add :TalkyBuildId string $BUILD_ID" "$APP_PLIST"
fi

echo "==> Creating entitlements for audio-input access..."
mkdir -p "$(dirname "$ENTITLEMENTS_PATH")"
cat > "$ENTITLEMENTS_PATH" <<'ENTEOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.device.audio-input</key>
    <true/>
</dict>
</plist>
ENTEOF

echo "==> Re-signing app bundle (ad-hoc) with entitlements..."
codesign --force --deep --sign - \
  --identifier "$APP_BUNDLE_ID" \
  --entitlements "$ENTITLEMENTS_PATH" \
  "$DIST_DIR/${APP_NAME}.app"

echo "==> Verifying code signature..."
codesign --verify --verbose=2 "$DIST_DIR/${APP_NAME}.app"
SIGNED_ID=$(codesign -dvvv "$DIST_DIR/${APP_NAME}.app" 2>&1 | grep '^Identifier=' | cut -d= -f2)
echo "    Identifier: $SIGNED_ID"
if [[ "$SIGNED_ID" != "$APP_BUNDLE_ID" ]]; then
  echo "Error: signed identifier '$SIGNED_ID' does not match expected '$APP_BUNDLE_ID'"
  exit 1
fi

echo "==> Preparing DMG stage..."
cp -R "$DIST_DIR/${APP_NAME}.app" "$STAGE_DIR/"
ln -sfn "/Applications" "$STAGE_DIR/Applications"
# Build metadata lives in Info.plist (TalkyBuildId) only — no BUILD.txt in the DMG.

DMG_BG="$PROJECT_DIR/assets/dmg_bg.png"
DMG_BG_RETINA="$PROJECT_DIR/assets/dmg_bg@2x.png"
# Default compressed DMG volume label (matches user-facing one-liner).
DMG_VOLNAME="Talky"
# Fancy layout path uses a distinct volume name for Finder / mount point.
FANCY_VOLNAME="$APP_NAME Installer"

SRCFOLDER="$STAGE_DIR"
HDIUTIL_WORK=""
DMG_TMP_OUT="$DMG_PATH"
FANCY_RW_DMG="$TMP_DMG_PATH"

if [[ "${TALKY_DMG_SKIP_TMP_HDIUTIL:-}" != "1" ]]; then
  HDIUTIL_WORK="$(mktemp -d /tmp/talky-hdiutil.XXXXXX)"
  trap '[[ -n "${HDIUTIL_WORK:-}" ]] && rm -rf "${HDIUTIL_WORK}"' EXIT
  echo "==> Copying build/dmg_stage -> ${HDIUTIL_WORK}/dmg_stage (ASCII path for hdiutil)..."
  ditto "$STAGE_DIR" "${HDIUTIL_WORK}/dmg_stage"
  touch "${HDIUTIL_WORK}/dmg_stage/.metadata_never_index" 2>/dev/null || true
  SRCFOLDER="${HDIUTIL_WORK}/dmg_stage"
  DMG_TMP_OUT="${HDIUTIL_WORK}/Talky-out.dmg"
  FANCY_RW_DMG="${HDIUTIL_WORK}/${APP_NAME}-rw.dmg"
fi

HDIUTIL_V=()
if [[ "${TALKY_HDIUTIL_VERBOSE:-}" == "1" ]]; then
  HDIUTIL_V=(-verbose)
fi

# Single-step DMG: hdiutil create -srcfolder <dmg_stage> -format UDZO
# Fallback: UDRO from same folder + convert to UDZO (still no blank-image attach/ditto path).
hdiutil_udzo_srcfolder() {
  local out="$1"
  local src="$2"
  rm -f "$out"
  echo "==> hdiutil create -volname \"${DMG_VOLNAME}\" -srcfolder \"${src}\" -ov -format UDZO ..." >&2
  if hdiutil create "${HDIUTIL_V[@]}" \
    -volname "$DMG_VOLNAME" \
    -srcfolder "$src" \
    -ov \
    -format UDZO \
    "$out"; then
    return 0
  fi
  echo "==> WARN: UDZO -srcfolder failed; trying UDRO + convert ..." >&2
  local udro="${HDIUTIL_WORK:-$BUILD_DIR}/${APP_NAME}-udro-tmp.dmg"
  rm -f "$udro"
  if hdiutil create "${HDIUTIL_V[@]}" \
    -volname "$DMG_VOLNAME" \
    -srcfolder "$src" \
    -ov \
    -format UDRO \
    "$udro"; then
    rm -f "$out"
    if hdiutil convert "${HDIUTIL_V[@]}" \
      "$udro" \
      -format UDZO \
      -o "$out"; then
      rm -f "$udro"
      return 0
    fi
  fi
  rm -f "$udro" "$out"
  return 1
}

echo "==> Creating DMG..."
rm -f "$TMP_DMG_PATH" "$DMG_PATH"
[[ -n "$HDIUTIL_WORK" ]] && rm -f "$DMG_TMP_OUT" "$FANCY_RW_DMG"

if [[ "${TALKY_DMG_FANCY:-}" == "1" ]]; then
  echo "==> Fancy DMG (RW image + Finder layout; may be slow)..."
  hdiutil create "${HDIUTIL_V[@]}" \
    -volname "$FANCY_VOLNAME" \
    -srcfolder "$SRCFOLDER" \
    -ov \
    -format UDRW \
    -fs HFS+ \
    -size 300m \
    "$FANCY_RW_DMG" >/dev/null

  MOUNT_POINT="/Volumes/$FANCY_VOLNAME"
  hdiutil attach "$FANCY_RW_DMG" -mountpoint "$MOUNT_POINT" -nobrowse -quiet

  if [[ -f "$DMG_BG_RETINA" ]]; then
    DMG_BG_SRC="$DMG_BG_RETINA"
  elif [[ -f "$DMG_BG" ]]; then
    DMG_BG_SRC="$DMG_BG"
  else
    DMG_BG_SRC=""
  fi

  if [[ -n "$DMG_BG_SRC" ]]; then
    echo "==> Installing DMG background image..."
    mkdir -p "$MOUNT_POINT/.background"
    cp "$DMG_BG_SRC" "$MOUNT_POINT/.background/background.png"

    echo "==> Applying DMG window layout via AppleScript..."
    osascript <<APPLESCRIPT
tell application "Finder"
  tell disk "$FANCY_VOLNAME"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {100, 100, 700, 500}
    set theViewOptions to the icon view options of container window
    set arrangement of theViewOptions to not arranged
    set icon size of theViewOptions to 128
    set background picture of theViewOptions to file ".background:background.png"
    set position of item "${APP_NAME}.app" of container window to {150, 200}
    set position of item "Applications" of container window to {450, 200}
    close
    open
    update without registering applications
    delay 1
    close
  end tell
end tell
APPLESCRIPT
  else
    echo "==> No DMG background image; skipping layout customization."
  fi

  INSTALLER_ICON="$PROJECT_DIR/assets/installer.icns"
  if [[ -f "$INSTALLER_ICON" ]]; then
    echo "==> Setting custom volume icon..."
    cp "$INSTALLER_ICON" "$MOUNT_POINT/.VolumeIcon.icns"
    SetFile -a C "$MOUNT_POINT"
  elif [[ -f "$ICON_PATH" ]]; then
    echo "==> Setting app icon as volume icon (fallback)..."
    cp "$ICON_PATH" "$MOUNT_POINT/.VolumeIcon.icns"
    SetFile -a C "$MOUNT_POINT"
  fi

  sync
  hdiutil detach "$MOUNT_POINT" -quiet

  rm -f "$DMG_TMP_OUT"
  hdiutil convert "${HDIUTIL_V[@]}" \
    "$FANCY_RW_DMG" \
    -format UDZO \
    -o "$DMG_TMP_OUT" >/dev/null

  rm -f "$FANCY_RW_DMG"
elif [[ "${TALKY_DMG_SIMPLE:-}" != "1" ]] && [[ -f "$PROJECT_DIR/dmg_settings.py" ]]; then
  echo "==> Building compressed .dmg with dmgbuild (dmg_settings.py + Talky Installer volume)..."
  if dmgbuild -s "$PROJECT_DIR/dmg_settings.py" \
    -Dstage="${SRCFOLDER}" \
    -Dproject_dir="${PROJECT_DIR}" \
    "$FANCY_VOLNAME" \
    "$DMG_TMP_OUT"; then
    :
  else
    echo "==> WARN: dmgbuild failed; falling back to plain hdiutil -srcfolder UDZO ..." >&2
    hdiutil_udzo_srcfolder "$DMG_TMP_OUT" "$SRCFOLDER"
  fi
else
  echo "==> Building compressed .dmg (UDZO; single-step -srcfolder from dmg_stage)..."
  hdiutil_udzo_srcfolder "$DMG_TMP_OUT" "$SRCFOLDER"
fi

if [[ "$DMG_TMP_OUT" != "$DMG_PATH" ]]; then
  mkdir -p "$DMG_DIR"
  mv -f "$DMG_TMP_OUT" "$DMG_PATH"
fi
# EXIT trap removes ${HDIUTIL_WORK} (stage copy under /tmp) when used

echo "==> Done"
echo "DMG: $DMG_PATH"
echo "Build ID: $BUILD_ID  (app Info.plist: TalkyBuildId)"
echo "Note: this DMG is unsigned and not notarized."
