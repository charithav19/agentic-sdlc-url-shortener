"""Verify installable ASGI bootstrap, not future workflow functionality."""

import psycopg
import pytest
from fastapi.testclient import TestClient


def test_openapi_is_available_without_business_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Agentic SDLC Orchestrator"
    assert schema["paths"] == {}


def test_api_docs_are_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200


def test_workflows_are_not_implemented(client: TestClient) -> None:
    assert client.post("/api/v1/workflows", json={}).status_code == 404


@pytest.mark.integration
def test_postgres_fixture_connectivity(postgres_connection: psycopg.Connection) -> None:
    row = postgres_connection.execute("SELECT 1, current_database()").fetchone()
    assert row is not None
    assert row[0] == 1
    assert row[1] == "bootstrap_test"
