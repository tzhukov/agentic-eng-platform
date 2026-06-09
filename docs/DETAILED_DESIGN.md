# Detailed Design: Self-Correction Customer Support Agent

## 1. Project Overview
This project builds a production-grade, backend-centric AI agent capable of self-correction. It uses a "state machine" approach to handle complex customer support queries that require code execution.

### Core Objectives
- **Stateful Orchestration**: Explicit control over agent logic and retry loops.
- **Secure Sandbox**: Isolated code execution with detailed error feedback.
- **Cloud-Native Infrastructure**: Local Kubernetes deployment with professional-grade tooling.
- **Automated Validation**: Rigorous testing of non-deterministic AI workflows.
- **Documentation & Verification**:
    - **Feature Docs**: Every new feature must have a dedicated folder in the `docs/` directory.
    - **Milestone Proof**: Every milestone for a feature must include a document outlining the work done and providing proof of completion (test logs, verification steps).

---

## 2. Technical Stack
| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Orchestration** | LangGraph (Python) | State-machine based workflow management. |
| **LLM Gateway** | LiteLLM | Unified routing to local (Ollama) and cloud (Gemini/OpenAI). |
| **Sandbox** | E2B Sandbox | Ephemeral, secure environment for code execution. |
| **Vector DB** | Qdrant | Specialized vector storage for documentation and RAG context. |
| **Observability** | LangFuse | Tracing, evaluations, and cost management. |
| **Infrastructure** | Kind + Tilt + MetalLB | Local Kubernetes development with rapid feedback. |
| **Packaging** | Helm Charts | Standardized K8s manifest management and deployment. |

---

## 3. System Architecture

### 3.1 Agent Workflow (LangGraph)
The agent logic is modeled as a cyclic graph:
1. `retrieve_docs`: Search `Qdrant` for context.
2. `generate_code`: LLM writes a Python solution.
3. `execute_code`: Code runs in E2B; stdout/stderr captured.
4. `reflect_and_fix` (Conditional): If error occurs, feed logs back to `generate_code`.
5. `final_answer`: Return result once successful or max retries reached.

### 3.2 Infrastructure (K8s & DevOps)
- **Bootstrap Script**: `scripts/setup-cluster.sh` to initialize the project-specific Kind cluster and MetalLB.
- **Helm Integration**:
    - Custom Helm chart for the Agent application.
    - Public components (Qdrant, LangFuse) included as **Helm dependencies** with pinned versions in `Chart.yaml`.
- **Tilt**: Live-update and orchestration of Helm deployments for a "hot reload" experience.
- **Security**: Use **K8s Secrets** for all API keys (E2B, LiteLLM, LangFuse) and DB credentials.
- **Configurability**: Support for in-cluster Qdrant or external homelab endpoints via Helm values.

---

## 4. Testing Strategy

### 4.1 Unit Tests (`pytest`)
- **MockLLM**: Use a deterministic mock for LLM responses to test graph node logic and state transitions without API costs.
- Test `Qdrant` retrieval with known document sets (using its local/memory mode).
- Validate E2B wrapper handling of timeout/resource limits.

### 4.2 Integration Tests
- **Graph State Transitions**: Verify that the graph routes correctly on error vs. success.
- **RAG Integrity**: Ensure retrieved context is properly formatted for the prompt.

### 4.3 End-to-End (E2E) / Eval Tests
- **Self-Correction Loop**: Provide a query that *must* fail on the first attempt (e.g., missing import) and verify the agent fixes it.
- **LangFuse Evals**: Use LangFuse to run deterministic "assertions" on agent outputs.

---

## 5. Implementation Milestones

### Milestone 1: K8s Infrastructure (Platform)
- [ ] Create `scripts/setup-cluster.sh` to provision `kind` and `MetalLB`.
- [ ] Bootstrap the project Helm chart with pinned dependencies (Qdrant).
- [ ] Set up `Tiltfile` to manage Helm releases and local development.
- [ ] Implement **K8s Secrets** management for peripheral endpoints.

### Milestone 2: Data & Retrieval (Backend)
- [ ] Configure Qdrant via Helm values.
- [ ] Implement the ingestion pipeline for internal documentation.
- [ ] Create a `RetrieveDocs` tool with semantic search capabilities.

### Milestone 3: The Agent Core (AI Engineering)
- [ ] Define the `LangGraph` state and nodes.
- [ ] Integrate `LiteLLM` for model-agnostic inference.
- [ ] Build the `E2B` sandbox executor node.

### Milestone 4: Self-Correction & Reliability
- [ ] Implement the conditional retry logic in LangGraph.
- [ ] Integrate `LangFuse` for full-trace observability.
- [ ] Write integration tests for the failure/retry loop using **MockLLM**.

### Milestone 5: API & Deployment
- [ ] Wrap the agent in a `FastAPI` service with streaming support.
- [ ] Finalize Helm chart for production-like local deployment.
- [ ] Verify end-to-end functionality with a "broken" test query.

### Milestone 6: Optimization & Prompt Refinement (Post-MVP)
- [ ] Implement Root Cause Analysis (RCA) in retry prompts (Chain-of-Thought).
- [ ] Define explicit sandbox environment constraints in system prompts.
- [ ] Implement strict output parsing (e.g., XML tags) for robustness.
- [ ] Anchor generation to documentation context (Contextual Weighting).

---

## 6. Definition of Done
- [ ] Agent successfully self-corrects a Python execution error in < 3 loops.
- [ ] All components deployed via Helm and observable in a local Kubernetes cluster.
- [ ] Test coverage > 80% for core agent logic.
- [ ] LangFuse traces show complete "thought process" for every request.
