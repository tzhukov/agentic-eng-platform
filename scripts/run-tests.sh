#!/usr/bin/env bash
# Run the full test suite (unit + integration + optional E2E).
#
# Usage:
#   ./scripts/run-tests.sh          # Run unit + integration only
#   E2E_TESTS=true ./scripts/run-tests.sh  # Include E2E tests (requires running cluster)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Use poetry if available, fall back to venv
if command -v poetry &>/dev/null && [ -f "$PROJECT_DIR/pyproject.toml" ]; then
    echo "=== Using Poetry environment ==="
    cd "$PROJECT_DIR"
    PYTHONPATH="$PROJECT_DIR" poetry run pytest "$@"
else
    echo "=== Using venv environment ==="
    source "$PROJECT_DIR/venv/bin/activate"
    export PYTHONPATH="$PYTHONPATH:$PROJECT_DIR"
    pytest "$@"
fi
