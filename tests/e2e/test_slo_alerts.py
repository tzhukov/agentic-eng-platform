"""E2E tests: SLO/SLI & Error Budget Alerting Rules.

Validates that Prometheus alerting rules and recording rules are loaded.
Requires a running Tilt cluster with observability charts deployed.
Run with: E2E_TESTS=true ./scripts/run-tests.sh"""

import requests

import pytest

PROMETHEUS_URL = "http://127.0.0.1:9090"

# All alerting rules that must be present in Prometheus
EXPECTED_ALERT_RULES = [
    "HighErrorRate",
    "CriticalErrorRate",
    "QueryLatencyBreach",
    "HealthCheckLatencyBreach",
    "SloErrorBudgetFastBurn",
    "SloErrorBudgetSlowBurn",
    "AgentApiDown",
    "LLMCostBudgetBurn",
]

# All recording rules that must be present
EXPECTED_RECORDING_RULES = [
    "job:http_requests_error_ratio:rate5m",
    "job:http_requests_error_ratio:rate1h",
    "job:http_requests_error_ratio:rate6h",
    "job:http_requests_error_ratio:rate30m",
    "job:http_request_duration_p95:query:rate5m",
]


class TestPrometheusRules:
    """Test Prometheus alerting and recording rules."""

    @pytest.mark.e2e
    def test_prometheus_rules_endpoint(self, api_client):
        """Prometheus rules API is accessible."""
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/rules", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "data" in data
        assert "groups" in data["data"]

    @pytest.mark.e2e
    def test_all_alert_rules_loaded(self, api_client):
        """All SLO alerting rules are loaded into Prometheus."""
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/rules", timeout=10)
        data = resp.json()
        groups = data["data"]["groups"]

        loaded_alert_names = set()
        for group in groups:
            for rule in group.get("rules", []):
                if rule.get("type") == "alerting":
                    loaded_alert_names.add(rule["name"])

        missing = [r for r in EXPECTED_ALERT_RULES if r not in loaded_alert_names]
        assert not missing, f"Missing alerting rules: {missing}\nLoaded: {sorted(loaded_alert_names)}"

    @pytest.mark.e2e
    def test_all_recording_rules_loaded(self, api_client):
        """All SLO recording rules are loaded into Prometheus."""
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/rules", timeout=10)
        data = resp.json()
        groups = data["data"]["groups"]

        loaded_recording_names = set()
        for group in groups:
            for rule in group.get("rules", []):
                if rule.get("type") == "recording":
                    loaded_recording_names.add(rule["name"])

        missing = [r for r in EXPECTED_RECORDING_RULES if r not in loaded_recording_names]
        assert not missing, f"Missing recording rules: {missing}\nLoaded: {sorted(loaded_recording_names)}"

    @pytest.mark.e2e
    def test_burn_rate_alert_severity(self, api_client):
        """Burn-rate alerts have the correct severity labels."""
        resp = requests.get(f"{PROMETHEUS_URL}/api/v1/rules", timeout=10)
        data = resp.json()
        groups = data["data"]["groups"]

        severity_map = {}
        for group in groups:
            for rule in group.get("rules", []):
                if rule.get("type") == "alerting":
                    severity_map[rule["name"]] = rule.get("labels", {}).get("severity")

        assert severity_map.get("SloErrorBudgetFastBurn") == "critical"
        assert severity_map.get("SloErrorBudgetSlowBurn") == "warning"
        assert severity_map.get("CriticalErrorRate") == "critical"
        assert severity_map.get("HighErrorRate") == "warning"

    @pytest.mark.e2e
    def test_recording_rules_queryable(self, api_client):
        """All recording rules can be queried from Prometheus."""
        for rule_name in EXPECTED_RECORDING_RULES:
            resp = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": rule_name},
                timeout=10,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success", f"Query for {rule_name} failed: {data}"
