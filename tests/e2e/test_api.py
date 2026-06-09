import requests
import pytest

# Tilt port-forwards 8000:8000, so we can hit it locally
API_URL = "http://127.0.0.1:8000"

def test_health_endpoint():
    response = requests.get(f"{API_URL}/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_query_endpoint():
    payload = {"query": "How do I become an AI engineer?"}
    response = requests.post(f"{API_URL}/query", json=payload, timeout=60)
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert data["result"] == "Success"
    assert len(data["stdout"]) > 0
