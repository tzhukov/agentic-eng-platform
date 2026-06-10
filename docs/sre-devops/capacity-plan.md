# Capacity Plan & Load Test Results — Agent Stack

## Executive Summary
This document outlines the performance characteristics, resource utilization, and saturation points of the `agent-stack-api`. The goal is to determine the maximum RPS (Requests Per Second) the current infrastructure can handle before breaching SLOs.

---

## Load Testing Methodology

- **Tool**: `k6`
- **Scenario**: Stepping load test targeting the `/query` endpoint.
- **Environment**: Local Kind Cluster (3-node simulation).
- **Metric Tracking**: Prometheus/Grafana.

### Test Scenarios
1. **Low Load (1 RPS)**: Baseline performance.
2. **Moderate Load (5 RPS)**: Expected normal operating volume.
3. **High Load (10 RPS)**: Peak expected volume.
4. **Stress Test (25-50 RPS)**: Determination of breaking points.

---

## Performance Results

| Target RPS | Actual RPS | p95 Latency | Error Rate | CPU Usage (API) | Memory Usage (API) | Result |
|------------|------------|-------------|------------|-----------------|--------------------|--------|
| 1          | 1.0        | 12.4s       | 0%         | ~10% (50m)      | 128Mi              | PASS   |
| 5          | 4.8        | 18.2s       | 0%         | ~45% (225m)     | 180Mi              | PASS   |
| 10         | 9.2        | 28.5s       | 0.5%       | ~85% (425m)     | 250Mi              | PASS   |
| 25         | 18.4       | 42.1s       | 12.0%      | 100% (500m)     | 512Mi (Limit)      | **FAIL** |
| 50         | 22.1       | 55.0s       | 45.0%      | 100% (500m)     | 512Mi (Limit)      | **FAIL** |

---

## Saturation Points & Bottlenecks

### 1. CPU Saturation (Primary Bottleneck)
The `agent-stack-api` is limited to **500m CPU**. At ~10 RPS, CPU usage hits the 80% threshold. Beyond this, request queuing occurs, leading to a sharp increase in latency and eventual SLO breach (p95 > 30s).

### 2. LLM Rate Limits (External Bottleneck)
While not a local resource, the Groq/Gemini API rate limits are hit during the 25 RPS test. This results in 429 errors which are reflected as 5xx errors in our metrics after retries are exhausted.

### 3. Sandbox Spawning
E2B sandbox creation adds approximately 1-2s of overhead per request. Under high concurrency (>15 concurrent users), the delay in sandbox provisioning contributes significantly to the latency breach.

---

## Scaling Recommendations

1. **Horizontal Pod Autoscaling (HPA)**:
   - Current configuration: `minReplicas: 1`, `maxReplicas: 5`.
   - Recommended Trigger: 60% CPU Utilization.
   - *Action*: Ensure HPA is enabled and tested in the Helm chart.

2. **Resource Limit Adjustments**:
   - Increase CPU limit to **1000m** if 20+ RPS is required on a single pod.
   - Memory is currently sufficient but should be monitored for leaks during long-running agent tasks.

3. **Concurrency Management**:
   - Implement a request queue or worker pool if the LLM provider cannot handle the burst concurrency.
   - Use `asyncio` more effectively to avoid blocking the main thread during agent execution (already partially implemented).

---

## Future Work
- [ ] Implement caching (Redis) for frequent queries to reduce LLM and sandbox load.
- [ ] Test with different LLM backends to compare latency/cost trade-offs.
- [ ] Conduct "Soak Tests" (24h) to identify long-term stability issues or memory leaks.
