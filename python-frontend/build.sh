#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== ZennoCall Build ==="

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
    echo "ERROR: $PYTHON not found. Install Python 3.10+."
    exit 1
fi

# Install deps if needed
if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "Installing build dependencies..."
    "$PYTHON" -m pip install -e ".[dev]"
fi

# Verify resources
if [ ! -f meetily/resources/icon.png ]; then
    echo "WARNING: meetily/resources/icon.png not found — app will have no icon."
fi

# Clean previous build
rm -rf build/ dist/

echo "Running PyInstaller..."
"$PYTHON" -m PyInstaller meetily.spec --noconfirm

echo ""
echo "=== Build Complete ==="
if [ "$(uname)" = "Darwin" ]; then
    echo "Output: dist/ZennoCall.app"
    echo "Run:    open dist/ZennoCall.app"
else
    echo "Output: dist/ZennoCall/"
    echo "Run:    ./dist/ZennoCall/ZennoCall"
fi
