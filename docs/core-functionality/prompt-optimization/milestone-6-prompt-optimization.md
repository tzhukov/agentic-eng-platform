# Milestone 6: Optimization & Prompt Refinement

## Overview

Goal: Improve the robustness and reliability of the agent's code-generation loop
through structured prompting, strict output parsing, and context-aware retrieval
injection. All changes are isolated to `src/agent/graph.py` and `tests/test_graph.py`.

---

## Work Performed

### M6a — Chain-of-Thought RCA in Retry Prompts ✅

On every retry (when `retry_count > 0` and `error_logs` is non-empty), the system
prompt now injects a mandatory **Root Cause Analysis** block:

```
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
```

The extracted reasoning is stored in the new `rca` field of `AgentState` and
threaded into subsequent retries so the model builds on prior analysis rather
than starting fresh.

### M6b — Explicit Sandbox Environment Constraints ✅

A `SANDBOX_ENV_SPEC` constant is injected into **every** system prompt (not just
retries). It specifies:

- Runtime: Python 3.12 in an isolated E2B micro-VM
- No internet access; no filesystem persistence
- Pre-installed packages whitelist: `numpy`, `pandas`, `requests`, `math`, `qdrant-client`
- Forbidden imports: `psycopg2`, `langchain`, `litellm`, `torch`, `tensorflow`
- Execution timeout: 30 s; Memory limit: 512 MB

This eliminates the previous ambiguity where the LLM could attempt unavailable
imports on first attempt, forcing a retry that should have been preventable.

### M6c — Strict XML Output Parsing with Graceful Fallback ✅

The LLM is now instructed to wrap its response in:

```xml
<solution>
  <reasoning>…</reasoning>
  <code>…</code>
</solution>
```

Two helpers were added to `graph.py`:

| Function | Purpose |
|---|---|
| `_extract_xml_tag(text, tag)` | Regex-based XML extraction, returns `""` if absent |
| `_parse_llm_response(raw)` | Extracts `(reasoning, code)`; falls back to ` ```python ` fence stripping, then raw text |

The fallback chain ensures the agent remains functional even if an LLM model
ignores the XML format directive.

### M6d — Contextual Weighting via Ranked Context Injection ✅

Qdrant search results now carry their relevance `score` through `AgentState`
(new field `context_scores: List[float]`). A new helper `_build_weighted_context`
sorts context chunks by score descending and annotates each with its rank and score:

```
[Context 1 — relevance 0.921]
…most relevant chunk…

[Context 2 — relevance 0.734]
…second chunk…
```

The system prompt instructs the model to prefer higher-ranked sources. This anchors
generation to the most relevant documentation and reduces hallucination.

---

## New State Fields

| Field | Type | Purpose |
|---|---|---|
| `context_scores` | `List[float]` | Relevance scores from Qdrant, parallel to `context` |
| `rca` | `str` | Chain-of-Thought root-cause analysis from last LLM response |

---

## Proof of Completion

### Test Results — `pytest tests/test_graph.py -v`

```
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.6.0

tests/test_graph.py::TestXmlParsing::test_extract_xml_tag_missing_returns_empty PASSED [  9%]
tests/test_graph.py::TestXmlParsing::test_extract_xml_tag_present            PASSED [ 18%]
tests/test_graph.py::TestXmlParsing::test_parse_llm_response_fallback_fence  PASSED [ 27%]
tests/test_graph.py::TestXmlParsing::test_parse_llm_response_fallback_raw    PASSED [ 36%]
tests/test_graph.py::TestXmlParsing::test_parse_llm_response_full_xml        PASSED [ 45%]
tests/test_graph.py::TestContextualWeighting::test_context_rank_labels       PASSED [ 54%]
tests/test_graph.py::TestContextualWeighting::test_context_sorted_by_score_descending PASSED [ 63%]
tests/test_graph.py::TestContextualWeighting::test_empty_context             PASSED [ 72%]
tests/test_graph.py::TestAgentGraph::test_graph_fallback_fence_parsing       PASSED [ 81%]
tests/test_graph.py::TestAgentGraph::test_graph_retry_path                   PASSED [ 90%]
tests/test_graph.py::TestAgentGraph::test_graph_success_path                 PASSED [100%]

======================== 11 passed, 1 warning in 13.27s ========================
```

**11 tests, 11 passed, 0 failures.**

Test coverage per M6 item:

| M6 Item | Test(s) |
|---|---|
| M6a — CoT RCA | `test_graph_retry_path` (asserts `rca` populated), `test_graph_success_path` (asserts `rca` = reasoning tag) |
| M6b — Sandbox constraints | Covered implicitly by `test_graph_success_path` (constraints appear in prompt; mock verifies invocation) |
| M6c — XML parsing | `TestXmlParsing` (5 tests: full XML, fence fallback, raw fallback, tag extraction present/absent) |
| M6c — Fallback integration | `test_graph_fallback_fence_parsing` (full graph run with fence-only LLM response) |
| M6d — Contextual weighting | `TestContextualWeighting` (3 tests: empty, sort order, rank labels); `test_graph_success_path` asserts `context_scores` in state |

---

## Files Changed

| File | Change |
|---|---|
| [`src/agent/graph.py`](../../src/agent/graph.py) | Added `SANDBOX_ENV_SPEC`, `OUTPUT_FORMAT_SPEC`, `_extract_xml_tag`, `_parse_llm_response`, `_build_weighted_context`; updated `AgentState` with `context_scores`/`rca`; rewrote `generate_solution` prompt; updated `retrieve_docs` to return scores |
| [`tests/test_graph.py`](../../tests/test_graph.py) | Added `TestXmlParsing` (5 tests), `TestContextualWeighting` (3 tests); updated existing flow tests for new state fields |
