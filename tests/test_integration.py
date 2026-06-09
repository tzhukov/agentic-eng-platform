import unittest
from unittest.mock import MagicMock, patch
from src.agent.graph import app
import os

class TestAgentIntegration(unittest.TestCase):
    
    @patch("src.agent.graph.retriever.retrieve")
    @patch("litellm.completion")
    @patch("src.agent.graph.executor.run_code")
    def test_self_correction_loop_integration(self, mock_run_code, mock_completion, mock_retrieve):
        """
        Verify that the graph correctly handles a sequence:
        Fail -> Fix -> Success
        """
        # 1. Mock Retrieval
        mock_retrieve.return_value = [{"text": "Context for fixing stuff", "source": "docs/fix.md"}]
        
        # 2. Mock LiteLLM to return code
        # First call: code that fails
        # Second call: code that succeeds
        mock_completion.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content="import nonexistent_pkg\nprint('failing')"))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content="print('success after fix')"))])
        ]
        
        # 3. Mock SandboxExecutor
        # First call: failure
        # Second call: success
        mock_run_code.side_effect = [
            {
                "success": False,
                "stdout": "",
                "stderr": "ModuleNotFoundError: No module named 'nonexistent_pkg'",
                "error": "ModuleNotFoundError: No module named 'nonexistent_pkg'"
            },
            {
                "success": True,
                "stdout": "success after fix\n",
                "stderr": "",
                "result": "success after fix"
            }
        ]
        
        # 4. Run Graph
        inputs = {"query": "Perform a task that might fail", "retry_count": 0}
        result = app.invoke(inputs)
        
        # 5. Assertions
        # It should have called LiteLLM twice (once for initial, once for fix)
        self.assertEqual(mock_completion.call_count, 2)
        # It should have called Sandbox twice
        self.assertEqual(mock_run_code.call_count, 2)
        # Final result should be success
        self.assertEqual(result["execution_result"], "Success")
        self.assertEqual(result["retry_count"], 2)
        self.assertIn("success after fix", result["stdout"])
        print("Integration test: Fail -> Fix -> Success path passed.")

if __name__ == "__main__":
    unittest.main()
