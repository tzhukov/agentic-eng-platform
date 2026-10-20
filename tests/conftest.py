"""Shared test fixtures for the agentic-eng-platform.

All fixtures are auto-discovered by pytest. Import them directly in your test files:

    from tests.conftest import mock_qdrant_client, mock_litellm_completion

Or use them as fixture names:

    def test_something(mock_qdrant_client, mock_litellm_completion):
        ...
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Infrastructure mocks — patch at the exact import site in graph.py
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_retriever():
    """Patch the module-level Retriever instance used by graph.py.

    Patches both the Qdrant client and the SentenceTransformer model
    at the import site in src.agent.graph to avoid the module-level
    instantiation problem.
    """
    with patch("src.agent.graph.retriever") as mock:
        mock_client = MagicMock()
        mock_point = MagicMock()
        mock_point.payload = {
            "text": "Sample doc chunk",
            "source": "test.md",
            "chunk_id": 0,
        }
        mock_point.score = 0.9
        mock_query_result = MagicMock()
        mock_query_result.points = [mock_point]
        mock_client.query_points.return_value = mock_query_result
        mock.client = mock_client
        mock.retrieve.return_value = [
            {"text": "Sample doc chunk", "source": "test.md", "score": 0.9}
        ]
        yield mock


@pytest.fixture
def mock_groq_api_key():
    """Ensure GROQ_API_KEY is set so graph.py doesn't raise."""
    with patch.dict("os.environ", {"GROQ_API_KEY": "test-key-123"}):
        yield


@pytest.fixture
def mock_litellm_response():
    """Return a deterministic LiteLLM response object."""
    response = MagicMock()
    response.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    "<solution>"
                    "<reasoning>test reasoning</reasoning>"
                    "<code>print('test')</code>"
                    "</solution>"
                )
            )
        )
    ]
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return response


@pytest.fixture
def mock_litellm_completion(mock_litellm_response):
    """Patch litellm.completion to return mock_litellm_response.

    Yields the mock_patch object so callers can inspect call_count.
    """
    with patch("src.agent.graph.litellm.completion", return_value=mock_litellm_response) as mock:
        yield mock


@pytest.fixture
def mock_e2b_run_code():
    """Patch SandboxExecutor.run_code to return deterministic results."""
    with patch("src.agent.graph.executor.run_code") as mock:
        mock.return_value = {
            "success": True,
            "stdout": "test output\n",
            "stderr": "",
            "result": "test output",
            "error": "",
        }
        yield mock


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_llm_xml_response() -> str:
    """Well-formed XML response from LLM (M6c format)."""
    return (
        "<solution>"
        "<reasoning>I will print hello.</reasoning>"
        "<code>print('Hello World')</code>"
        "</solution>"
    )


@pytest.fixture
def sample_llm_fence_response() -> str:
    """Markdown fence response (graceful fallback format)."""
    return "```python\nprint('fence fallback')\n```"


@pytest.fixture
def sample_docs() -> list[dict]:
    """Sample document chunks for testing RAG context."""
    return [
        {
            "text": "AI engineers build and deploy ML systems end-to-end.",
            "source": "docs/ai-engineer.md",
            "score": 0.95,
        },
        {
            "text": "Python is the primary language for AI development.",
            "source": "docs/python.md",
            "score": 0.72,
        },
        {
            "text": "Machine learning requires understanding of statistics and algorithms.",
            "source": "docs/ml-basics.md",
            "score": 0.58,
        },
    ]


@pytest.fixture
def sample_error_response() -> str:
    """LLM response that generates code which will fail."""
    return (
        "<solution>"
        "<reasoning>I will import a nonexistent module.</reasoning>"
        "<code>import nonexistent_pkg</code>"
        "</solution>"
    )
