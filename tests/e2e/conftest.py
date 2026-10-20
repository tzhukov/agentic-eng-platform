"""E2E test fixtures — require a running cluster (Tilt).

These fixtures are session-scoped to avoid repeated HTTP setup.
If the cluster is not ready, tests using these fixtures will be skipped."""

from __future__ import annotations

import time

import pytest
import requests

API_URL = "http://127.0.0.1:8000"


@pytest.fixture(scope="session")
def api_client():
    """Session-scoped requests session for E2E tests.

    Waits up to 60 seconds for the API to become healthy before yielding.
    Skips all tests if the cluster is not available.
    """
    session = requests.Session()

    for attempt in range(60):
        try:
            resp = session.get(f"{API_URL}/healthz", timeout=2)
            if resp.status_code == 200:
                return session
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(1)

    pytest.skip("API not ready at {API_URL} — is Tilt running?")


@pytest.fixture(scope="session")
def query_endpoint(api_client: requests.Session) -> str:
    """Return the full query endpoint URL."""
    return f"{API_URL}/query"


@pytest.fixture(scope="session")
def metrics_endpoint(api_client: requests.Session) -> str:
    """Return the full metrics endpoint URL."""
    return f"{API_URL}/metrics"


@pytest.fixture(scope="session")
def debug_fail_endpoint(api_client: requests.Session) -> str:
    """Return the debug fail endpoint URL."""
    return f"{API_URL}/debug/fail"


@pytest.fixture(scope="session")
def debug_slow_endpoint(api_client: requests.Session) -> str:
    """Return the debug slow endpoint URL with default delay."""
    return f"{API_URL}/debug/slow?delay=5"
