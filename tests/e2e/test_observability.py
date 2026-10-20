"""E2E tests for observability stack (Prometheus, Alertmanager, Grafana).

Requires a running Tilt cluster with observability charts deployed.
Run with: E2E_TESTS=true ./scripts/run-tests.sh"""

import requests

import pytest


class TestPrometheus:
    """Test Prometheus metrics scraping."""

    @pytest.mark.e2e
    def test_prometheus_healthy(self, api_client):
        """Verify Prometheus is reachable at port 9090."""
        resp = requests.get("http://127.0.0.1:9090/-/healthy", timeout=5)
        assert resp.status_code == 200


class TestAlertmanager:
    """Test Alertmanager configuration."""

    @pytest.mark.e2e
    def test_alertmanager_configured(self, api_client):
        """Verify Alertmanager SMTP config."""
        resp = requests.get("http://127.0.0.1:9093/api/v2/status", timeout=5)
        assert resp.status_code == 200

        status_data = resp.json()
        config_yaml = status_data.get("config", {}).get("original", "")
        assert "smtp.mailtrap.io:2525" in config_yaml
        assert "alertmanager@agentic.local" in config_yaml


class TestGrafana:
    """Test Grafana dashboard provisioning."""

    @pytest.mark.e2e
    def test_grafana_dashboard(self, api_client):
        """Verify Grafana dashboard is provisioned."""
        auth = ("admin", "admin")
        resp = requests.get(
            "http://127.0.0.1:3001/api/dashboards/uid/agent-dashboard",
            auth=auth,
            timeout=5,
        )
        assert resp.status_code == 200

        dash_data = resp.json()
        assert dash_data["dashboard"]["title"] == "Agent Stack Dashboard"
