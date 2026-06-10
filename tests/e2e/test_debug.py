import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_debug_fail():
    response = client.get("/debug/fail")
    assert response.status_code == 500
    assert response.json()["detail"] == "Debug failure"

def test_debug_slow():
    # Use a small delay for testing
    response = client.get("/debug/slow?delay=0.1")
    assert response.status_code == 200
    assert response.json() == {"status": "slow", "delay": 0.1}

def test_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
