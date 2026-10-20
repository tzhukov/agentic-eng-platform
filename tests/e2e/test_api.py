"""E2E tests for the API endpoints (requires running Tilt cluster).

Tests hit the live API at http://127.0.0.1:8000.
Run with: E2E_TESTS=true ./scripts/run-tests.sh"""

import requests

import pytest


class TestHealthEndpoint:
    """Test the /healthz endpoint."""

    @pytest.mark.e2e
    def test_health_endpoint(self, api_client):
        response = api_client.get("http://127.0.0.1:8000/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestQueryEndpoint:
    """Test the /query endpoint."""

    @pytest.mark.e2e
    def test_query_endpoint(self, api_client, query_endpoint):
        payload = {"query": "How do I become an AI engineer?"}
        response = api_client.post(query_endpoint, json=payload, timeout=60)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"] == "Success"
        assert len(data["stdout"]) > 0
