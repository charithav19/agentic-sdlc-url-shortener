"""Bootstrap fixtures; application database ownership begins in Phase 5."""

import os
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import app


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-postgres", action="store_true", help="Fail rather than skip without a test DSN"
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def postgres_connection(request: pytest.FixtureRequest) -> Iterator[psycopg.Connection]:
    dsn = os.environ.get("POSTGRES_TEST_DSN")
    if not dsn:
        if request.config.getoption("--require-postgres"):
            pytest.fail("POSTGRES_TEST_DSN is required; use make test-db")
        pytest.skip("PostgreSQL fixture not configured; use make test-db")
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        yield connection
