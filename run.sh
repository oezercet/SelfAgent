#!/bin/bash
# SelfAgent — Start the server
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

echo "==================================="
echo "  SelfAgent is running"
echo "  http://localhost:8765"
echo "==================================="
echo ""

python -m chat.server
