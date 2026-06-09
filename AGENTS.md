# General AI Agent Guidelines
- **DO NOT MAKE THINGS UP.**
- **Documentation:** For every new feature, create a corresponding folder in the `docs/` directory.
- **Verification:** In every milestone, for every feature being implemented, add a document to its feature folder outlining the work performed. This document must include **proof of completion**, such as test results, logs, or screenshots.

## Platform Engineering & Deployment Guidelines
- **Probes Match Behavior:** Readiness/liveness probes must accurately reflect application state. For non-HTTP services or batch scripts, use `exec` probes (e.g., `["true"]`) or disable them, rather than relying on default `httpGet` handlers that will fail.
- **Local Dev vs. Production:** For local `kind` clusters, scale down high-availability dependencies (e.g., ClickHouse, ZooKeeper) to 1 replica to ensure stability and reduce resource contention.
- **CI/CD Reliability:** Do not rely solely on implicit `tilt` or Helm readiness probes to determine system health for complex multi-service stacks; implement explicit, deterministic health-check scripts that poll APIs with defined timeouts.
- **Automated Cluster Testing:** All new features must include an end-to-end (E2E) test in `tests/e2e/` that validates functionality against the running Kubernetes cluster. Use the orchestrator script `scripts/run-tests.sh` to run the full suite (unit, integration, and E2E) before submitting any PRs.

# Python AI Agent Guidelines

You are an AI coding assistant operating in a modern Python (3.12+) environment. Your objective is to write robust, type-safe, and observable code for backend AI systems.

## Language Features & Standards
- **Strict Typing:** Use Python's type hinting system extensively. Use `Pydantic` for data validation, settings management, and structured LLM outputs.
- **Asynchronous Programming:** Use `asyncio` for non-blocking I/O, especially when calling LLM APIs or performing network operations.
- **Dependency Management:** Use `Poetry` or `uv` for reproducible environment and dependency management.
- **Modern Syntax:** Leverage f-strings, structural pattern matching (Python 3.10+), and advanced typing features like `Annotated` and `TypeAlias`.

## Architecture & Patterns (Agentic Focus)
- **Stateful Orchestration:** Use `LangGraph` to model agents as state machines. Prioritize explicit state transitions and clear cycle management.
- **LLM Gateway:** Use `LiteLLM` for a unified interface to multiple LLM providers. Ensure configuration is managed via environment variables and K8s secrets.
- **Reliability:** Treat LLMs as non-deterministic microservices. Implement robust retry logic, fallbacks, and error handling for code execution tasks.
- **Security:** Always execute agent-generated code in isolated environments (e.g., E2B Sandbox). Never run untrusted code on the host system.

## Observability & Platform Engineering
- **Tracing:** Integrate `LangFuse` (via OpenInference) for full-lifecycle tracing of agent thoughts, tool calls, and LLM interactions.
- **Cloud-Native:** Design for Kubernetes. Ensure the application handles signals for graceful shutdown and provides `/healthz` and `/readyz` endpoints.
- **Telemetry:** Log structured data for easier analysis in centralized logging systems.

## Testing
- **Framework:** Use `pytest` as the primary testing framework.
- **Mocking:** Use `unittest.mock` or specialized mocking libraries (like `respx` for HTTP) to isolate unit tests.
- **Deterministic Testing:** Use **MockLLM** to verify graph logic and state transitions without incurring API costs or dealing with non-determinism during unit testing.
- **Evaluations:** Implement "Eval" tests that assert specific behavioral qualities of the agent's output using deterministic checks or LLM-as-a-judge.

# Go AI Agent Guidelines

You are an AI coding assistant operating in a modern Go (1.26+) environment. Your objective is to write clean, maintainable, and idiomatic Go code tailored for high-performance backend systems and control plane services. 

## Language Features & 1.26 Idioms
- **Pointer Instantiation:** Use the 1.26 `new(expr)` built-in to instantiate pointers to literals directly, eliminating the need for custom pointer helper functions.
  - *Good:* `timeout := new(int(30))`
  - *Bad:* `t := 30; timeout := &t`
- **Error Unwrapping:** Use the type-safe `errors.AsType` introduced in Go 1.26 instead of the legacy `errors.As`.
  - *Good:* `if connErr, ok := errors.AsType[*net.OpError](err); ok { ... }`
- **Generics:** Use self-referential type constraints when building complex recursive data structures.
- **Routing & Loops:** Rely on standard `net/http` pattern matching (1.22+) and modern loop variable semantics.
- **Logging:** Default to `log/slog` for structured, leveled logging.

## Architecture & Patterns
- **Simplicity First:** Avoid over-engineering. Assume the developer is proficient in Go and values clear, readable logic over clever abstractions.
- **Context:** Always pass `context.Context` as the first parameter for functions that perform I/O or network calls. Ensure context propagation is flawless across API boundaries.
- **Cloud-Native Resilience:** Design services with graceful shutdowns, explicit timeouts, and clear readiness/liveness probes suitable for Kubernetes deployment.

## Concurrency & Memory
- Manage goroutines responsibly. Ensure every goroutine has a clear exit condition to avoid leaks (preventing flags from the 1.26 `goroutineleak` profile).
- Keep variable scopes tight so the compiler can confidently allocate slice backing stores on the stack, taking full advantage of 1.26 compiler optimizations.

## Testing
- Rely strictly on the standard `testing` package.
- Default to table-driven tests for broad coverage of edge cases.
