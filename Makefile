BASE_URL ?= http://127.0.0.1:8000
PROMETHEUS_URL ?= http://127.0.0.1:9090
GRAFANA_URL ?= http://127.0.0.1:3001
GRAFANA_PASS ?= admin
ALERTMANAGER_URL ?= http://127.0.0.1:9093
QDRANT_URL ?= http://172.18.255.200:6333

.PHONY: test test-unit test-e2e test-metrics handoff-check dev clean help

help: ## Show this help menu
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

test: ## Run complete test suite (unit, integration, and E2E)
	@./scripts/run-tests.sh

test-unit: ## Run unit tests (graph logic and cost metrics)
	@pytest tests/test_graph.py tests/test_metrics.py -v

test-metrics: ## Run cost observability metrics tests
	@pytest tests/test_metrics.py -v

test-e2e: ## Run E2E cluster tests
	@pytest tests/e2e/ -v

handoff-check: ## Validate all system invariants and observability endpoints
	@BASE_URL=$(BASE_URL) \
	 PROMETHEUS_URL=$(PROMETHEUS_URL) \
	 GRAFANA_URL=$(GRAFANA_URL) \
	 GRAFANA_PASS=$(GRAFANA_PASS) \
	 ALERTMANAGER_URL=$(ALERTMANAGER_URL) \
	 QDRANT_URL=$(QDRANT_URL) \
	 ./scripts/handoff-check.sh

dev: ## Launch Tilt dev environment
	@tilt up

clean: ## Clean python bytecode and test caches
	@find . -name "*.pyc" -delete && find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache
