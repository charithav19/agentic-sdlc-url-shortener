#!/bin/sh
# Ephemeral connectivity fixture only; never touches Compose volumes.
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
uv_bin=${UV:-uv}
image=postgres:17.7-alpine@sha256:bb377b7239d2774ac8cc76f481596ce96c5a6b5e9d141f6d0a0ee371a6e7c0f2
container_id=
cleanup() {
    if [ -n "$container_id" ]; then
        docker rm --force --volumes "$container_id" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker info >/dev/null
container_id=$(docker run --detach --rm \
    --publish 127.0.0.1::5432 \
    --env POSTGRES_DB=bootstrap_test \
    --env POSTGRES_USER=bootstrap_test \
    --env POSTGRES_PASSWORD=bootstrap-test-only \
    "$image")
attempt=0
until docker exec "$container_id" pg_isready -U bootstrap_test -d bootstrap_test >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        printf '%s\n' 'PostgreSQL fixture failed readiness after 30 seconds.' >&2
        exit 1
    fi
    sleep 1
done
address=$(docker port "$container_id" 5432/tcp)
port=${address##*:}
export POSTGRES_TEST_DSN="postgresql://bootstrap_test:bootstrap-test-only@127.0.0.1:$port/bootstrap_test"
cd "$repo_root/apps/orchestrator"
"$uv_bin" run --locked python -m pytest -m integration --require-postgres "$@"
