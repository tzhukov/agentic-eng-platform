# Design: LLM Cost Observability

**Status:** Proposed  
**Author:** Forward Deployed Infrastructure  
**Last Updated:** 2026-06-27  
**Related:** [`llmrouter/docs/cost-observability/design.md`](../../../llmrouter/docs/cost-observability/design.md)

---

## 1. Overview

Enterprise AI deployments fail in production for two reasons beyond reliability: **cost overruns** and **cost opacity**. A traditional SRE observability stack (request rate, error rate, latency) does not surface LLM token spend, retry cost amplification, or per-query cost attribution — all of which Tribe AI client engagements require.

This design extends the existing `agentic` Prometheus/Grafana stack with LLM cost metrics, sourced from LiteLLM callbacks and surfaced alongside existing SLO panels. The `llmrouter` project's per-agent token accounting model is the reference implementation for the metric schema.

---

## 2. Goals

- Track token consumption (prompt + completion) per request, per model, and per agent.
- Surface estimated USD cost per query in Grafana.
- Quantify the cost amplification caused by the self-correction retry loop.
- Integrate into the existing `Agent Stack Dashboard` without disrupting current SLO panels.
- Provide a cost budget alert (analogous to error budget alerts) that fires when projected monthly spend exceeds a threshold.

## 3. Non-Goals

- Real-time billing integration with provider APIs (LLM provider invoices vary; this is estimation only).
- Showback/chargeback across multiple tenants (deferred — see `llmrouter` multi-tenant design).
- Cost attribution at the Kubernetes namespace level (out of scope for single-service deployment).

---

## 4. Metric Schema

### 4.1 New Prometheus Metrics in `agent-stack-api`

These metrics are emitted by the FastAPI service via `prometheus-client` and scraped by the existing Prometheus pod annotation discovery.

| Metric | Type | Labels | Description |
|---|---|---|---|
| `llm_tokens_total` | Counter | `model`, `token_type` (`prompt`/`completion`) | Cumulative token count |
| `llm_request_cost_usd` | Histogram | `model` | Estimated USD cost per LLM call |
| `agent_retry_tokens_total` | Counter | `model` | Tokens consumed in retry attempts (not first-pass) |
| `agent_retry_cost_usd` | Histogram | `model` | Estimated USD cost of retry calls specifically |
| `agent_total_cost_usd` | Histogram | — | Total estimated USD per end-to-end agent query |

### 4.2 Token → Cost Conversion Table

Prices are injected as environment variables and defaulted via `config.py`. This avoids hardcoding and allows cost-model updates without code changes.

```python
# src/agent/config.py
TOKEN_COSTS_USD_PER_1K: dict[str, dict[str, float]] = {
    "gemini-2.0-flash":    {"prompt": 0.00010, "completion": 0.00040},
    "gemini-1.5-pro":      {"prompt": 0.00125, "completion": 0.00500},
    "groq/llama3-8b":      {"prompt": 0.00005, "completion": 0.00008},
    "groq/llama3-70b":     {"prompt": 0.00059, "completion": 0.00079},
}
```

---

## 5. Implementation

### 5.1 LiteLLM Callback Integration

LiteLLM exposes a `success_handler` callback that fires after every LLM call with full token usage and model metadata. This is the capture point for all metrics.

```python
# src/agent/metrics.py  (additions)
import litellm
from prometheus_client import Counter, Histogram
from .config import settings

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total LLM tokens consumed",
    ["model", "token_type"],
)
llm_request_cost_usd = Histogram(
    "llm_request_cost_usd",
    "Estimated USD cost per LLM call",
    ["model"],
    buckets=[0.0001, 0.001, 0.01, 0.05, 0.10, 0.25, 0.50, 1.00],
)
agent_retry_tokens_total = Counter(
    "agent_retry_tokens_total",
    "LLM tokens consumed in self-correction retries",
    ["model"],
)
agent_total_cost_usd = Histogram(
    "agent_total_cost_usd",
    "Total estimated USD cost per agent query (all LLM calls)",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.10, 0.25, 0.50, 1.00],
)


def _cost_for_call(model: str, usage: litellm.Usage) -> float:
    table = settings.token_costs_usd_per_1k
    entry = table.get(model, {"prompt": 0.0, "completion": 0.0})
    prompt_cost = (usage.prompt_tokens / 1000) * entry["prompt"]
    completion_cost = (usage.completion_tokens / 1000) * entry["completion"]
    return prompt_cost + completion_cost


def litellm_cost_callback(kwargs, response_obj, start_time, end_time):
    model = kwargs.get("model", "unknown")
    usage = getattr(response_obj, "usage", None)
    if usage is None:
        return

    llm_tokens_total.labels(model=model, token_type="prompt").inc(usage.prompt_tokens)
    llm_tokens_total.labels(model=model, token_type="completion").inc(usage.completion_tokens)

    cost = _cost_for_call(model, usage)
    llm_request_cost_usd.labels(model=model).observe(cost)


# Register at startup (src/api/main.py)
litellm.success_callback = [litellm_cost_callback]
```

### 5.2 Retry Cost Tracking in the LangGraph Node

The self-correction node (`reflect_and_fix`) already tracks retry count in graph state. Attach cost attribution to retries by threading per-invocation cost through state:

```python
# src/agent/graph.py (additions to AgentState)
class AgentState(TypedDict):
    # ... existing fields ...
    retry_token_cost_usd: float   # accumulated cost of retry attempts
    total_token_cost_usd: float   # accumulated cost of all LLM calls
```

In the `reflect_and_fix` node, after LLM invocation:

```python
retry_cost = _cost_for_call(model, response.usage)
state["retry_token_cost_usd"] += retry_cost
agent_retry_tokens_total.labels(model=model).inc(
    response.usage.prompt_tokens + response.usage.completion_tokens
)
```

In the `final_answer` node (terminal), emit the per-query total:

```python
agent_total_cost_usd.observe(state["total_token_cost_usd"])
```

### 5.3 Grafana Dashboard Extension

Add a **Cost** row to the existing `Agent Stack Dashboard` (UID: `agent-dashboard`).

New panels:

| Panel | PromQL | Visualization |
|---|---|---|
| Token Rate (by model) | `sum(rate(llm_tokens_total[5m])) by (model, token_type)` | Time series |
| Estimated Cost Rate ($/hr) | `sum(rate(llm_request_cost_usd_sum[1h])) by (model) * 3600` | Stat |
| p95 Cost per Query | `histogram_quantile(0.95, sum(rate(agent_total_cost_usd_bucket[1h])) by (le))` | Stat |
| Retry Cost Ratio | `sum(rate(agent_retry_tokens_total[5m])) / sum(rate(llm_tokens_total[5m]))` | Gauge (0–100%) |
| Projected Monthly Cost | `sum(rate(llm_request_cost_usd_sum[1h])) * 720` | Stat with threshold alert at $50 |

### 5.4 Cost Budget Alert Rule

Add to `deploy/observability/prometheus-values.yaml` under `serverFiles.alerting_rules.yml`:

```yaml
- alert: LLMCostBudgetBurn
  expr: >
    sum(rate(llm_request_cost_usd_sum[1h])) * 720 > 50
  for: 30m
  labels:
    severity: warning
  annotations:
    summary: "Projected monthly LLM cost exceeds $50"
    description: >
      Current spend rate projects ${{ $value | printf "%.2f" }} for the month.
      Review retry amplification and model selection.
```

---

## 6. Integration with `llmrouter`

When `agentic` routes its LLM calls through the local `llmrouter` instance (via LiteLLM's OpenAI-compatible endpoint), cost metrics will be **double-tracked**: once in `agent-stack-api` (via LiteLLM callback) and once in `llmrouter` (via its own per-agent Prometheus counters).

This is intentional. The two sources answer different questions:

| Source | Answers |
|---|---|
| `agent-stack-api` metrics | "What did this agent spend per query?" |
| `llmrouter` metrics | "What did all agents spend, by provider and routing strategy?" |

For a client deployment, the `llmrouter` metrics become the **billing source of truth** across all tenants. The `agentic` metrics are the **per-service debug view**.

See [`llmrouter/docs/cost-observability/design.md`](../../../llmrouter/docs/cost-observability/design.md) for the router-side implementation.

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LiteLLM callback not firing for streaming responses | Silent metric gaps | Test with `stream=False` first; add streaming callback separately |
| Cost table becomes stale as providers reprice | Inaccurate cost estimates | Version-pin cost table in config; add `last_updated` timestamp to metric label |
| Retry cost tracking adds overhead to hot path | Latency regression | Metrics are in-memory counters — overhead is nanoseconds; no I/O in callback |
| Grafana ConfigMap size exceeds K8s limit (~1MB) | Dashboard provisioning fails | Split dashboard JSON into separate ConfigMaps per row |

---

## 8. Definition of Done

- [ ] `llm_tokens_total`, `llm_request_cost_usd`, `agent_total_cost_usd` visible in Prometheus UI.
- [ ] Cost row rendering in Grafana `Agent Stack Dashboard` with live data.
- [ ] `LLMCostBudgetBurn` alert fires correctly in simulation (call `/debug/slow` with high model cost).
- [ ] Retry cost ratio panel shows non-zero value when self-correction loop fires.
- [ ] Unit test: `test_cost_callback_records_metrics` passes in `tests/test_metrics.py`.
- [ ] `docs/reliability/cost-observability-design.md` linked from main `docs/DETAILED_DESIGN.md`.
