"""
src/agent/metrics.py

LLM Cost Observability — Prometheus metrics + LiteLLM success callback.

Registers the following metrics (all scraped via /metrics):
  - llm_tokens_total          Counter  (model, token_type)
  - llm_request_cost_usd      Histogram (model)
  - agent_retry_tokens_total  Counter  (model)
  - agent_retry_cost_usd      Histogram (model)
  - agent_total_cost_usd      Histogram ()

Call `register_litellm_callback()` once at application startup to wire the
LiteLLM success handler. Use `observe_query_cost(total_usd)` in the terminal
graph node to record per-query totals.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# ---------------------------------------------------------------------------
# Token cost table — prices in USD per 1 000 tokens.
# Override by setting TOKEN_COST_* environment variables (see config.py).
# ---------------------------------------------------------------------------
DEFAULT_TOKEN_COSTS_USD_PER_1K: dict[str, dict[str, float]] = {
    "gemini-2.0-flash":          {"prompt": 0.00010, "completion": 0.00040},
    "gemini-1.5-pro":            {"prompt": 0.00125, "completion": 0.00500},
    "groq/llama3-8b-8192":       {"prompt": 0.00005, "completion": 0.00008},
    "groq/llama3-70b-8192":      {"prompt": 0.00059, "completion": 0.00079},
    "groq/llama-3.3-70b-versatile": {"prompt": 0.00059, "completion": 0.00079},
}

# ---------------------------------------------------------------------------
# Prometheus metric definitions
# ---------------------------------------------------------------------------

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

agent_retry_cost_usd = Histogram(
    "agent_retry_cost_usd",
    "Estimated USD cost of retry LLM calls specifically",
    ["model"],
    buckets=[0.0001, 0.001, 0.01, 0.05, 0.10, 0.25, 0.50, 1.00],
)

agent_total_cost_usd = Histogram(
    "agent_total_cost_usd",
    "Total estimated USD cost per end-to-end agent query (all LLM calls)",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.10, 0.25, 0.50, 1.00],
)


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------

def cost_for_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_table: dict[str, dict[str, float]] | None = None,
) -> float:
    """Return estimated USD cost for a single LLM call."""
    table = cost_table or DEFAULT_TOKEN_COSTS_USD_PER_1K
    entry = table.get(model, {"prompt": 0.0, "completion": 0.0})
    return (prompt_tokens / 1000) * entry["prompt"] + (completion_tokens / 1000) * entry["completion"]


def record_llm_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    is_retry: bool = False,
    cost_table: dict[str, dict[str, float]] | None = None,
) -> float:
    """
    Record token counts and cost for one LLM call.

    Updates:
      - llm_tokens_total (always)
      - llm_request_cost_usd (always)
      - agent_retry_tokens_total + agent_retry_cost_usd (when is_retry=True)

    Returns the computed USD cost so callers can accumulate per-query totals.
    """
    llm_tokens_total.labels(model=model, token_type="prompt").inc(prompt_tokens)
    llm_tokens_total.labels(model=model, token_type="completion").inc(completion_tokens)

    cost = cost_for_call(model, prompt_tokens, completion_tokens, cost_table)
    llm_request_cost_usd.labels(model=model).observe(cost)

    if is_retry:
        agent_retry_tokens_total.labels(model=model).inc(prompt_tokens + completion_tokens)
        agent_retry_cost_usd.labels(model=model).observe(cost)

    return cost


def observe_query_cost(total_usd: float) -> None:
    """Emit the total per-query cost histogram observation (call once per query at terminal node)."""
    agent_total_cost_usd.observe(total_usd)


# ---------------------------------------------------------------------------
# LiteLLM callback registration
# ---------------------------------------------------------------------------

def _litellm_success_callback(kwargs: dict, response_obj: object, start_time: object, end_time: object) -> None:  # noqa: ARG001
    """LiteLLM success_callback — fires after every successful LLM call."""
    model: str = kwargs.get("model", "unknown")
    usage = getattr(response_obj, "usage", None)
    if usage is None:
        return

    prompt_tokens: int = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens: int = getattr(usage, "completion_tokens", 0) or 0

    # We don't know at callback time whether this is a retry; graph.py handles
    # retry-specific counters directly via record_llm_call(is_retry=True).
    # Here we only record the per-call token and cost totals.
    record_llm_call(model, prompt_tokens, completion_tokens, is_retry=False)


def register_litellm_callback() -> None:
    """Wire the cost callback into LiteLLM. Call once at application startup."""
    import litellm  # local import — avoids circular import at module load

    existing = litellm.success_callback or []
    if _litellm_success_callback not in existing:
        litellm.success_callback = existing + [_litellm_success_callback]
