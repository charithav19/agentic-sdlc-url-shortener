.DEFAULT_GOAL := help

UV ?= uv
PYTHON ?= $(UV) run --project apps/orchestrator --locked python
COMPOSE ?= docker compose
JAVA_APP := apps/url-shortener
PYTHON_APP := apps/orchestrator

.PHONY: help bootstrap build test test-java test-python test-db lint format structure compose-config up down health demo smoke

help:
	@printf '%s\n' 'Phase 1 bootstrap targets:' \
	  '  bootstrap       Install locked Python development dependencies' \
	  '  build           Build Spring Boot JAR and Python wheel/sdist' \
	  '  test            Run Java and Python bootstrap tests (no Docker)' \
	  '  test-db         Check PostgreSQL fixture connectivity (requires Docker)' \
	  '  lint / format   Check / apply pinned Java and Python formatting' \
	  '  structure       Verify monorepo layout and build configuration' \
	  '  compose-config  Validate Compose with example configuration' \
	  '  up / down       Start / stop databases only; down preserves volumes' \
	  '  health          Check database readiness only' \
	  '  demo / smoke    Unavailable until scenario/packaging phases'

bootstrap:
	cd $(PYTHON_APP) && $(UV) sync --locked

build:
	cd $(JAVA_APP) && ./mvnw --batch-mode verify
	cd $(PYTHON_APP) && $(UV) lock --check && $(UV) build --no-sources

test: test-java test-python

test-java:
	cd $(JAVA_APP) && ./mvnw --batch-mode verify

test-python:
	cd $(PYTHON_APP) && $(UV) run --locked python -m pytest -m 'not integration'

test-db:
	UV='$(UV)' scripts/test-postgres.sh

lint:
	cd $(JAVA_APP) && ./mvnw --batch-mode spotless:check
	cd $(PYTHON_APP) && $(UV) run --locked ruff check . ../../scripts/verify-structure.py
	cd $(PYTHON_APP) && $(UV) run --locked ruff format --check . ../../scripts/verify-structure.py

format:
	cd $(JAVA_APP) && ./mvnw --batch-mode spotless:apply
	cd $(PYTHON_APP) && $(UV) run --locked ruff check --fix . ../../scripts/verify-structure.py
	cd $(PYTHON_APP) && $(UV) run --locked ruff format . ../../scripts/verify-structure.py

structure:
	$(PYTHON) scripts/verify-structure.py

compose-config:
	$(COMPOSE) --env-file .env.example config --quiet

up:
	$(COMPOSE) up --detach --wait

down:
	$(COMPOSE) down

health:
	$(COMPOSE) exec -T url-db sh -c 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'
	$(COMPOSE) exec -T orchestrator-db sh -c 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

demo smoke:
	@printf '%s\n' '$@ is not implemented in Phase 1; see IMPLEMENTATION_PLAN.md.' >&2
	@exit 2
