"""PostgreSQL migration and transactional session behavior."""

import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.config import Settings, get_settings
from app.persistence.session import create_session_factory, session_scope


def test_settings_validate_and_mask_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings(db_port=0)
    with pytest.raises(ValidationError):
        Settings(log_level="TRACE")

    settings = Settings(db_password="sensitive:a@b")
    assert settings.database_url.password == "sensitive:a@b"
    assert "sensitive:a@b" not in repr(settings)
    assert "sensitive:a@b" not in str(settings.database_url)


@pytest.mark.integration
def test_clean_alembic_upgrade(
    postgres_connection, postgres_dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = make_url(postgres_dsn).set(drivername="postgresql+psycopg")
    monkeypatch.setenv("ORCHESTRATOR_DB_HOST", url.host or "127.0.0.1")
    monkeypatch.setenv("ORCHESTRATOR_DB_PORT", str(url.port))
    monkeypatch.setenv("ORCHESTRATOR_DB_NAME", url.database or "")
    monkeypatch.setenv("ORCHESTRATOR_DB_USER", url.username or "")
    monkeypatch.setenv("ORCHESTRATOR_DB_PASSWORD", url.password or "")
    get_settings.cache_clear()
    config = Config("alembic.ini")
    engine = create_engine(url)
    try:
        command.upgrade(config, "head")
        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            tables = (
                connection.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
                .scalars()
                .all()
            )
        assert version == "0002_workflow_foundation"
        assert set(tables) == {
            "alembic_version",
            "workflow_runs",
            "stage_runs",
            "artifacts",
            "artifact_lineage",
            "decisions",
            "approvals",
            "audit_events",
        }
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_commits_and_rolls_back(postgres_connection, postgres_dsn: str) -> None:
    postgres_connection.execute("CREATE TABLE phase5_session_probe (id INTEGER PRIMARY KEY)")
    postgres_connection.commit()
    url = make_url(postgres_dsn).set(drivername="postgresql+psycopg")
    engine = create_async_engine(url)
    factory = create_session_factory(engine)
    try:
        async with session_scope(factory) as session:
            await session.execute(text("INSERT INTO phase5_session_probe (id) VALUES (1)"))

        with pytest.raises(RuntimeError, match="force rollback"):
            async with session_scope(factory) as session:
                await session.execute(text("INSERT INTO phase5_session_probe (id) VALUES (2)"))
                raise RuntimeError("force rollback")

        async with session_scope(factory) as session:
            rows = (
                (await session.execute(text("SELECT id FROM phase5_session_probe ORDER BY id")))
                .scalars()
                .all()
            )
        assert rows == [1]
    finally:
        await engine.dispose()
        postgres_connection.execute("DROP TABLE phase5_session_probe")
        postgres_connection.commit()
