#!/bin/bash
# SelfAgent — One-command setup
set -e

echo "==================================="
echo "  SelfAgent Setup"
echo "==================================="
echo ""

# Check Python 3.10+
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo "Error: Python 3.10+ required. Found Python $PY_VERSION."
    exit 1
fi

echo "[1/4] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[2/4] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "[3/4] Installing Playwright browser (chromium)..."
playwright install chromium

echo "[4/4] Setting up configuration..."
if [ ! -f config.yaml ]; then
    cp config.example.yaml config.yaml
    echo "  -> Created config.yaml from config.example.yaml"
    echo "  -> Edit config.yaml and add your API key."
else
    echo "  -> config.yaml already exists, skipping."
fi

mkdir -p storage

echo ""
echo "==================================="
echo "  Setup complete!"
echo "  1. Edit config.yaml with your API key"
echo "  2. Run: ./run.sh"
echo "==================================="
