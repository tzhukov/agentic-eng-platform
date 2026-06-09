# Milestone 5: API & Deployment

## Overview
Goal: Expose the agent via a FastAPI service and containerize the application for Kubernetes deployment.

## Work Performed
- [x] Create `src/api/main.py` (FastAPI wrapper).
- [x] Create `Dockerfile` for the Python agent.
- [x] Update Helm chart to deploy the agent application and expose port 8000.
- [x] Configure Tilt to build (`docker_build`) and deploy (`helm`) the agent container.

## Proof of Completion
- [x] API endpoint (`/query`) successfully returns agent output and generated code.
- [x] Deployment status: `tilt ci` passed, and all infrastructure pods (including ClickHouse) are `1/1 Running` and stable in Kind.
- [x] End-to-end integration test: FastAPI container is consuming the local observability stack and returning agent predictions, with traces being delivered to the local LangFuse instance.
