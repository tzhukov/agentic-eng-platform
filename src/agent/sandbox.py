import os
from e2b_code_interpreter import Sandbox
from typing import Dict, Any

class SandboxExecutor:
    def __init__(self):
        self.api_key = os.getenv("E2B_API_KEY")
        if not self.api_key:
            # We'll allow initialization without a key for testing, 
            # but execution will fail.
            print("Warning: E2B_API_KEY not found in environment.")

    def run_code(self, code: str) -> Dict[str, Any]:
        """
        Executes the provided Python code in an E2B Sandbox.
        Returns a dictionary with 'result', 'stdout', 'stderr', and 'error'.
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "E2B_API_KEY is missing. Code execution skipped.",
                "stdout": "",
                "stderr": ""
            }

        try:
            # Clean up the code if it's wrapped in markdown blocks
            clean_code = code.strip()
            if clean_code.startswith("```python"):
                clean_code = clean_code[9:]
            if clean_code.endswith("```"):
                clean_code = clean_code[:-3]
            clean_code = clean_code.strip()

            with Sandbox.create() as sandbox:
                print(f"--- RUNNING CODE IN E2B SANDBOX ---")
                execution = sandbox.run_code(clean_code)
                
                # Capture outputs
                stdout = "\n".join(execution.logs.stdout)
                stderr = "\n".join(execution.logs.stderr)
                error = execution.error
                
                if error:
                    return {
                        "success": False,
                        "error": f"{error.name}: {error.value}\n{error.traceback}",
                        "stdout": stdout,
                        "stderr": stderr
                    }
                
                return {
                    "success": True,
                    "result": execution.results[0] if execution.results else "No result returned",
                    "stdout": stdout,
                    "stderr": stderr,
                    "error": ""
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Internal Sandbox Error: {str(e)}",
                "stdout": "",
                "stderr": ""
            }

if __name__ == "__main__":
    # Test script
    executor = SandboxExecutor()
    test_code = """
import math
print(f"The square root of 16 is {math.sqrt(16)}")
16 * 2
    """
    print(executor.run_code(test_code))
