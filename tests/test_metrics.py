"""Unit tests for LLM cost observability metrics.

Tests verify cost calculation, metric recording, and LiteLLM callback wiring.
All metrics are Prometheus Counters/Histograms — no external services needed."""

from unittest.mock import MagicMock

import pytest
import litellm

from src.agent.metrics import (
    cost_for_call,
    record_llm_call,
    observe_query_cost,
    llm_tokens_total,
    llm_request_cost_usd,
    agent_retry_tokens_total,
    agent_retry_cost_usd,
    agent_total_cost_usd,
    _litellm_success_callback,
    register_litellm_callback,
    DEFAULT_TOKEN_COSTS_USD_PER_1K,
)


class TestCostObservability:
    """Tests for cost calculation and metric recording."""

    @pytest.mark.unit
    def test_cost_calculation(self):
        """groq/llama-3.3-70b-versatile: prompt=0.00059, completion=0.00079 per 1k."""
        model = "groq/llama-3.3-70b-versatile"
        cost = cost_for_call(model, prompt_tokens=1000, completion_tokens=1000)
        expected = 0.00059 + 0.00079
        assert abs(cost - expected) < 1e-9

    @pytest.mark.unit
    def test_unknown_model_cost_defaults_zero(self):
        cost = cost_for_call("unknown-model", prompt_tokens=1000, completion_tokens=1000)
        assert cost == 0.0

    @pytest.mark.unit
    def test_cost_callback_records_metrics(self):
        """Simulate LiteLLM callback and verify metric counters increment."""
        model = "groq/llama-3.3-70b-versatile"
        prompt_before = llm_tokens_total.labels(model=model, token_type="prompt")._value.get()
        compl_before = llm_tokens_total.labels(model=model, token_type="completion")._value.get()

        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 250
        mock_response.usage.completion_tokens = 50

        _litellm_success_callback(
            kwargs={"model": model},
            response_obj=mock_response,
            start_time=None,
            end_time=None,
        )

        prompt_after = llm_tokens_total.labels(model=model, token_type="prompt")._value.get()
        compl_after = llm_tokens_total.labels(model=model, token_type="completion")._value.get()

        assert prompt_after - prompt_before == 250
        assert compl_after - compl_before == 50

    @pytest.mark.unit
    def test_retry_metrics_recorded(self):
        """Verify retry-specific metrics increment when is_retry=True."""
        model = "groq/llama-3.3-70b-versatile"
        retry_tokens_before = agent_retry_tokens_total.labels(model=model)._value.get()

        cost = record_llm_call(model, prompt_tokens=100, completion_tokens=50, is_retry=True)
        assert cost > 0.0

        retry_tokens_after = agent_retry_tokens_total.labels(model=model)._value.get()
        assert retry_tokens_after - retry_tokens_before == 150

    @pytest.mark.unit
    def test_observe_query_cost(self):
        """Test total query cost histogram records without error."""
        observe_query_cost(0.015)  # no assertion needed — just verify no exception

    @pytest.mark.unit
    def test_register_litellm_callback(self):
        """Verify callback is registered (idempotent)."""
        register_litellm_callback()
        assert _litellm_success_callback in litellm.success_callback
