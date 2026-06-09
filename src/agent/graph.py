import operator
from typing import Annotated, List, TypedDict, Union
from langgraph.graph import StateGraph, END
from src.agent.retriever import Retriever
from src.agent.sandbox import SandboxExecutor
from src.agent.config import load_custom_env
import litellm
import os
from prometheus_client import Counter, Histogram

# 1. Define Prometheus Metrics
RETRIES = Counter("agent_retries_total", "Total number of retries")
FAILURES = Counter("agent_failures_total", "Total number of agent failures")
TOOL_DURATION = Histogram("qdrant_operation_duration_seconds", "Qdrant tool latency", ["operation"])

# 2. Initialize Configuration
load_custom_env()

# 2. Configure Observability
# litellm.success_callback = ["langfuse"]
# litellm.failure_callback = ["langfuse"]

# 3. Define Agent State
class AgentState(TypedDict):
    query: str
    context: List[str]
    generated_code: str
    execution_result: str
    stdout: str
    stderr: str
    error_logs: str
    retry_count: int
    messages: Annotated[List[dict], operator.add]

# 4. Initialize Components
retriever = Retriever()
executor = SandboxExecutor()

# 5. Define Nodes
def retrieve_docs(state: AgentState):
    """Fetch relevant documentation from Qdrant."""
    print("\n--- RETRIEVING CONTEXT ---")
    query = state["query"]
    
    with TOOL_DURATION.labels(operation="retrieve").time():
        results = retriever.retrieve(query)
    
    context_texts = [r["text"] for r in results]
    return {"context": context_texts}

def generate_solution(state: AgentState):
    """Generate Python code to solve the user's request."""
    if not os.getenv("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY environment variable is not set.")

    # Increment retry counter metric if this is a retry
    if state.get("retry_count", 0) > 0:
        RETRIES.inc()

    print("--- GENERATING SOLUTION ---")
    query = state["query"]
    context = "\n".join(state["context"])
    error_logs = state.get("error_logs", "")

    system_prompt = f"""You are a senior Python expert. Write a clean, functional Python script to solve the user's request.

### RUNTIME ENVIRONMENT:
- Python 3.12
- Pre-installed: `qdrant-client`, `numpy`, `pandas`, `requests`, `math`
- NO INTERNET ACCESS.
- Do NOT try to install new packages.
- Do NOT use `psycopg2`, `langchain`, or `litellm` inside the script.

### DOCUMENTATION CONTEXT:
{context}

### ERROR HANDLING:
If previous execution failed, you MUST identify the root cause and fix it.
ERROR LOGS:
{error_logs}

### OUTPUT FORMAT:
Output ONLY the Python code, wrapped in ```python ... ``` blocks.
"""

    response = litellm.completion(
        model="groq/llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
    )

    code = response.choices[0].message.content

    return {"generated_code": code, "retry_count": state.get("retry_count", 0) + 1}

def execute_sandbox(state: AgentState):
    """Execute the generated code in a real E2B sandbox."""
    print("--- EXECUTING IN E2B SANDBOX ---")
    code = state["generated_code"]

    result = executor.run_code(code)

    if result["success"]:
        return {
            "execution_result": "Success", 
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "error_logs": ""
        }
    else:
        FAILURES.inc() # Increment failure metric
        return {
            "execution_result": "Error", 
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "error_logs": result["error"]
        }


def should_retry(state: AgentState):
    """Decide whether to retry or finish."""
    if state["execution_result"] == "Success":
        return "end"
    if state["retry_count"] >= 3:
        return "fail"
    return "retry"

# 6. Build the Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("retrieve_docs", retrieve_docs)
workflow.add_node("generate_solution", generate_solution)
workflow.add_node("execute_sandbox", execute_sandbox)

# Define Edges
workflow.set_entry_point("retrieve_docs")
workflow.add_edge("retrieve_docs", "generate_solution")
workflow.add_edge("generate_solution", "execute_sandbox")

# Conditional Edges
workflow.add_conditional_edges(
    "execute_sandbox",
    should_retry,
    {
        "retry": "generate_solution",
        "end": END,
        "fail": END
    }
)

# Compile
app = workflow.compile()

if __name__ == "__main__":
    # Test Run
    inputs = {"query": "Explain how to become an AI engineer.", "retry_count": 0}
    for output in app.stream(inputs):
        for key, value in output.items():
            print(f"\n--- Node '{key}' completed ---")
            if "context" in value:
                print(f"Retrieved {len(value['context'])} context chunks.")
            if "generated_code" in value:
                print(f"Generated Code Sample:\n{value['generated_code'][:100]}...")
            if "execution_result" in value:
                print(f"Result: {value['execution_result']}")
                if value['execution_result'] == "Success":
                    print(f"Stdout:\n{value.get('stdout', 'N/A')}")
                else:
                    print(f"Error Logs: {value.get('error_logs', 'N/A')}")
