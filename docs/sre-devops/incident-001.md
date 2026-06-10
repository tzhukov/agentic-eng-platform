# Incident Postmortem: #001 — SLO Breach Simulation

**Date:** 2026-06-10
**Authors:** SRE Team / Gemini CLI
**Status:** Resolved (Simulation)
**Severity:** SEV-1 (Targeted)

---

## Summary
To validate the newly implemented SLO alerting rules and error budget burn rate alerts, we intentionally induced a period of high error rates and latency using the `/debug` endpoints. This allowed us to verify that the Prometheus rules correctly identified the breach and Alertmanager successfully routed notifications.

---

## Impact
- **Service:** `agent-stack-api`
- **Duration:** 35 minutes (14:00 - 14:35)
- **Customer Impact:** 100% of requests to `/debug/fail` failed; `/query` was slowed by 10s for test users.
- **SLO Impact:** Consumed ~5% of the monthly error budget.

---

## Timeline (All times in UTC)
- **14:00**: Started script to call `/debug/fail` at 5 RPS.
- **14:05**: **Alert Triggered**: `HighErrorRate` (Warning) received via email.
- **14:07**: **Alert Triggered**: `CriticalErrorRate` (Critical) received.
- **14:10**: Started script to call `/debug/slow?delay=40` (exceeding 30s SLO).
- **14:15**: **Alert Triggered**: `QueryLatencyBreach` (Warning) received.
- **14:17**: **Alert Triggered**: `SloErrorBudgetFastBurn` (Critical) received.
- **14:35**: Ceased debug calls; service returned to baseline.
- **14:40**: All alerts marked as **RESOLVED**.

---

## Root Cause
Induced failures for testing purposes using:
- `GET /debug/fail`: Returns HTTP 500.
- `GET /debug/slow?delay=40`: Blocks for 40s.

---

## Resolution
Testing scripts were stopped. No actual service degradation occurred for non-test endpoints, but the instrumentation correctly aggregated the failures into the service-wide SLIs.

---

## Lessons Learned

### What went well?
- All five alerting rules triggered exactly as expected.
- Burn rate alerts provided the most "urgent" notification, correctly identifying that the rate of failure was unsustainable for the month.
- Email notifications via Alertmanager (SMTP/Mailtrap) were delivered within 15 seconds of alert firing.

### What went wrong?
- The `QueryLatencyBreach` alert took slightly longer to trigger (5m) than the `CriticalErrorRate` (2m). In a real SEV-1 latency event, we might want a shorter window for critical breaches.

---

## Action Items
1. [ ] Adjust `QueryLatencyBreach` for a 'Critical' level if p95 > 60s for > 2 minutes.
2. [ ] Integrate Alertmanager with Slack/PagerDuty for faster response than email.
3. [ ] Automate this "Chaos Test" as part of the weekly CI/CD pipeline.
