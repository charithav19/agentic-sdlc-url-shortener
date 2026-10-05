#!/bin/sh
set -eu

SHORTENER_URL=${URL_BASE_URL:-http://127.0.0.1:${URL_SHORTENER_PORT:-8080}}
ORCHESTRATOR_URL=${ORCHESTRATOR_BASE_URL:-http://127.0.0.1:${ORCHESTRATOR_PORT:-8000}}
ATTEMPTS=${HEALTH_ATTEMPTS:-30}

wait_for_url() {
    name=$1
    url=$2
    attempt=1
    while [ "$attempt" -le "$ATTEMPTS" ]; do
        if curl --fail --silent --show-error --max-time 3 "$url" >/dev/null 2>&1; then
            printf '%s\n' "healthy: $name ($url)"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    printf '%s\n' "unhealthy: $name ($url)" >&2
    return 1
}

docker compose exec -T shortener-db sh -ec 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec -T orchestrator-db sh -ec 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
wait_for_url url-shortener "$SHORTENER_URL/actuator/health/readiness"
wait_for_url orchestrator "$ORCHESTRATOR_URL/health"
