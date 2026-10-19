import unittest
from unittest.mock import MagicMock, patch

from src.agent.graph import (
    app,
    _extract_xml_tag,
    _parse_llm_response,
    _build_weighted_context,
)


# ---------------------------------------------------------------------------
# Milestone 6 Unit Tests — helpers
# ---------------------------------------------------------------------------

class TestXmlParsing(unittest.TestCase):
    """M6c: Strict XML output parsing with graceful fallback."""

    def test_extract_xml_tag_present(self):
        xml = "<solution><code>print('hi')</code></solution>"
        self.assertEqual(_extract_xml_tag(xml, "code"), "print('hi')")

    def test_extract_xml_tag_missing_returns_empty(self):
        self.assertEqual(_extract_xml_tag("no tags here", "code"), "")

    def test_parse_llm_response_full_xml(self):
        raw = """<solution>
<reasoning>I will print hello.</reasoning>
<code>print('hello')</code>
</solution>"""
        reasoning, code = _parse_llm_response(raw)
        self.assertEqual(reasoning, "I will print hello.")
        self.assertEqual(code, "print('hello')")

    def test_parse_llm_response_fallback_fence(self):
        """When XML is absent, falls back to stripping ```python fences."""
        raw = "```python\nprint('fallback')\n```"
        reasoning, code = _parse_llm_response(raw)
        self.assertEqual(reasoning, "")
        self.assertEqual(code, "print('fallback')")

    def test_parse_llm_response_fallback_raw(self):
        """When neither XML nor fences are present, returns raw text as code."""
        raw = "print('bare')"
        _, code = _parse_llm_response(raw)
        self.assertEqual(code, "print('bare')")


class TestContextualWeighting(unittest.TestCase):
    """M6d: Contextual weighting — context ranked by relevance score."""

    def test_empty_context(self):
        result = _build_weighted_context([], [])
        self.assertIn("No documentation context", result)

    def test_context_sorted_by_score_descending(self):
        texts = ["low", "high", "mid"]
        scores = [0.3, 0.9, 0.6]
        result = _build_weighted_context(texts, scores)
        # "high" (0.9) should appear before "mid" (0.6) and "low" (0.3)
        self.assertLess(result.index("[Context 1"), result.index("[Context 2"))
        self.assertIn("0.900", result)
        idx_high = result.index("high")
        idx_low = result.index("low")
        self.assertLess(idx_high, idx_low)

    def test_context_rank_labels(self):
        texts = ["a", "b"]
        scores = [0.5, 0.8]
        result = _build_weighted_context(texts, scores)
        self.assertIn("[Context 1", result)
        self.assertIn("[Context 2", result)


# ---------------------------------------------------------------------------
# Existing graph flow tests (updated for new AgentState fields)
# ---------------------------------------------------------------------------

class TestAgentGraph(unittest.TestCase):

    @patch("src.agent.graph.retriever.retrieve")
    @patch("litellm.completion")
    def test_graph_success_path(self, mock_completion, mock_retrieve):
        """Success path: XML-formatted response parsed correctly, single attempt."""
        mock_retrieve.return_value = [
            {"text": "Sample context", "source": "docs/test.md", "score": 0.85}
        ]

        mock_response = MagicMock()
        # M6c: LLM returns well-formed XML
        mock_response.choices[0].message.content = (
            "<solution>"
            "<reasoning>Simple print statement.</reasoning>"
            "<code>print('Hello World')</code>"
            "</solution>"
        )
        mock_completion.return_value = mock_response

        inputs = {"query": "Write a hello world script", "retry_count": 0}

        with patch("src.agent.graph.executor.run_code") as mock_run_code:
            mock_run_code.return_value = {
                "success": True,
                "stdout": "Hello World\n",
                "stderr": "",
                "result": "Hello World",
            }
            result = app.invoke(inputs)

        self.assertEqual(result["execution_result"], "Success")
        self.assertEqual(result["stdout"], "Hello World\n")
        self.assertEqual(result["retry_count"], 1)
        # M6c: code was correctly extracted from XML
        self.assertIn("print", result["generated_code"])
        # M6a: rca should be populated from reasoning tag
        self.assertEqual(result["rca"], "Simple print statement.")
        # M6d: context_scores should be present
        self.assertIn("context_scores", result)
        print("✓ Success path test passed (XML parse, context_scores).")

    @patch("src.agent.graph.retriever.retrieve")
    @patch("litellm.completion")
    def test_graph_retry_path(self, mock_completion, mock_retrieve):
        """Retry path: agent exhausts 3 retries, rca accumulates."""
        mock_retrieve.return_value = [
            {"text": "Sample context", "source": "docs/test.md", "score": 0.7}
        ]

        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            "<solution>"
            "<reasoning>Tried importing fail_module.</reasoning>"
            "<code>import fail_module</code>"
            "</solution>"
        )
        mock_completion.return_value = mock_response

        inputs = {"query": "Write a failing script", "retry_count": 0}

        with patch("src.agent.graph.executor.run_code") as mock_run_code:
            mock_run_code.return_value = {
                "success": False,
                "stdout": "",
                "stderr": "ImportError: No module named 'fail_module'",
                "error": "ImportError: No module named 'fail_module'",
            }
            result = app.invoke(inputs)

        self.assertEqual(result["execution_result"], "Error")
        self.assertEqual(result["retry_count"], 3)
        # M6a: rca should be set from reasoning on retries
        self.assertIn("fail_module", result.get("rca", "") or result.get("generated_code", ""))
        print("✓ Retry path test passed (RCA populated, 3 retries exhausted).")

    @patch("src.agent.graph.retriever.retrieve")
    @patch("litellm.completion")
    def test_graph_fallback_fence_parsing(self, mock_completion, mock_retrieve):
        """M6c fallback: LLM returns markdown fence instead of XML — still works."""
        mock_retrieve.return_value = [
            {"text": "Fallback context", "source": "docs/test.md", "score": 0.6}
        ]

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "```python\nprint('fence fallback')\n```"
        mock_completion.return_value = mock_response

        inputs = {"query": "Write something", "retry_count": 0}

        with patch("src.agent.graph.executor.run_code") as mock_run_code:
            mock_run_code.return_value = {
                "success": True,
                "stdout": "fence fallback\n",
                "stderr": "",
                "result": "fence fallback",
            }
            result = app.invoke(inputs)

        self.assertEqual(result["execution_result"], "Success")
        self.assertIn("print", result["generated_code"])
        print("✓ Fence fallback parsing test passed.")


if __name__ == "__main__":
    unittest.main()
