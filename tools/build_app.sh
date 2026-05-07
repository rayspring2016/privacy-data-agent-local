#!/usr/bin/env bash
# build_app.sh — Build Mac .app bundle and Windows zip for privacy-data-agent
#
# Outputs (in release/):
#   privacy-data-agent-v{VERSION}-mac.zip     ← contains 数据脱敏工具.app
#   privacy-data-agent-v{VERSION}-windows.zip ← contains privacy-data-agent-local/ folder

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RELEASE_SRC="$PROJECT_DIR/release/privacy-data-agent-local"
BUILD_DIR="$PROJECT_DIR/build"

# ── Version ────────────────────────────────────────────────────────────────
VERSION=$(grep '^version' "$PROJECT_DIR/pyproject.toml" | head -1 | sed 's/.*= *"//' | sed 's/".*//')
echo "Building privacy-data-agent v$VERSION"

# ── Clean build dir ────────────────────────────────────────────────────────
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/mac" "$BUILD_DIR/windows"

APP_NAME="数据脱敏工具"

# ════════════════════════════════════════════════════════════════════════════
# MAC: .app bundle
# ════════════════════════════════════════════════════════════════════════════
APP_DIR="$BUILD_DIR/mac/$APP_NAME.app"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources/app"

echo "→ Copying app content into .app bundle..."
rsync -a \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='runs/' \
  --exclude='*.egg-info' \
  "$RELEASE_SRC/" "$APP_DIR/Contents/Resources/app/"

echo "→ Writing Info.plist..."
cat > "$APP_DIR/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.privacy-data-agent.local</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Privacy Data Agent ${VERSION} — Local use only</string>
</dict>
</plist>
PLIST

echo "→ Writing launcher script..."
LAUNCHER="$APP_DIR/Contents/MacOS/$APP_NAME"
cat > "$LAUNCHER" << 'LAUNCHER_SCRIPT'
#!/bin/zsh
# Privacy Data Agent — macOS launcher
# Runs inside the .app bundle; no terminal window is shown.

APP_RESOURCES="$(dirname "$0")/../Resources/app"
cd "$APP_RESOURCES" || exit 1

LOG="/tmp/privacy-data-agent.log"
PORT=8501

# ── First-run: create venv if missing ──────────────────────────────────────
if [ ! -f ".venv/bin/python" ]; then
  # Show a progress dialog while installing (background)
  osascript -e 'display notification "首次启动正在安装运行环境，约需 1 分钟，请稍候..." with title "数据脱敏工具"' 2>/dev/null || true

  if ! command -v python3 &>/dev/null; then
    osascript -e 'display dialog "未找到 Python 3。\n\n请先安装 Python 3.11 或以上版本：\nhttps://www.python.org/downloads/" with title "数据脱敏工具" buttons {"确定"} default button "确定" with icon stop' 2>/dev/null || true
    exit 1
  fi

  python3 -m venv .venv >> "$LOG" 2>&1
  .venv/bin/pip install -e . --quiet --no-warn-script-location >> "$LOG" 2>&1
fi

# ── Kill any stale streamlit on this port ──────────────────────────────────
lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true

# ── Launch streamlit in background ────────────────────────────────────────
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_CLIENT_TOOLBAR_MODE=viewer

.venv/bin/python -m streamlit run src/privacy_data_agent/web_app.py \
  --server.address 127.0.0.1 \
  --server.port "$PORT" \
  --browser.gatherUsageStats false \
  --client.toolbarMode viewer \
  --server.headless true \
  >> "$LOG" 2>&1 &

STREAMLIT_PID=$!

# ── Wait for startup, then open browser ───────────────────────────────────
sleep 5
open "http://127.0.0.1:${PORT}"

# ── Keep app alive until streamlit exits ──────────────────────────────────
wait "$STREAMLIT_PID"
LAUNCHER_SCRIPT

chmod +x "$LAUNCHER"

echo "→ Packaging Mac zip..."
cd "$BUILD_DIR/mac"
zip -r --symlinks "$PROJECT_DIR/release/privacy-data-agent-v${VERSION}-mac.zip" "$APP_NAME.app" -x "*.DS_Store"
cd "$PROJECT_DIR"

MAC_SIZE=$(du -sh "$PROJECT_DIR/release/privacy-data-agent-v${VERSION}-mac.zip" | cut -f1)
echo "   ✓ release/privacy-data-agent-v${VERSION}-mac.zip  ($MAC_SIZE)"

# ════════════════════════════════════════════════════════════════════════════
# WINDOWS: folder + VBScript launcher
# ════════════════════════════════════════════════════════════════════════════
WIN_APP_DIR="$BUILD_DIR/windows/privacy-data-agent-local"
mkdir -p "$WIN_APP_DIR"

echo "→ Copying app content for Windows..."
rsync -a \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='runs/' \
  --exclude='*.egg-info' \
  "$RELEASE_SRC/" "$WIN_APP_DIR/"

echo "→ Writing Windows VBScript launcher..."
cat > "$WIN_APP_DIR/${APP_NAME}.vbs" << 'VBS_SCRIPT'
' 数据脱敏工具.vbs — Silent launcher for Privacy Data Agent
' Double-click this file to start the web UI without any console window.
'
' First time: run windows\00-install-windows.bat to set up the environment.

Dim WshShell, fso, strDir, strBat
Set fso      = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

strDir = fso.GetParentFolderName(WScript.ScriptFullName)
strBat = strDir & "\windows\03-launch-web-ui-windows.bat"

If Not fso.FileExists(strBat) Then
    MsgBox "启动脚本未找到：" & vbCrLf & strBat, vbCritical, "数据脱敏工具"
    WScript.Quit 1
End If

' Run with hidden window (0), async (False)
WshShell.Run Chr(34) & strBat & Chr(34), 0, False

Set WshShell = Nothing
Set fso      = Nothing
VBS_SCRIPT

echo "→ Packaging Windows zip..."
cd "$BUILD_DIR/windows"
zip -r "$PROJECT_DIR/release/privacy-data-agent-v${VERSION}-windows.zip" "privacy-data-agent-local" -x "*.DS_Store"
cd "$PROJECT_DIR"

WIN_SIZE=$(du -sh "$PROJECT_DIR/release/privacy-data-agent-v${VERSION}-windows.zip" | cut -f1)
echo "   ✓ release/privacy-data-agent-v${VERSION}-windows.zip  ($WIN_SIZE)"

# ── Sync VBScript back to source tree ─────────────────────────────────────
cp "$WIN_APP_DIR/${APP_NAME}.vbs" "$PROJECT_DIR/windows/${APP_NAME}.vbs"
# Also put it at release root so it's available in the existing release dir
cp "$WIN_APP_DIR/${APP_NAME}.vbs" "$RELEASE_SRC/${APP_NAME}.vbs"
echo "   ✓ Synced ${APP_NAME}.vbs → windows/ and release/privacy-data-agent-local/"

echo ""
echo "Done. Output files:"
ls -lh "$PROJECT_DIR/release/privacy-data-agent-v${VERSION}-mac.zip" \
        "$PROJECT_DIR/release/privacy-data-agent-v${VERSION}-windows.zip"
