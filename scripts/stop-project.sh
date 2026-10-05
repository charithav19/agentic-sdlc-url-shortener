#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

echo ""
echo "Stopping Agentic SDLC project..."
echo ""

stop_process() {
  local name="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    echo "$name: not running"
    return
  fi

  PID="$(cat "$pid_file")"

  if kill -0 "$PID" >/dev/null 2>&1; then
    echo "Stopping $name (PID $PID)..."
    kill "$PID" || true

    for _ in {1..15}; do
      if ! kill -0 "$PID" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done

    if kill -0 "$PID" >/dev/null 2>&1; then
      echo "$name did not stop gracefully. Terminating..."
      kill -9 "$PID" || true
    fi
  fi

  rm -f "$pid_file"

  echo "✓ $name stopped"
}

stop_process \
  "Agentic Orchestrator" \
  "$RUN_DIR/orchestrator.pid"

stop_process \
  "URL Shortener" \
  "$RUN_DIR/url-shortener.pid"

echo ""
echo "Stopping PostgreSQL containers..."

cd "$ROOT_DIR"

docker compose down

echo ""
echo "✓ Project stopped"
echo ""