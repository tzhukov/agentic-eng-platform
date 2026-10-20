"""Integration tests for the agent graph (fail → fix → success loop).

Uses mocked Qdrant, LiteLLM, and E2B — no real infrastructure required.
Fixtures from tests/conftest.py."""

from unittest.mock import MagicMock

import pytest
from src.agent.graph import app


class TestAgentIntegration:
    """Integration tests for graph state transitions."""

    @pytest.mark.integration
    def test_self_correction_loop(
        self,
        mock_groq_api_key,
        mock_retriever,
        mock_litellm_completion,
        mock_e2b_run_code,
        sample_docs,
    ):
        """
        Verify that the graph correctly handles a sequence:
        Fail → Fix → Success

        The first LLM call returns code that fails.
        The second LLM call returns code that succeeds.
        The graph should call both and return success.
        """
        # First LLM call: code that fails
        # Second LLM call: code that succeeds
        responses = [
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content="import nonexistent_pkg\nprint('failing')")
                    )
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(content="print('success after fix')")
                    )
                ]
            ),
        ]
        mock_litellm_completion.side_effect = responses
        # Also set the return_value mock's content so the mock response is correct
        mock_litellm_completion.return_value.choices[0].message.content = "import nonexistent_pkg\nprint('failing')"

        # First sandbox call: failure
        # Second sandbox call: success
        mock_e2b_run_code.side_effect = [
            {
                "success": False,
                "stdout": "",
                "stderr": "ModuleNotFoundError: No module named 'nonexistent_pkg'",
                "error": "ModuleNotFoundError: No module named 'nonexistent_pkg'",
            },
            {
                "success": True,
                "stdout": "success after fix\n",
                "stderr": "",
                "result": "success after fix",
            },
        ]

        # Run graph
        inputs = {"query": "Perform a task that might fail", "retry_count": 0}
        result = app.invoke(inputs)

        # Verify
        assert mock_litellm_completion.call_count == 2
        assert mock_e2b_run_code.call_count == 2
        assert result["execution_result"] == "Success"
        assert result["retry_count"] == 2
        assert "success after fix" in result["stdout"]
