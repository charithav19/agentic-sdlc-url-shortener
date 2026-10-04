"""Verify the service remains limited to its Phase 5 API."""

import psycopg
import pytest
from fastapi.testclient import TestClient


def test_openapi_exposes_only_health(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Agentic SDLC Orchestrator"
    assert set(schema["paths"]) == {"/health"}


def test_api_docs_are_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200


def test_workflows_are_not_implemented(client: TestClient) -> None:
    response = client.post("/api/v1/workflows", json={})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    assert response.json()["traceId"] == response.headers["X-Trace-Id"]


@pytest.mark.integration
def test_postgres_fixture_connectivity(postgres_connection: psycopg.Connection) -> None:
    row = postgres_connection.execute("SELECT 1, current_database()").fetchone()
    assert row is not None
    assert row[0] == 1
    assert row[1] == "bootstrap_test"
