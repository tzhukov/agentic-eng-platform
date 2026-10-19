# Incident Response Runbook

This runbook outlines immediate triaging, escalation, and resolution steps for all Prometheus Alertmanager alerts in the agent platform.

---

### HighErrorRate
- **Severity:** `warning`
- **Condition:** 5xx error rate > 5% over 5m window
- **SLO Impact:** Consuming availability error budget at an accelerated pace
- **Immediate Steps:**
  1. Inspect pod logs: `kubectl logs -n agent-system -l app=agent-api --tail=100 -f`
  2. Check downstream service connectivity (Qdrant, LLM providers): `curl -sf http://127.0.0.1:8000/healthz`
  3. Determine if errors correlate with a specific endpoint (e.g. `/query` vs `/debug/*`) in Grafana.
- **Escalation:** If error rate remains above 5% for >15 minutes, notify on-call infrastructure lead.

---

### CriticalErrorRate
- **Severity:** `critical`
- **Condition:** 5xx error rate > 20% over 2m window
- **SLO Impact:** Severe error budget burn; imminent total outage
- **Immediate Steps:**
  1. Check pod status: `kubectl get pods -n agent-system`
  2. If CrashLoopBackOff: `kubectl describe pod -l app=agent-api -n agent-system`
  3. Check recent deployments: `helm history agent-stack -n agent-system`
  4. If bad release: Roll back via `helm rollback agent-stack <PREVIOUS_REVISION> -n agent-system`
- **Escalation:** Page on-call immediately; declare Sev-1 incident if rollback does not restore service within 5m.

---

### QueryLatencyBreach
- **Severity:** `warning`
- **Condition:** p95 latency on `/query` > 30s over 5m window
- **SLO Impact:** Latency SLO violation (target: 95% of queries complete in <30s)
- **Immediate Steps:**
  1. Check Grafana `Agent Custom Metrics`: Are retries elevated (`agent_retries_total`)?
  2. Check E2B sandbox execution metrics: Is E2B experiencing queuing or API throttles?
  3. Check LLM provider latency in LangFuse traces.
- **Resolution Verification:** Observe p95 latency drop below 30s in Grafana for 10 consecutive minutes.

---

### SloErrorBudgetFastBurn
- **Severity:** `critical`
- **Condition:** 14.4× burn rate detected across both 1h and 5m windows
- **SLO Impact:** 100% of the monthly error budget will be exhausted in ~2 days
- **Immediate Steps:**
  1. Freeze non-emergency deployments immediately.
  2. Check error breakdown in Grafana: Are 500s originating from agent code generation or execution?
  3. If third-party provider outage (Groq / Gemini / E2B), update provider status in status page and enable graceful fallback.

---

### SloErrorBudgetSlowBurn
- **Severity:** `warning`
- **Condition:** 6× burn rate detected across both 6h and 30m windows
- **SLO Impact:** Monthly error budget exhausted in ~5 days if sustained
- **Immediate Steps:**
  1. Review error trends over past 6 hours in Grafana.
  2. Identify recurring failure patterns or edge-case queries causing retries.
  3. Schedule bug fix in current sprint backlog.

---

### LLMCostBudgetBurn
- **Severity:** `warning`
- **Condition:** Projected monthly LLM cost exceeds $50 (spend rate: `sum(rate(llm_request_cost_usd_sum[1h])) * 720 > 50`)
- **SLO Impact:** Financial budget overrun; runaway retry amplification risk
- **Immediate Steps:**
  1. Check `Retry Cost Ratio (%)` panel in Grafana: Is the retry loop amplifying token consumption?
  2. Check `LLM Token Rate (by model)` panel: Has traffic shifted to a higher-cost model?
  3. Inspect recent queries: Are user inputs unusually long or causing repetitive failed attempts?
  4. If runaway agent loops: Temporarily clamp `retry_count` max limit in `graph.py` or throttle abusive callers.
