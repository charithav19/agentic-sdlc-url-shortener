# syntax=docker/dockerfile:1.7

FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /opt/orchestrator

RUN pip install uv==0.11.8
COPY apps/orchestrator/pyproject.toml apps/orchestrator/uv.lock apps/orchestrator/README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY apps/orchestrator/app/ app/
COPY apps/orchestrator/config/ config/
COPY scenarios/ /scenarios/
COPY scenarios/ app/resources/scenarios/
RUN uv sync --locked --no-dev

FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime
ENV PATH="/opt/orchestrator/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 orchestrator \
    && useradd --system --uid 10001 --gid orchestrator --home-dir /opt/orchestrator --shell /usr/sbin/nologin orchestrator \
    && mkdir -p /opt/orchestrator /workspaces \
    && chown orchestrator:orchestrator /opt/orchestrator /workspaces

WORKDIR /opt/orchestrator
COPY --from=build --chown=orchestrator:orchestrator /opt/orchestrator/.venv .venv
COPY --from=build --chown=orchestrator:orchestrator /opt/orchestrator/app app
COPY --from=build --chown=orchestrator:orchestrator /opt/orchestrator/config config
COPY --chown=orchestrator:orchestrator apps/orchestrator/alembic alembic
COPY --chown=orchestrator:orchestrator apps/orchestrator/alembic.ini ./

USER orchestrator
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=18 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2).read()" || exit 1
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
