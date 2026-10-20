#!/usr/bin/env bash
# One-command environment bootstrap for the agentic-eng-platform.
# Usage: ./scripts/dev-setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Agentic Eng Platform — Dev Setup ==="

# 1. Install Poetry if missing
if ! command -v poetry &>/dev/null; then
    echo "[1/4] Installing Poetry via install script..."
    curl -sSL https://install.python-poetry.org | python3 -
    # Add to PATH (poetry installer usually does this, but be explicit)
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[1/4] Poetry already installed: $(poetry --version)"
fi

# 2. Install dependencies
cd "$PROJECT_DIR"
echo "[2/4] Installing dependencies via Poetry..."
poetry install

# 3. Verify Python version
echo "[3/4] Verifying Python version..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "  Python: $PYTHON_VERSION"
if command -v python &>/dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo "  python (alias): $PYTHON_VERSION"
fi

# 4. Verify key components
echo "[4/4] Verifying key components..."
PYTHONPATH="$PROJECT_DIR" poetry run python -c "
import fastapi; print(f'  FastAPI: {fastapi.__version__}')
import litellm; print(f'  LiteLLM: {litellm.__version__}')
import langgraph; print(f'  LangGraph: {langgraph.__version__}')
import qdrant_client; print(f'  Qdrant client: {qdrant_client.__version__}')
import pytest; print(f'  Pytest: {pytest.__version__}')
" || echo "  ⚠ Some packages failed to import (check requirements)"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and fill in your API keys"
echo "  2. Run ./scripts/setup-cluster.sh to provision Kind + MetalLB"
echo "  3. Run tilt up to start the full stack"
echo "  4. Run pytest to verify everything works"
echo ""
echo "Active Poetry env: $(poetry env info --path 2>/dev/null || echo 'not active')"
