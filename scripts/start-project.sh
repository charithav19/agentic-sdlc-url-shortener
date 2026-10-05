#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

ORCHESTRATOR_PORT=8000
URL_SHORTENER_PORT=8080

mkdir -p "$RUN_DIR"

echo ""
echo "===================================================="
echo "  Agentic SDLC URL Shortener - Local Startup"
echo "===================================================="
echo ""

cd "$ROOT_DIR"

# --------------------------------------------------
# 1. Validate prerequisites
# --------------------------------------------------

echo "[1/8] Checking prerequisites..."

command -v docker >/dev/null 2>&1 || {
  echo "ERROR: Docker is not installed."
  exit 1
}

command -v uv >/dev/null 2>&1 || {
  echo "ERROR: uv is not installed."
  exit 1
}

command -v curl >/dev/null 2>&1 || {
  echo "ERROR: curl is not installed."
  exit 1
}

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker Desktop is not running."
  echo "Start Docker Desktop and retry."
  exit 1
fi

echo "✓ Prerequisites available"

# --------------------------------------------------
# 2. Load environment
# --------------------------------------------------

echo ""
echo "[2/8] Loading environment..."

if [ ! -f "$ROOT_DIR/.env" ]; then
  echo "ERROR: .env does not exist."
  echo ""
  echo "Create it first:"
  echo "  cp .env.example .env"
  echo ""
  echo "Then configure database passwords and reviewer token."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

echo "✓ Environment loaded"

# --------------------------------------------------
# 3. Configure Java 21
# --------------------------------------------------

echo ""
echo "[3/8] Checking Java 21..."

if [[ "$(uname)" == "Darwin" ]]; then
  if /usr/libexec/java_home -v 21 >/dev/null 2>&1; then
    export JAVA_HOME
    JAVA_HOME=$(/usr/libexec/java_home -v 21)
    export PATH="$JAVA_HOME/bin:$PATH"
  else
    echo "ERROR: JDK 21 is not installed."
    exit 1
  fi
fi

JAVA_VERSION="$(java -version 2>&1 | head -n 1)"

echo "✓ $JAVA_VERSION"

# --------------------------------------------------
# 4. Start PostgreSQL databases
# --------------------------------------------------

echo ""
echo "[4/8] Starting PostgreSQL databases..."

docker compose up -d --wait

echo "✓ PostgreSQL containers started"

echo ""
echo "Checking database health..."

make health

echo "✓ Databases healthy"

# --------------------------------------------------
# 5. Run orchestrator migrations
# --------------------------------------------------

echo ""
echo "[5/8] Running FastAPI database migrations..."

cd "$ROOT_DIR/apps/orchestrator"

uv sync --locked >/dev/null

uv run --locked alembic upgrade head

echo "✓ Orchestrator database migrated"

# --------------------------------------------------
# 6. Start FastAPI orchestrator
# --------------------------------------------------

echo ""
echo "[6/8] Starting Agentic SDLC Orchestrator..."

if [ -f "$RUN_DIR/orchestrator.pid" ]; then
  OLD_PID="$(cat "$RUN_DIR/orchestrator.pid")"

  if kill -0 "$OLD_PID" >/dev/null 2>&1; then
    echo "Orchestrator already running with PID $OLD_PID"
  else
    rm -f "$RUN_DIR/orchestrator.pid"
  fi
fi

if [ ! -f "$RUN_DIR/orchestrator.pid" ]; then
  nohup uv run --locked uvicorn app.main:app \
    --host 127.0.0.1 \
    --port "$ORCHESTRATOR_PORT" \
    > "$RUN_DIR/orchestrator.log" 2>&1 &

  ORCHESTRATOR_PID=$!

  echo "$ORCHESTRATOR_PID" > "$RUN_DIR/orchestrator.pid"

  echo "Orchestrator PID: $ORCHESTRATOR_PID"
fi

# --------------------------------------------------
# 7. Start Spring Boot URL shortener
# --------------------------------------------------

echo ""
echo "[7/8] Starting Spring Boot URL Shortener..."

cd "$ROOT_DIR/apps/url-shortener"

if [ -f "$RUN_DIR/url-shortener.pid" ]; then
  OLD_PID="$(cat "$RUN_DIR/url-shortener.pid")"

  if kill -0 "$OLD_PID" >/dev/null 2>&1; then
    echo "URL Shortener already running with PID $OLD_PID"
  else
    rm -f "$RUN_DIR/url-shortener.pid"
  fi
fi

if [ ! -f "$RUN_DIR/url-shortener.pid" ]; then
  nohup ./mvnw spring-boot:run \
    > "$RUN_DIR/url-shortener.log" 2>&1 &

  URL_PID=$!

  echo "$URL_PID" > "$RUN_DIR/url-shortener.pid"

  echo "URL Shortener PID: $URL_PID"
fi

# --------------------------------------------------
# 8. Wait for applications
# --------------------------------------------------

echo ""
echo "[8/8] Waiting for applications..."

wait_for_service() {
  local name="$1"
  local url="$2"
  local attempts=60

  printf "Waiting for %s " "$name"

  for ((i=1; i<=attempts; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo ""
      echo "✓ $name ready"
      return 0
    fi

    printf "."
    sleep 2
  done

  echo ""
  echo "ERROR: $name did not become ready."
  return 1
}

wait_for_service \
  "Agentic Orchestrator" \
  "http://127.0.0.1:${ORCHESTRATOR_PORT}/health"

wait_for_service \
  "URL Shortener" \
  "http://127.0.0.1:${URL_SHORTENER_PORT}/actuator/health"

echo ""
echo "===================================================="
echo "              PROJECT READY"
echo "===================================================="
echo ""
echo "Agentic Orchestrator:"
echo "  API:     http://localhost:8000"
echo "  Swagger: http://localhost:8000/docs"
echo "  Health:  http://localhost:8000/health"
echo ""
echo "URL Shortener:"
echo "  API:     http://localhost:8080"
echo "  Swagger: http://localhost:8080/swagger-ui.html"
echo "  Health:  http://localhost:8080/actuator/health"
echo ""
echo "PostgreSQL:"
echo "  URL DB:          localhost:${URL_DB_PORT:-5433}"
echo "  Orchestrator DB: localhost:${ORCHESTRATOR_DB_PORT:-5434}"
echo ""
echo "Logs:"
echo "  $RUN_DIR/orchestrator.log"
echo "  $RUN_DIR/url-shortener.log"
echo ""
echo "To watch logs:"
echo "  tail -f .run/orchestrator.log"
echo "  tail -f .run/url-shortener.log"
echo ""
echo "To stop:"
echo "  ./scripts/stop-project.sh"
echo ""