# SLO/SLI Specification — Agent Stack API

## Service Description

The `agent-stack-api` is a FastAPI service that executes a LangGraph-based self-correction coding agent. It handles user queries (`POST /query`) and exposes a health check (`GET /healthz`).

---

## SLIs (Service Level Indicators)

| SLI | Definition | Prometheus Expression |
|-----|-----------|----------------------|
| **Availability** | Proportion of requests that succeed (non-5xx) | `1 - (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))` |
| **Latency (p95) — /query** | 95th percentile request duration for the /query endpoint | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{endpoint="/query"}[5m])) by (le))` |
| **Latency (p95) — /healthz** | 95th percentile request duration for health checks | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{endpoint="/healthz"}[5m])) by (le))` |
| **Agent Retry Rate** | Rate of agent self-corrections (indicator of LLM quality) | `sum(rate(agent_retries_total[5m]))` |

---

## SLOs (Service Level Objectives)

### SLO 1 — Availability
> **99.5% of requests must succeed (non-5xx) over a 30-day rolling window.**

| Window | Error Budget |
|--------|-------------|
| 30 days | 3h 36m (0.5%) |
| 7 days | 50m 24s |
| 1 day | 7m 12s |

### SLO 2 — Query Latency
> **95% of `/query` requests must complete within 30 seconds over a 30-day rolling window.**

This accounts for the non-deterministic nature of LLM inference and multi-step agent execution (retrieval → generation → sandbox execution → self-correction loop).

| Window | Latency Target |
|--------|---------------|
| p95 | ≤ 30s |
| p99 | ≤ 60s (aspirational) |

### SLO 3 — Health Check Latency
> **95% of `/healthz` requests must complete within 200ms over a 30-day rolling window.**

---

## Error Budget Policy

### Burn Rate Thresholds

Using the multi-window, multi-burn-rate (MWMBR) alerting model from the Google SRE Workbook:

| Alert Name | Burn Rate | Short Window | Long Window | Meaning |
|-----------|-----------|-------------|------------|---------|
| `SloErrorBudgetFastBurn` | 14.4× | 5 minutes | 1 hour | Will exhaust monthly budget in ~2 days |
| `SloErrorBudgetSlowBurn` | 6× | 30 minutes | 6 hours | Will exhaust monthly budget in ~5 days |

A **burn rate of 1×** = consuming error budget at exactly the rate that would exhaust it in 30 days.

### Budget Consumption Actions

| Remaining Budget | Action |
|-----------------|--------|
| > 50% | Normal operations |
| 25–50% | Increased monitoring, on-call awareness |
| 10–25% | Freeze non-critical changes, incident review |
| < 10% | Incident declared, escalate to engineering lead |

---

## Alerting Rules

Defined in `deploy/observability/prometheus-values.yaml` under `serverFiles.alerting_rules.yml`.

### HighErrorRate
- **Condition:** 5xx error rate > 5% sustained for 5 minutes
- **Severity:** `warning`

### CriticalErrorRate
- **Condition:** 5xx error rate > 20% sustained for 2 minutes
- **Severity:** `critical`

### QueryLatencyBreach
- **Condition:** p95 `/query` latency > 30s for 5 minutes
- **Severity:** `warning`

### SloErrorBudgetFastBurn
- **Condition:** Error rate burn rate > 14.4× in both 1h and 5m windows
- **Severity:** `critical` — pages on-call immediately

### SloErrorBudgetSlowBurn
- **Condition:** Error rate burn rate > 6× in both 6h and 30m windows
- **Severity:** `warning` — ticket created, review at next working hour
