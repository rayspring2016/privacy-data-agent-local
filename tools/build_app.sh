#!/usr/bin/env bash
# build_app.sh — Package privacy-data-agent for release
#
# Outputs (in release/):
#   privacy-data-agent-local-v{VERSION}.zip  ← contains privacy-data-agent-local/ folder

set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RELEASE_DIR="$PROJECT_DIR/release"

# ── Version ────────────────────────────────────────────────────────────────
VERSION=$(grep '^version' "$PROJECT_DIR/pyproject.toml" | head -1 | sed 's/.*= *"//' | sed 's/".*//')
echo "Building privacy-data-agent v$VERSION"

# ── Clean fat directories before packaging ─────────────────────────────
RELEASE_APP="$RELEASE_DIR/privacy-data-agent-local"
echo "→ Cleaning fat directories..."
rm -rf "$RELEASE_APP/.venv"                                    # dev dependencies + binary libs (~500M)
rm -rf "$RELEASE_APP/.streamlit"                               # streamlit config (not needed locally)
find "$RELEASE_APP/src" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$RELEASE_APP/src" -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
echo "   ✓ Fat dirs cleaned"

# ── Package release folder directly ─────────────────────────────────────────
echo "→ Packaging privacy-data-agent-local-v${VERSION}.zip..."
cd "$RELEASE_DIR"
zip -r "privacy-data-agent-local-v${VERSION}.zip" "privacy-data-agent-local" \
    -x "*.DS_Store" \
    -x "*.pyc" \
    -x "*.pyo" \
    -x "*__pycache__*"
cd "$PROJECT_DIR"

SIZE=$(du -sh "$RELEASE_DIR/privacy-data-agent-local-v${VERSION}.zip" | cut -f1)
echo "   ✓ release/privacy-data-agent-local-v${VERSION}.zip  ($SIZE)"
echo ""
echo "Done."