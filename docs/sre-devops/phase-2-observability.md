# Phase 2: Observability Stack — Completion Report

## Overview

Deployed a fully modular observability stack (Prometheus, Alertmanager, Grafana) into the existing `agent-system` Kubernetes namespace, configured Prometheus pod-level scraping of the FastAPI metrics endpoint, configured Alertmanager with SMTP email routing, and provisioned a pre-built Grafana dashboard covering all key SRE signals.

---

## Work Performed

### 1. Prometheus Scrape Annotations (`deploy/charts/agent/templates/api-deployment.yaml`)

Added Prometheus annotations to the **Pod template** (not just the Deployment metadata) so that Prometheus's `kubernetes-pods` scrape job can discover and scrape the `/metrics` endpoint on each running API pod:

```yaml
template:
  metadata:
    annotations:
      prometheus.io/scrape: "true"
      prometheus.io/port: "8000"
      prometheus.io/path: "/metrics"
```

### 2. Modular Helm Deployments (`deploy/observability/`)

Three separate Helm releases deployed into `agent-system`:

| Release | Chart | Notes |
|---------|-------|-------|
| `prometheus` | `prometheus-community/prometheus` | Alertmanager, NodeExporter, KubeStateMetrics disabled; persistence disabled |
| `alertmanager` | `prometheus-community/alertmanager` | SMTP route to `smtp.mailtrap.io:2525` |
| `grafana` | `grafana/grafana` | Prometheus datasource pre-provisioned; dashboard provisioned via ConfigMap |

**Values files:**
- [`deploy/observability/prometheus-values.yaml`](file:///home/txz/dev/agentic/deploy/observability/prometheus-values.yaml)
- [`deploy/observability/alertmanager-values.yaml`](file:///home/txz/dev/agentic/deploy/observability/alertmanager-values.yaml)
- [`deploy/observability/grafana-values.yaml`](file:///home/txz/dev/agentic/deploy/observability/grafana-values.yaml)

### 3. Grafana Dashboard

A provisioned dashboard `Agent Stack Dashboard` (UID: `agent-dashboard`) containing 4 panels:

| Panel | PromQL |
|-------|--------|
| HTTP Request Rate (by status) | `sum(rate(http_requests_total[5m])) by (status)` |
| HTTP Error Rate (5xx %) | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100` |
| HTTP p95 Latency | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` |
| Agent Custom Metrics | `agent_retries_total`, `agent_failures_total` |

### 4. Deployment Script (`scripts/deploy-observability.sh`)

An idempotent deployment script that:
- Resolves the running Tilt image tags dynamically (avoids `ErrImagePull` in kind)
- Reads API credentials from `.env` and injects them into the Helm secret template
- Runs `helm upgrade --install` for all three observability releases
- Waits for all rollouts to complete

### 5. E2E Tests (`tests/e2e/test_observability.py`)

Added three new E2E tests (integrated into `scripts/run-tests.sh`):

| Test | What it validates |
|------|-------------------|
| `test_prometheus_healthy_and_scraping_agent` | Prometheus is healthy AND has an active scrape target for the `agent-api` pod |
| `test_alertmanager_configured_with_smtp` | Alertmanager `/api/v2/status` reports SMTP config with `smtp.mailtrap.io:2525` |
| `test_grafana_dashboard_provisioned` | Grafana API returns HTTP 200 for dashboard UID `agent-dashboard` with correct title |

---

## Proof of Completion

### Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/txz/dev/agentic

tests/test_graph.py::TestAgentGraph::test_graph_retry_path PASSED        [ 12%]
tests/test_graph.py::TestAgentGraph::test_graph_success_path PASSED      [ 25%]
tests/test_integration.py::TestAgentIntegration::test_self_correction_loop_integration PASSED [ 37%]
tests/e2e/test_api.py::test_health_endpoint PASSED                       [ 50%]
tests/e2e/test_api.py::test_query_endpoint PASSED                        [ 62%]
tests/e2e/test_observability.py::test_prometheus_healthy_and_scraping_agent PASSED [ 75%]
tests/e2e/test_observability.py::test_alertmanager_configured_with_smtp PASSED [ 87%]
tests/e2e/test_observability.py::test_grafana_dashboard_provisioned PASSED [100%]

======================== 8 passed, 1 warning in 24.56s =========================
```

### Running Pods (kubectl get pods -n agent-system)

```
alertmanager-0                                       1/1     Running
grafana-945b68b9c-mr756                              1/1     Running
prometheus-server-fdd489dd9-ghdcs                    2/2     Running
agent-stack-api-68cbc8d8f6-zl86g                     1/1     Running
```

### Helm Releases

```
NAME          NAMESPACE     REVISION  STATUS    CHART
prometheus    agent-system  4         deployed  prometheus-19.x
alertmanager  agent-system  4         deployed  alertmanager-1.x
grafana       agent-system  4         deployed  grafana-10.x
```

---

## Access

| Service | Command |
|---------|---------|
| Prometheus | `kubectl port-forward svc/prometheus-server 9090:80 -n agent-system` → http://localhost:9090 |
| Alertmanager | `kubectl port-forward svc/alertmanager 9093:9093 -n agent-system` → http://localhost:9093 |
| Grafana | `kubectl port-forward svc/grafana 3001:80 -n agent-system` → http://localhost:3001 (admin/admin) |
