# Milestone 3: The Agent Core (AI Engineering)

## Overview
Goal: Build the LangGraph state machine that orchestrates the self-correction loop.

## Work Performed
- [x] Define `AgentState` and LangGraph structure.
- [x] Integrate `LiteLLM` for model-agnostic generation.
- [x] Implement `RetrieveDocs` node using the Milestone 2 tool.
- [x] Implement `GenerateSolution` node (code generation).
- [x] Implement `ExecuteSandbox` node (integrated with E2B Sandbox).
- [x] Implement `ReflectAndFix` conditional logic (retry loop).

## Proof of Completion
- [x] Unit tests in `tests/test_graph.py` verifying success and retry paths using **MockLLM**.
- [x] Trace of a successful self-correction loop in a live run:
    - **Step 1**: Retrieved 3 context chunks from Qdrant.
    - **Step 2**: Generated code; execution failed with `SyntaxError: unterminated string literal`.
    - **Step 3**: Agent identified the error and generated a fixed script.
    - **Step 4**: Second execution successful (Stdout showing Name, Skills, and Experience).
