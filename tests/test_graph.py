"""Unit tests for the agent graph (LangGraph state machine).

Tests verify XML parsing, context weighting, and graph flow logic.
All external dependencies are mocked via tests/conftest.py fixtures."""

import pytest
from src.agent.graph import (
    app,
    _extract_xml_tag,
    _parse_llm_response,
    _build_weighted_context,
)


# ---------------------------------------------------------------------------
# Milestone 6 Unit Tests — helpers
# ---------------------------------------------------------------------------


class TestXmlParsing:
    """M6c: Strict XML output parsing with graceful fallback."""

    def test_extract_xml_tag_present(self):
        xml = "<solution><code>print('hi')</code></solution>"
        assert _extract_xml_tag(xml, "code") == "print('hi')"

    def test_extract_xml_tag_missing_returns_empty(self):
        assert _extract_xml_tag("no tags here", "code") == ""

    def test_parse_llm_response_full_xml(self, sample_llm_xml_response):
        reasoning, code = _parse_llm_response(sample_llm_xml_response)
        assert reasoning == "I will print hello."
        assert code == "print('Hello World')"

    def test_parse_llm_response_fallback_fence(self, sample_llm_fence_response):
        """When XML is absent, falls back to stripping ```python fences."""
        reasoning, code = _parse_llm_response(sample_llm_fence_response)
        assert reasoning == ""
        assert code == "print('fence fallback')"

    def test_parse_llm_response_fallback_raw(self):
        """When neither XML nor fences are present, returns raw text as code."""
        raw = "print('bare')"
        _, code = _parse_llm_response(raw)
        assert code == "print('bare')"


class TestContextualWeighting:
    """M6d: Contextual weighting — context ranked by relevance score."""

    def test_empty_context(self):
        result = _build_weighted_context([], [])
        assert "No documentation context" in result

    def test_context_sorted_by_score_descending(self):
        texts = ["low", "high", "mid"]
        scores = [0.3, 0.9, 0.6]
        result = _build_weighted_context(texts, scores)
        # "high" (0.9) should appear before "mid" (0.6) and "low" (0.3)
        assert result.index("[Context 1") < result.index("[Context 2")
        assert "0.900" in result
        idx_high = result.index("high")
        idx_low = result.index("low")
        assert idx_high < idx_low

    def test_context_rank_labels(self):
        texts = ["a", "b"]
        scores = [0.5, 0.8]
        result = _build_weighted_context(texts, scores)
        assert "[Context 1" in result
        assert "[Context 2" in result


# ---------------------------------------------------------------------------
# Graph flow tests
# ---------------------------------------------------------------------------


class TestAgentGraph:
    """Test LangGraph state machine flow using conftest mocks."""

    @pytest.mark.unit
    def test_graph_success_path(
        self,
        mock_groq_api_key,
        mock_retriever,
        mock_litellm_completion,
        mock_e2b_run_code,
        sample_llm_xml_response,
    ):
        """Success path: XML-formatted response parsed correctly, single attempt."""
        mock_litellm_completion.choices[0].message.content = sample_llm_xml_response
        mock_e2b_run_code.return_value = {
            "success": True,
            "stdout": "Hello World\n",
            "stderr": "",
            "result": "Hello World",
        }

        inputs = {"query": "Write a hello world script", "retry_count": 0}
        result = app.invoke(inputs)

        assert result["execution_result"] == "Success"
        assert result["stdout"] == "Hello World\n"
        assert result["retry_count"] == 1
        assert "print" in result["generated_code"]
        assert result["rca"] == "test reasoning"
        assert "context_scores" in result

    @pytest.mark.unit
    def test_graph_retry_path(
        self,
        mock_groq_api_key,
        mock_retriever,
        mock_litellm_completion,
        mock_e2b_run_code,
        sample_error_response,
    ):
        """Retry path: agent exhausts 3 retries, rca accumulates."""
        mock_litellm_completion.return_value.choices[0].message.content = sample_error_response
        mock_e2b_run_code.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "ImportError: No module named 'nonexistent_pkg'",
            "error": "ImportError: No module named 'nonexistent_pkg'",
        }

        inputs = {"query": "Write a failing script", "retry_count": 0}
        result = app.invoke(inputs)

        assert result["execution_result"] == "Error"
        assert result["retry_count"] == 3
        # generated_code should contain the failing import
        assert "nonexistent_pkg" in result.get("generated_code", "")

    @pytest.mark.unit
    def test_graph_fallback_fence_parsing(
        self,
        mock_groq_api_key,
        mock_retriever,
        mock_litellm_completion,
        mock_e2b_run_code,
        sample_llm_fence_response,
    ):
        """M6c fallback: LLM returns markdown fence instead of XML — still works."""
        mock_litellm_completion.choices[0].message.content = sample_llm_fence_response
        mock_e2b_run_code.return_value = {
            "success": True,
            "stdout": "fence fallback\n",
            "stderr": "",
            "result": "fence fallback",
        }

        inputs = {"query": "Write something", "retry_count": 0}
        result = app.invoke(inputs)

        assert result["execution_result"] == "Success"
        assert "print" in result["generated_code"]
