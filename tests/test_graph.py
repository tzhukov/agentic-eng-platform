import unittest
from unittest.mock import MagicMock, patch
from src.agent.graph import app

class TestAgentGraph(unittest.TestCase):
    
    @patch("src.agent.graph.retriever.retrieve")
    @patch("litellm.completion")
    def test_graph_success_path(self, mock_completion, mock_retrieve):
        # 1. Setup Mocks
        mock_retrieve.return_value = [{"text": "Sample context", "source": "docs/test.md"}]
        
        # Mock LiteLLM response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "print('Hello World')"
        mock_completion.return_value = mock_response
        
        # 2. Run Graph
        inputs = {"query": "Write a hello world script", "retry_count": 0}
        
        # We need to mock SandboxExecutor.run_code since it's now used in the graph
        with patch("src.agent.graph.executor.run_code") as mock_run_code:
            mock_run_code.return_value = {
                "success": True,
                "stdout": "Hello World\n",
                "stderr": "",
                "result": "Hello World"
            }
            result = app.invoke(inputs)
        
        # 3. Assertions
        self.assertEqual(result["execution_result"], "Success")
        self.assertEqual(result["stdout"], "Hello World\n")
        self.assertEqual(result["retry_count"], 1)
        self.assertIn("print", result["generated_code"])
        print("Success path test passed.")

    @patch("src.agent.graph.retriever.retrieve")
    @patch("litellm.completion")
    def test_graph_retry_path(self, mock_completion, mock_retrieve):
        # 1. Setup Mocks
        mock_retrieve.return_value = [{"text": "Sample context", "source": "docs/test.md"}]
        
        # Mock LiteLLM to return code that triggers our mock 'fail' logic
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "import fail_module"
        mock_completion.return_value = mock_response
        
        # 2. Run Graph
        # We need to limit recursion or it might loop forever in a test
        inputs = {"query": "Write a failing script", "retry_count": 0}
        
        # Mock SandboxExecutor to return failure
        with patch("src.agent.graph.executor.run_code") as mock_run_code:
            mock_run_code.return_value = {
                "success": False,
                "stdout": "",
                "stderr": "ImportError: No module named 'fail_module'",
                "error": "ImportError: No module named 'fail_module'"
            }
            result = app.invoke(inputs)
        
        # 3. Assertions
        self.assertEqual(result["execution_result"], "Error")
        self.assertEqual(result["retry_count"], 3)
        print("Retry path test passed.")

if __name__ == "__main__":
    unittest.main()
