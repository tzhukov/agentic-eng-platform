import operator
import re
from typing import Annotated, List, TypedDict

from langgraph.graph import StateGraph, END
from src.agent.retriever import Retriever
from src.agent.sandbox import SandboxExecutor
from src.agent.config import load_custom_env
from src.agent.metrics import record_llm_call, observe_query_cost
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

# ---------------------------------------------------------------------------
# M6: Explicit sandbox environment constraints (injected into every prompt)
# ---------------------------------------------------------------------------
SANDBOX_ENV_SPEC = """\
### SANDBOX ENVIRONMENT (READ CAREFULLY):
- Runtime: Python 3.12 inside an isolated E2B micro-VM.
- NO internet access. Network calls will time out immediately.
- NO filesystem persistence between runs. Write only to /tmp if needed.
- Pre-installed packages ONLY: `numpy`, `pandas`, `requests`, `math`, `qdrant-client`.
- Forbidden imports: `psycopg2`, `langchain`, `litellm`, `torch`, `tensorflow`.
  Any import outside the pre-installed list will raise ModuleNotFoundError.
- Execution timeout: 30 seconds. Long-running loops will be killed.
- Memory limit: 512 MB. Large allocations will raise MemoryError.\
"""

# M6: Strict XML output format spec
OUTPUT_FORMAT_SPEC = """\
### OUTPUT FORMAT (STRICT):
You MUST wrap your response inside XML tags as shown below.
Do NOT include any text outside the tags.

<solution>
<reasoning>
One short paragraph explaining your approach and why it will succeed
in the sandbox constraints above.
</reasoning>
<code>
# Your complete, runnable Python script here.
# No markdown fences inside this tag.
</code>
</solution>\
"""


# 3. Define Agent State
class AgentState(TypedDict):
    query: str
    context: List[str]
    context_scores: List[float]   # M6: relevance scores from Qdrant for weighting
    generated_code: str
    execution_result: str
    stdout: str
    stderr: str
    error_logs: str
    rca: str                      # M6: Chain-of-Thought root-cause from last retry
    retry_count: int
    retry_token_cost_usd: float   # Cost observability: accumulated retry LLM cost
    total_token_cost_usd: float   # Cost observability: accumulated total LLM cost
    messages: Annotated[List[dict], operator.add]


# 4. Initialize Components
retriever = Retriever()
executor = SandboxExecutor()


# ---------------------------------------------------------------------------
# M6: XML parsing helpers
# ---------------------------------------------------------------------------

def _extract_xml_tag(text: str, tag: str) -> str:
    """Extract content between <tag>...</tag>. Returns empty string if absent."""
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_llm_response(raw: str) -> tuple[str, str]:
    """
    Parse <solution><reasoning>...</reasoning><code>...</code></solution>.

    Falls back to stripping ```python fences if XML is absent (graceful degradation).
    Returns (reasoning, code).
    """
    reasoning = _extract_xml_tag(raw, "reasoning")
    code = _extract_xml_tag(raw, "code")

    if not code:
        # Graceful fallback: strip markdown fences
        fence_match = re.search(r"```python\s*(.*?)```", raw, re.DOTALL)
        code = fence_match.group(1).strip() if fence_match else raw.strip()

    return reasoning, code


# ---------------------------------------------------------------------------
# M6: Contextual weighting helper
# ---------------------------------------------------------------------------

def _build_weighted_context(context_texts: List[str], scores: List[float]) -> str:
    """
    Inject context in descending relevance order and annotate each chunk with
    its rank so the model understands which sources are most authoritative.
    """
    if not context_texts:
        return "(No documentation context retrieved.)"

    paired = sorted(zip(scores, context_texts), reverse=True)
    parts: List[str] = []
    for rank, (score, text) in enumerate(paired, start=1):
        parts.append(f"[Context {rank} — relevance {score:.3f}]\n{text}")
    return "\n\n".join(parts)


# 5. Define Nodes

def retrieve_docs(state: AgentState):
    """Fetch relevant documentation from Qdrant, preserving relevance scores."""
    print("\n--- RETRIEVING CONTEXT ---")
    query = state["query"]

    with TOOL_DURATION.labels(operation="retrieve").time():
        results = retriever.retrieve(query)

    # M6: preserve scores for downstream contextual weighting
    context_texts = [r["text"] for r in results]
    context_scores = [r.get("score", 1.0) for r in results]

    return {"context": context_texts, "context_scores": context_scores}


def generate_solution(state: AgentState):
    """
    Generate Python code using:
      - M6a: Chain-of-Thought RCA prompt block on retries
      - M6b: Explicit sandbox environment constraints
      - M6c: Strict XML output format with graceful fallback parser
      - M6d: Contextually-weighted documentation (ranked by relevance score)
    """
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    retry_count = state.get("retry_count", 0)

    if retry_count > 0:
        RETRIES.inc()

    print(f"--- GENERATING SOLUTION (attempt {retry_count + 1}) ---")

    query = state["query"]
    error_logs = state.get("error_logs", "")
    rca_prev = state.get("rca", "")

    # M6d: contextual weighting — inject context ranked by relevance score
    weighted_context = _build_weighted_context(
        state.get("context", []),
        state.get("context_scores", [1.0] * len(state.get("context", []))),
    )

    # M6a: Chain-of-Thought RCA block — injected only on retries
    rca_block = ""
    if retry_count > 0 and error_logs:
        rca_block = f"""\
### ROOT CAUSE ANALYSIS (RCA) — REQUIRED ON RETRY:
The previous attempt failed. Before writing new code you MUST reason through:
1. What exactly caused the error? (quote the relevant line from the logs)
2. Why did your previous code trigger it?
3. What specific change will prevent it?

Capture this reasoning inside the <reasoning> tag in your response.

PREVIOUS ERROR LOGS:
{error_logs}

PREVIOUS RCA (if any):
{rca_prev}
"""

    system_prompt = f"""You are a senior Python expert writing scripts for execution inside a sandboxed VM.

{SANDBOX_ENV_SPEC}

### DOCUMENTATION CONTEXT (ranked by relevance — prefer higher-ranked sources):
{weighted_context}

{rca_block}
{OUTPUT_FORMAT_SPEC}
"""

    response = litellm.completion(
        model="groq/llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
    )

    raw = response.choices[0].message.content
    # M6c: strict XML parse with graceful fallback
    reasoning, code = _parse_llm_response(raw)

    if reasoning:
        print(f"  LLM Reasoning: {reasoning[:120]}...")

    # Cost observability: record tokens and accumulate per-query cost
    model_name = "groq/llama-3.3-70b-versatile"
    usage = getattr(response, "usage", None)
    raw_prompt = getattr(usage, "prompt_tokens", 0) if usage else 0
    raw_compl = getattr(usage, "completion_tokens", 0) if usage else 0
    prompt_tokens = raw_prompt if isinstance(raw_prompt, (int, float)) else 0
    completion_tokens = raw_compl if isinstance(raw_compl, (int, float)) else 0
    is_retry = retry_count > 0
    call_cost = record_llm_call(model_name, int(prompt_tokens), int(completion_tokens), is_retry=is_retry)

    prev_retry_cost = state.get("retry_token_cost_usd", 0.0) or 0.0
    prev_total_cost = state.get("total_token_cost_usd", 0.0) or 0.0

    return {
        "generated_code": code,
        "rca": reasoning,
        "retry_count": retry_count + 1,
        "retry_token_cost_usd": prev_retry_cost + (call_cost if is_retry else 0.0),
        "total_token_cost_usd": prev_total_cost + call_cost,
    }


def execute_sandbox(state: AgentState):
    """Execute the generated code in a real E2B sandbox."""
    print("--- EXECUTING IN E2B SANDBOX ---")
    code = state["generated_code"]

    result = executor.run_code(code)

    if result["success"]:
        # Cost observability: emit per-query total histogram on success
        observe_query_cost(state.get("total_token_cost_usd", 0.0) or 0.0)
        return {
            "execution_result": "Success",
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "error_logs": "",
        }
    else:
        FAILURES.inc()
        return {
            "execution_result": "Error",
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "error_logs": result["error"],
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
        "fail": END,
    },
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
            if "rca" in value and value["rca"]:
                print(f"RCA: {value['rca'][:200]}")
            if "generated_code" in value:
                print(f"Generated Code Sample:\n{value['generated_code'][:100]}...")
            if "execution_result" in value:
                print(f"Result: {value['execution_result']}")
                if value["execution_result"] == "Success":
                    print(f"Stdout:\n{value.get('stdout', 'N/A')}")
                else:
                    print(f"Error Logs: {value.get('error_logs', 'N/A')}")
