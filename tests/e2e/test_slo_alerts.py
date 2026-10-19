"""
E2E tests: Phase 3 — SLO/SLI & Error Budget Alerting Rules

Validates that the Prometheus alerting rules and recording rules defined in
deploy/observability/prometheus-values.yaml are correctly loaded into the
running Prometheus instance.
"""
import socket
import subprocess
import time

import pytest
import requests

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


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="session", autouse=True)
def ensure_prometheus_port_forward():
    """Start a port-forward to Prometheus if not already running."""
    if is_port_open(9090):
        yield
        return

    p = subprocess.Popen(
        ["kubectl", "port-forward", "svc/prometheus-server", "9090:80", "-n", "agent-system"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)
    yield
    p.terminate()
    try:
        p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        p.kill()


def _get_all_rules() -> dict:
    """Fetch all rules from Prometheus /api/v1/rules."""
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/rules", timeout=10)
    resp.raise_for_status()
    return resp.json()


def test_prometheus_rules_endpoint_reachable():
    """Prometheus rules API is accessible and returns a valid response."""
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/rules", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "data" in data
    assert "groups" in data["data"]


def test_all_alert_rules_loaded():
    """All SLO alerting rules defined in prometheus-values.yaml are loaded."""
    data = _get_all_rules()
    groups = data["data"]["groups"]

    loaded_alert_names = set()
    for group in groups:
        for rule in group.get("rules", []):
            if rule.get("type") == "alerting":
                loaded_alert_names.add(rule["name"])

    missing = [r for r in EXPECTED_ALERT_RULES if r not in loaded_alert_names]
    assert not missing, (
        f"Missing alerting rules: {missing}\n"
        f"Loaded alerts: {sorted(loaded_alert_names)}"
    )
    print(f"✓ All {len(EXPECTED_ALERT_RULES)} alerting rules loaded: {EXPECTED_ALERT_RULES}")


def test_all_recording_rules_loaded():
    """All SLO recording rules defined in prometheus-values.yaml are loaded."""
    data = _get_all_rules()
    groups = data["data"]["groups"]

    loaded_recording_names = set()
    for group in groups:
        for rule in group.get("rules", []):
            if rule.get("type") == "recording":
                loaded_recording_names.add(rule["name"])

    missing = [r for r in EXPECTED_RECORDING_RULES if r not in loaded_recording_names]
    assert not missing, (
        f"Missing recording rules: {missing}\n"
        f"Loaded recording rules: {sorted(loaded_recording_names)}"
    )
    print(f"✓ All {len(EXPECTED_RECORDING_RULES)} recording rules loaded: {EXPECTED_RECORDING_RULES}")


def test_burn_rate_alert_rules_have_correct_severity():
    """Burn-rate alerts have the correct severity labels."""
    data = _get_all_rules()
    groups = data["data"]["groups"]

    severity_map = {}
    for group in groups:
        for rule in group.get("rules", []):
            if rule.get("type") == "alerting":
                severity_map[rule["name"]] = rule.get("labels", {}).get("severity")

    assert severity_map.get("SloErrorBudgetFastBurn") == "critical", (
        f"SloErrorBudgetFastBurn should be 'critical', got: {severity_map.get('SloErrorBudgetFastBurn')}"
    )
    assert severity_map.get("SloErrorBudgetSlowBurn") == "warning", (
        f"SloErrorBudgetSlowBurn should be 'warning', got: {severity_map.get('SloErrorBudgetSlowBurn')}"
    )
    assert severity_map.get("CriticalErrorRate") == "critical"
    assert severity_map.get("HighErrorRate") == "warning"
    print("✓ All burn-rate alert severity labels are correctly configured.")


def test_recording_rules_are_evaluating():
    """Recording rules can be queried from Prometheus (they produce results or return no-data gracefully)."""
    for rule_name in EXPECTED_RECORDING_RULES:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": rule_name},
            timeout=10,
        )
        assert resp.status_code == 200, f"Query for {rule_name} failed with {resp.status_code}"
        data = resp.json()
        assert data["status"] == "success", f"Query for {rule_name} returned non-success: {data}"
    print(f"✓ All {len(EXPECTED_RECORDING_RULES)} recording rules are queryable.")
