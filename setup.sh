#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== Web Search Agent Setup ==="

# 1. Create venv
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/3] Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/3] Virtual environment already exists."
fi

# 2. Install dependencies
echo "[2/3] Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

# 3. Install Playwright Chromium
echo "[3/3] Installing Playwright Chromium browser..."
"$VENV_DIR/bin/playwright" install chromium

echo ""
echo "=== Setup Complete ==="
echo "To use search.py:"
echo "  $VENV_DIR/bin/python3 $SCRIPT_DIR/search.py --list-platforms"
echo ""
echo "Or activate the venv first:"
echo "  source $VENV_DIR/bin/activate"
echo "  python3 search.py --list-platforms"
