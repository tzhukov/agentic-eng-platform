#!/bin/bash
set -e

# Activate virtual environment
source venv/bin/activate
export PYTHONPATH=$PYTHONPATH:.

# Run Unit Tests
echo "--- Running Unit Tests ---"
pytest tests/test_graph.py

# Run Integration Tests
echo "--- Running Integration Tests ---"
export QDRANT_HOST="172.18.255.200"
pytest tests/test_integration.py

# Run E2E Cluster Tests
echo "--- Running E2E Cluster Tests ---"
# Assumes Tilt is running and port-forwarding 8000
pytest tests/e2e/test_api.py
pytest tests/e2e/test_observability.py

echo "--- All tests passed! ---"
