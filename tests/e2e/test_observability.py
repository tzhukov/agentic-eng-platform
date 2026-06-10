import subprocess
import time
import socket
import pytest
import requests

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

@pytest.fixture(scope="session", autouse=True)
def setup_observability_port_forwards():
    processes = []
    
    # 1. Prometheus port-forward (9090)
    if not is_port_open(9090):
        print("Starting port-forward for Prometheus server (9090)...")
        p_prom = subprocess.Popen([
            "kubectl", "port-forward", "svc/prometheus-server", "9090:80", "-n", "agent-system"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(p_prom)
    else:
        print("Prometheus port (9090) is already open.")

    # 2. Alertmanager port-forward (9093)
    if not is_port_open(9093):
        print("Starting port-forward for Alertmanager (9093)...")
        p_alert = subprocess.Popen([
            "kubectl", "port-forward", "svc/alertmanager", "9093:9093", "-n", "agent-system"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(p_alert)
    else:
        print("Alertmanager port (9093) is already open.")

    # 3. Grafana port-forward (3001)
    if not is_port_open(3001):
        print("Starting port-forward for Grafana (3001)...")
        p_graf = subprocess.Popen([
            "kubectl", "port-forward", "svc/grafana", "3001:80", "-n", "agent-system"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(p_graf)
    else:
        print("Grafana port (3001) is already open.")

    # Give a few seconds for connections to establish
    time.sleep(5)

    yield

    # Clean up port forward processes
    for p in processes:
        p.terminate()
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p.kill()

def test_prometheus_healthy_and_scraping_agent():
    # Verify Prometheus is healthy
    resp = requests.get("http://127.0.0.1:9090/-/healthy", timeout=5)
    assert resp.status_code == 200

    # Verify Prometheus discovers agent-stack-api metrics target
    resp = requests.get("http://127.0.0.1:9090/api/v1/targets", timeout=5)
    assert resp.status_code == 200
    targets = resp.json()["data"]["activeTargets"]
    
    agent_targets = [
        t for t in targets
        if t.get("labels", {}).get("app") == "agent-api" or t.get("discoveredLabels", {}).get("__meta_kubernetes_pod_label_app") == "agent-api"
    ]
    assert len(agent_targets) > 0, f"No prometheus target found for agent-stack-api. Found targets: {targets}"
    print(f"Found {len(agent_targets)} scraping target(s) for agent-stack-api.")

def test_alertmanager_configured_with_smtp():
    # Verify Alertmanager status & config
    resp = requests.get("http://127.0.0.1:9093/api/v2/status", timeout=5)
    assert resp.status_code == 200
    
    status_data = resp.json()
    config_yaml = status_data.get("config", {}).get("original", "")
    assert "smtp.mailtrap.io:2525" in config_yaml
    assert "alertmanager@agentic.local" in config_yaml

def test_grafana_dashboard_provisioned():
    # Verify Grafana dashboard exists
    auth = ("admin", "admin")
    resp = requests.get("http://127.0.0.1:3001/api/dashboards/uid/agent-dashboard", auth=auth, timeout=5)
    assert resp.status_code == 200
    
    dash_data = resp.json()
    assert dash_data["dashboard"]["title"] == "Agent Stack Dashboard"
    print("Grafana dashboard 'Agent Stack Dashboard' successfully provisioned and verified.")
