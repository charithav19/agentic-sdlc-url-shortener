"""Isolated PostgreSQL fixtures for the orchestrator service."""

import os
import uuid
from collections.abc import AsyncIterator, Iterator

import psycopg
import pytest
import pytest_asyncio
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.main import app
from app.persistence.session import create_session_factory


@pytest.fixture
def agent_context():
    from app.agents.contracts import AgentContext, FileSnapshot, Snapshot

    return AgentContext(
        workflow_id=uuid.UUID(int=1),
        stage_run_id=uuid.UUID(int=2),
        trace_id=uuid.UUID(int=3),
        generation=1,
        attempt=1,
        requirement="Create an HTTP URL shortener.",
        artifacts=(Snapshot(name="requirement-v1", version=1, content="HTTP links"),),
        files=(FileSnapshot(name="src/app.py", version=1, content="return 302"),),
    )


@pytest.fixture
def agent_provider():
    from app.agents.fake_provider import FakeAgentProvider
    from tests.agent_fixtures import OUTPUTS

    return FakeAgentProvider(OUTPUTS)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-postgres", action="store_true", help="Fail rather than skip without a test DSN"
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def postgres_dsn(request: pytest.FixtureRequest) -> str:
    dsn = os.environ.get("POSTGRES_TEST_DSN")
    if not dsn:
        if request.config.getoption("--require-postgres"):
            pytest.fail("POSTGRES_TEST_DSN is required; use make test-db")
        pytest.skip("PostgreSQL fixture not configured; use make test-db")
    return dsn


@pytest.fixture
def postgres_connection(postgres_dsn: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(postgres_dsn, connect_timeout=5) as connection:
        yield connection


@pytest_asyncio.fixture
async def phase6_factory(
    postgres_dsn: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = make_url(postgres_dsn).set(drivername="postgresql+psycopg")
    migration_engine = create_engine(url)
    try:
        with migration_engine.begin() as connection:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        migration_engine.dispose()
    engine = create_async_engine(url)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()
