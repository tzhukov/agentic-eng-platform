# Self-Correction Customer Support Agent

This project implements a production-grade, self-correcting AI support agent using LangGraph, LiteLLM, Qdrant, and E2B. Designed with platform engineering principles, it runs on Kubernetes and is fully observable via a local LangFuse instance.

## Quick Start

### 1. Environment Setup

#### Bootstrap
```bash
# One-command setup (installs Poetry + all deps)
./scripts/dev-setup.sh
```

#### Prerequisites
Ensure you have `kind`, `helm`, `tilt`, and `poetry` installed.

Create a `.env` file in the root with the following format:
```toml
[model.groq]
api_key = "your-groq-api-key"

[model.google]
api_key = "your-google-api-key"

[model.e2b]
E2B_API_KEY = "your-e2b-api-key"

[observability.langfuse]
public_key = "pk-lf-dev-123456789"
secret_key = "sk-lf-dev-123456789"
host = "http://localhost:3000"
```

### 2. Infrastructure Deployment
Initialize the cluster and deploy the stack:
```bash
# Provision Kind cluster and MetalLB
./scripts/setup-cluster.sh

# Run Tilt to orchestrate Helm charts and local development
tilt up
```

### 3. Run the Agent
The Web UI and API are exposed via the FastAPI service, port-forwarded by Tilt to `http://localhost:8000`.

- **Web UI:** Access the interactive interface at `http://localhost:8000/`.
- **API Endpoint:** Query the agent directly at `http://localhost:8000/query`.

**Example API Query:**
```bash
curl -X POST http://127.0.0.1:8000/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Explain how to become an AI engineer"}'
```

### 4. Testing
Run the automated test suite (Unit, Integration, and E2E):
```bash
./scripts/run-tests.sh
```

## Architecture & Design
For detailed architectural decisions, please refer to:
- [`DETAILED_DESIGN.md`](./DETAILED_DESIGN.md): The project roadmap and HLD.
- [`docs/core-functionality/`](./docs/core-functionality/): Detailed documentation for each milestone.
