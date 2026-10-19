#!/usr/bin/env bash
# scripts/handoff-check.sh
# Validates system health and observability invariants across the agentic stack.
# Exit code: 0 if all pass, 1 if any fail.

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3001}"
GRAFANA_PASS="${GRAFANA_PASS:-admin}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://127.0.0.1:9093}"
QDRANT_URL="${QDRANT_URL:-http://172.18.255.200:6333}"

PASS=0
FAIL=0

check() {
  local name="$1"
  local cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    echo "  ✅ $name"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name"
    FAIL=$((FAIL + 1))
  fi
}

echo ""
echo "=== Agentic Stack — Handoff Validation ==="
echo ""

echo "── API Health"
check "Liveness (/healthz)"   "curl -sf --max-time 5 ${BASE_URL}/healthz"
check "Metrics endpoint"      "curl -sf --max-time 5 ${BASE_URL}/metrics | grep -q 'http_requests_total'"
check "Cost metrics exposed"  "curl -sf --max-time 5 ${BASE_URL}/metrics | grep -q 'llm_tokens_total'"

echo ""
echo "── Observability"
check "Prometheus healthy"         "curl -sf --max-time 5 ${PROMETHEUS_URL}/-/healthy"
check "Prometheus scraping agent"  "curl -sf --max-time 5 '${PROMETHEUS_URL}/api/v1/targets' | grep -q 'agent-api'"
check "Grafana healthy"            "curl -sf --max-time 5 -u admin:${GRAFANA_PASS} ${GRAFANA_URL}/api/health | grep -q 'ok'"
check "Agent dashboard exists"     "curl -sf --max-time 5 -u admin:${GRAFANA_PASS} ${GRAFANA_URL}/api/dashboards/uid/agent-dashboard"
check "Alertmanager healthy"       "curl -sf --max-time 5 ${ALERTMANAGER_URL}/-/healthy"
check "Cost alert loaded"          "curl -sf --max-time 5 ${PROMETHEUS_URL}/api/v1/rules | grep -q 'LLMCostBudgetBurn'"

echo ""
echo "── Dependencies"
check "Qdrant cluster/host reachable" "curl -sf --max-time 5 ${QDRANT_URL}/healthz || curl -sf --max-time 5 http://127.0.0.1:6333/healthz"

echo ""
echo "── Kubernetes"
if command -v kubectl >/dev/null 2>&1; then
  check "Namespace agent-system exists" "kubectl get ns agent-system"
  check "Agent pods present"            "kubectl get pods -n agent-system -l app=agent-api --no-headers | grep -q Running"
else
  echo "  ℹ️  kubectl not installed or not in PATH, skipping K8s checks."
fi

echo ""
echo "──────────────────────────────────────────"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "  ⚠️  Handoff check FAILED (${FAIL} checks failed). Resolve failures before closing engagement."
  exit 1
else
  echo "  ✅ Handoff check PASSED. System is healthy and observable."
  exit 0
fi
