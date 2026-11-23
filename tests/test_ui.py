import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_serve_index():
    """Test that GET / returns the HTML UI successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Max Clipper" in response.text
    assert "<html" in response.text

def test_api_clips_endpoint():
    """Test that GET /api/clips returns JSON with clips list."""
    response = client.get("/api/clips")
    assert response.status_code == 200
    data = response.json()
    assert "clips" in data
