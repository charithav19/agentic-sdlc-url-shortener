.DEFAULT_GOAL := help

UV ?= uv
PYTHON ?= $(UV) run --project apps/orchestrator --locked python
COMPOSE ?= docker compose
JAVA_APP := apps/url-shortener
PYTHON_APP := apps/orchestrator

.PHONY: help bootstrap build test test-java test-python test-db runner-image test-runner lint format structure compose-config up down health demo smoke

help:
	@printf '%s\n' 'Repository targets:' \
	  '  bootstrap       Install locked Python development dependencies' \
	  '  build           Build Spring Boot JAR and Python wheel/sdist' \
	  '  test            Run Java unit/PostgreSQL tests and Python service unit tests' \
	  '  test-db         Run Python PostgreSQL integration tests (requires Docker)' \
	  '  test-runner     Build and security-test isolated engineering runner' \
	  '  lint / format   Check / apply pinned Java and Python formatting' \
	  '  structure       Verify monorepo layout and build configuration' \
	  '  compose-config  Validate Compose with example configuration' \
	  '  up / down       Build and start / stop the complete Compose stack' \
	  '  health          Check both databases and application readiness' \
	  '  demo / smoke    Start and exercise the packaged services'

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

runner-image:
	docker build -t schwab-engineering-runner:local infra/runner

test-runner: runner-image
	cd $(PYTHON_APP) && RUN_RUNNER_TESTS=1 $(UV) run --locked python -m pytest -m runner

lint:
	cd $(JAVA_APP) && ./mvnw --batch-mode spotless:check
	cd $(PYTHON_APP) && $(UV) run --locked ruff check . ../../scripts/verify-structure.py ../../infra/runner/entrypoint.py
	cd $(PYTHON_APP) && $(UV) run --locked ruff format --check . ../../scripts/verify-structure.py ../../infra/runner/entrypoint.py

format:
	cd $(JAVA_APP) && ./mvnw --batch-mode spotless:apply
	cd $(PYTHON_APP) && $(UV) run --locked ruff check --fix . ../../scripts/verify-structure.py ../../infra/runner/entrypoint.py
	cd $(PYTHON_APP) && $(UV) run --locked ruff format . ../../scripts/verify-structure.py ../../infra/runner/entrypoint.py

structure:
	$(PYTHON) scripts/verify-structure.py

compose-config:
	$(COMPOSE) config --quiet

up:
	$(COMPOSE) up --build --detach --wait

down:
	$(COMPOSE) down --remove-orphans

health:
	scripts/health-check.sh

smoke: health
	scripts/smoke-test.sh

demo: up smoke
