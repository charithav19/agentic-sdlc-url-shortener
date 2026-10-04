"""Readiness probes must reflect PostgreSQL state without leaking configuration."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.dependencies import get_engine
from app.config import get_settings
from app.main import app


def test_unavailable_database_returns_503_without_secrets(client: TestClient) -> None:
    engine = create_async_engine(
        "postgresql+psycopg://probe:secret-value@127.0.0.1:1/unavailable",
        connect_args={"connect_timeout": 1},
    )
    app.dependency_overrides[get_engine] = lambda: engine
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "HTTP_ERROR",
        "message": "Database unavailable",
    }
    assert response.json()["traceId"] == response.headers["X-Trace-Id"]
    assert "secret-value" not in response.text


@pytest.mark.integration
def test_healthy_database_returns_200(
    postgres_connection, postgres_dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    dsn = make_url(postgres_dsn)
    monkeypatch.setenv("ORCHESTRATOR_DB_HOST", dsn.host or "127.0.0.1")
    monkeypatch.setenv("ORCHESTRATOR_DB_PORT", str(dsn.port))
    monkeypatch.setenv("ORCHESTRATOR_DB_NAME", dsn.database or "")
    monkeypatch.setenv("ORCHESTRATOR_DB_USER", dsn.username or "")
    monkeypatch.setenv("ORCHESTRATOR_DB_PASSWORD", dsn.password or "")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}
    assert response.headers["X-Trace-Id"]
