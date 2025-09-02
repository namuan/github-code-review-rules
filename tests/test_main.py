"""Tests for main application setup."""

from fastapi.testclient import TestClient

from github_pr_rules_analyzer.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_health_check() -> None:
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "version" in data


def test_database_info() -> None:
    """Test the database info endpoint."""
    response = client.get("/database-info")
    assert response.status_code == 200
    data = response.json()
    assert "database_url" in data
    assert "driver" in data


def test_api_docs() -> None:
    """Test that API docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_redoc() -> None:
    """Test that ReDoc is accessible."""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
