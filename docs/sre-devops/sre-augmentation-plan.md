# Plan: Augmenting Agentic Project for SRE/DevOps Portfolio

## Objective
Enhance the existing `agentic` project to serve as a comprehensive SRE/DevOps portfolio artifact by implementing SLOs, robust observability (Prometheus/Grafana), capacity planning, and incident response simulations.

## Proposed Phased Implementation

### Phase 1: Instrumentation (Metrics)
- [x] Add `prometheus-fastapi-instrumentator` to FastAPI backend.
- [x] Expose standard HTTP metrics (`requests_total`, `request_duration_seconds`).
- [x] Add custom agent metrics (`agent_retries_total`, `agent_failures_total`, `qdrant_operation_duration_seconds`).
- [x] Update Helm chart to add Prometheus annotations to the API pod.

### Phase 2: Observability Stack (Modular)
- [x] Deploy modular Prometheus, Grafana, and Alertmanager via individual Helm charts.
- [x] Configure Prometheus to scrape the `agent-stack-api` service.
- [x] Configure Alertmanager for SMTP email notifications.
- [x] Create a Grafana dashboard visualizing request rates, error rates, latency, and agent-specific metrics.

### Phase 3: SLO/SLI & Error Budgets
- [x] Create `docs/sre-devops/slo-spec.md` defining availability and latency objectives.
- [x] Implement Prometheus Alerting Rules for:
    - High error rates (5xx).
    - Latency breaches (p95).
    - Burn-rate alerts for error budget consumption.

### Phase 4: Capacity Planning & Load Testing
- [x] Set up `tests/load/` with `k6` test scenarios.
- [x] Conduct load tests at increasing RPS (1, 5, 10, 25, 50).
- [x] Document saturation points in `docs/sre-devops/capacity-plan.md`.

### Phase 5: Incident Simulation
- [x] Add `/debug/fail` and `/debug/slow` endpoints to FastAPI.
- [x] Induce failures, record data, and write a postmortem in `docs/sre-devops/incident-001.md`.
