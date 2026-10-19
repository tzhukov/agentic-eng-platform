# Design: Client Handoff Artifacts

**Status:** Proposed  
**Author:** Forward Deployed Infrastructure  
**Last Updated:** 2026-06-27  

---

## 1. Overview

A Forward Deployed Infrastructure Engineer's deliverable is not a running system — it is a **system that the client's team can operate without the original engineer present**. This design defines the artifacts, tooling, and documentation that constitute a complete client handoff for the `agentic` stack.

The principle: **if it cannot be explained in writing and validated by a script, it is not complete.**

---

## 2. Goals

- Produce a structured operations runbook covering day-0 deployment, day-1 operations, and day-2 incident response.
- Create a `make handoff-check` target that validates all observable system invariants are healthy before an engagement closes.
- Define the minimum knowledge transfer checklist that a client's platform team needs to be self-sufficient.
- Ensure all runbook steps are tested — no undocumented manual steps.

## 3. Non-Goals

- Replacing the SLO spec (`docs/sre-devops/slo-spec.md`) — the handoff runbook references it, not duplicates it.
- Training client engineers on Kubernetes fundamentals — assumes K8s-literate operators.
- Covering multi-region or DR procedures — scoped to single-region deployment.

---

## 4. Artifact Structure

```
docs/runbook/
  client-handoff-design.md   ← this document
  operations.md              ← day-to-day operations guide (to be implemented)
  incident-response.md       ← per-alert response procedures (to be implemented)
  architecture-overview.md   ← system map for new operators (to be implemented)

scripts/
  handoff-check.sh           ← automated validation script (to be implemented)

Makefile
  handoff-check              ← target invoking handoff-check.sh
```

---

## 5. `handoff-check.sh` — Validation Script Design

This script is the single command a client runs to confirm the deployment is healthy and observable. It must exit `0` only when all checks pass. It must print a clear status line per check.

### 5.1 Checks

| Check | Command | Pass Condition |
|---|---|---|
| API liveness | `curl -sf $BASE_URL/healthz` | HTTP 200 |
| API readiness | `curl -sf $BASE_URL/readyz` | HTTP 200 |
| Metrics endpoint | `curl -sf $BASE_URL/metrics \| grep http_requests_total` | Metric present |
| Prometheus healthy | `curl -sf $PROMETHEUS_URL/-/healthy` | HTTP 200 |
| Prometheus target up | `curl -sf $PROMETHEUS_URL/api/v1/targets \| jq '.data.activeTargets[] \| select(.labels.job=="kubernetes-pods") \| .health'` | `"up"` |
| Grafana healthy | `curl -sf -u admin:$GRAFANA_PASS $GRAFANA_URL/api/health` | `{"database": "ok"}` |
| Grafana dashboard exists | `curl -sf -u admin:$GRAFANA_PASS $GRAFANA_URL/api/dashboards/uid/agent-dashboard` | HTTP 200 |
| Alertmanager healthy | `curl -sf $ALERTMANAGER_URL/-/healthy` | HTTP 200 |
| Qdrant healthy | `curl -sf $QDRANT_URL/healthz` | HTTP 200 |
| All pods Running | `kubectl get pods -n agent-system --no-headers \| awk '{print $3}' \| sort -u` | Only `Running` |
| No pod restarts > 3 | `kubectl get pods -n agent-system -o json \| jq '[.items[].status.containerStatuses[].restartCount] \| max'` | `<= 3` |
| HPA exists (if cloud) | `kubectl get hpa -n agent-system` | HPA object present |

### 5.2 Script Structure

```bash
#!/usr/bin/env bash
# scripts/handoff-check.sh
# Usage: BASE_URL=https://... PROMETHEUS_URL=http://... ./scripts/handoff-check.sh

set -euo pipefail

PASS=0
FAIL=0

check() {
  local name="$1"
  local cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    echo "  ✅ $name"
    ((PASS++))
  else
    echo "  ❌ $name"
    ((FAIL++))
  fi
}

echo ""
echo "=== Agentic Stack — Handoff Validation ==="
echo ""

echo "── API Health"
check "Liveness (/healthz)"   "curl -sf ${BASE_URL}/healthz"
check "Readiness (/readyz)"   "curl -sf ${BASE_URL}/readyz"
check "Metrics endpoint"      "curl -sf ${BASE_URL}/metrics | grep -q http_requests_total"

echo ""
echo "── Observability"
check "Prometheus healthy"         "curl -sf ${PROMETHEUS_URL}/-/healthy"
check "Prometheus scraping agent"  "curl -sf '${PROMETHEUS_URL}/api/v1/query?query=up{job=\"kubernetes-pods\"}' | jq -e '.data.result | length > 0'"
check "Grafana healthy"            "curl -sf -u admin:${GRAFANA_PASS} ${GRAFANA_URL}/api/health | jq -e '.database == \"ok\"'"
check "Agent dashboard exists"     "curl -sf -u admin:${GRAFANA_PASS} ${GRAFANA_URL}/api/dashboards/uid/agent-dashboard"
check "Alertmanager healthy"       "curl -sf ${ALERTMANAGER_URL}/-/healthy"

echo ""
echo "── Dependencies"
check "Qdrant healthy"   "curl -sf ${QDRANT_URL}/healthz"

echo ""
echo "── Kubernetes"
check "All pods Running"       "[ \"\$(kubectl get pods -n agent-system --no-headers | awk '{print \$3}' | sort -u)\" = 'Running' ]"
check "Pod restarts < 3"       "[ \"\$(kubectl get pods -n agent-system -o json | jq '[.items[].status.containerStatuses[].restartCount] | max')\" -le 3 ]"

echo ""
echo "──────────────────────────────────────────"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "  ⚠️  Handoff check FAILED. Resolve failures before closing engagement."
  exit 1
else
  echo "  ✅ Handoff check PASSED. System is healthy and observable."
  exit 0
fi
```

### 5.3 Makefile Target

```makefile
.PHONY: handoff-check
handoff-check: ## Validate all system invariants before client handoff
	@echo "Running handoff validation..."
	@BASE_URL=$(BASE_URL) \
	 PROMETHEUS_URL=$(PROMETHEUS_URL) \
	 GRAFANA_URL=$(GRAFANA_URL) \
	 GRAFANA_PASS=$(GRAFANA_PASS) \
	 ALERTMANAGER_URL=$(ALERTMANAGER_URL) \
	 QDRANT_URL=$(QDRANT_URL) \
	 ./scripts/handoff-check.sh
```

---

## 6. `operations.md` — Content Specification

The operations runbook must cover the following sections. Each section maps to a concrete operator task.

### 6.1 Access & Credentials

- How to retrieve Grafana admin password from K8s Secret or Secret Manager.
- How to port-forward each service for local debugging.
- RBAC: minimum permissions a read-only ops user needs.

### 6.2 Routine Operations

| Task | Frequency | Procedure |
|---|---|---|
| Review Grafana dashboard | Daily | Check request rate, error rate, p95 latency, cost panels |
| Check error budget remaining | Weekly | Prometheus query or SLO panel |
| Review pod restart counts | Weekly | `kubectl get pods -n agent-system` |
| Rotate API keys | Quarterly | Update Secret Manager → ESO auto-syncs K8s secret → rolling restart |
| Update agent image | As needed | `scripts/push-image.sh && helm upgrade ...` with new `image.tag` |
| Scale replicas | On demand | `kubectl scale deploy agent-stack-api --replicas=N -n agent-system` or edit HPA |

### 6.3 Configuration Changes

All configuration changes must go through the Helm values files, not `kubectl edit`. Changes to `values-gke.yaml` must be committed to git before applying.

```bash
# Correct
vim deploy/charts/agent/values-gke.yaml
git commit -am "chore: increase memory limit to 1.5Gi"
helm upgrade agent-stack ./deploy/charts/agent -f values.yaml -f values-gke.yaml -n agent-system

# Incorrect — will be overwritten on next helm upgrade
kubectl edit deploy agent-stack-api -n agent-system
```

---

## 7. `incident-response.md` — Content Specification

Maps every Alertmanager alert to a concrete response procedure. Format per alert:

```
### <AlertName>

**Severity:** critical | warning
**Meaning:** <one sentence>
**SLO Impact:** <which SLO is at risk and how fast>

#### Immediate Steps
1. ...
2. ...

#### Escalation
If unresolved after N minutes: ...

#### Resolution Verification
- [ ] Alert marked RESOLVED in Alertmanager
- [ ] SLO panel shows recovery
```

Alerts requiring procedures (from `slo-spec.md`):

- `HighErrorRate`
- `CriticalErrorRate`
- `QueryLatencyBreach`
- `SloErrorBudgetFastBurn`
- `SloErrorBudgetSlowBurn`
- `LLMCostBudgetBurn` *(new — from cost-observability-design.md)*

---

## 8. Knowledge Transfer Checklist

The following topics must be covered in a live walkthrough session with the client team before engagement close. Each item is checkbox-gated in a `handoff-session.md` sign-off document.

### Architecture
- [ ] Client team can describe the data flow: user → API → LangGraph → LiteLLM → LLM provider → E2B → Qdrant
- [ ] Client team knows the Helm chart layout and which `values-gke.yaml` knobs control capacity

### Operations
- [ ] Client team can access Grafana and interpret all dashboard panels
- [ ] Client team can rotate secrets without engineer help
- [ ] Client team can deploy a new image version via `helm upgrade`
- [ ] Client team understands HPA behavior and when to intervene manually

### Incident Response
- [ ] Client team has received the alert email at least once (from incident simulation)
- [ ] Client team can follow the `incident-response.md` runbook for each alert
- [ ] Client team knows the escalation path if runbook does not resolve the issue

### Cost Management
- [ ] Client team understands the `Projected Monthly Cost` Grafana panel
- [ ] Client team knows how to update the cost table when providers reprice
- [ ] Client team has reviewed the retry cost ratio and understands its implications

---

## 9. Implementation Milestones

### Milestone 1: Scripts & Makefile
- [ ] `scripts/handoff-check.sh` created and executable
- [ ] `make handoff-check` target added to `Makefile`
- [ ] Script passes on the local kind deployment

### Milestone 2: Operations Runbook
- [ ] `docs/runbook/operations.md` written with all sections from §6
- [ ] Every procedure in the runbook tested end-to-end

### Milestone 3: Incident Response Runbook
- [ ] `docs/runbook/incident-response.md` written for all 6 alerts
- [ ] Alert simulation run for each alert to verify steps work

### Milestone 4: Architecture Overview
- [ ] `docs/runbook/architecture-overview.md` includes system diagram (Mermaid)
- [ ] All external dependencies listed with contact/support links

### Milestone 5: Sign-Off
- [ ] `make handoff-check` passes on cloud deployment
- [ ] Live walkthrough completed with client team
- [ ] `handoff-session.md` sign-off document signed

---

## 10. Definition of Done

- [ ] `scripts/handoff-check.sh` exits `0` against the cloud deployment.
- [ ] `make handoff-check` works from a clean clone with only env vars set.
- [ ] All three runbook docs written and reviewed.
- [ ] A simulated new operator (no prior context) can onboard using only `docs/runbook/` in under 30 minutes.
