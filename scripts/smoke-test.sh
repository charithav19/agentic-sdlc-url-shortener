#!/bin/sh
set -eu

SHORTENER_URL=${URL_BASE_URL:-http://127.0.0.1:${URL_SHORTENER_PORT:-8080}}
ORCHESTRATOR_URL=${ORCHESTRATOR_BASE_URL:-http://127.0.0.1:${ORCHESTRATOR_PORT:-8000}}
ALIAS="smoke$(date +%s)$$"
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/schwab-smoke.XXXXXX")
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM

assert_status() {
    expected=$1
    actual=$2
    label=$3
    if [ "$actual" != "$expected" ]; then
        printf '%s\n' "$label: expected HTTP $expected, received $actual" >&2
        exit 1
    fi
}

create_status=$(curl --silent --show-error --output "$TMP_DIR/create.json" --write-out '%{http_code}' \
    --header 'Content-Type: application/json' \
    --data "{\"url\":\"https://example.com/compose-smoke\",\"customAlias\":\"$ALIAS\"}" \
    "$SHORTENER_URL/api/v1/links")
assert_status 201 "$create_status" "create link"
grep -F "\"shortCode\":\"$ALIAS\"" "$TMP_DIR/create.json" >/dev/null

metadata_status=$(curl --silent --show-error --output "$TMP_DIR/metadata.json" --write-out '%{http_code}' \
    "$SHORTENER_URL/api/v1/links/$ALIAS")
assert_status 200 "$metadata_status" "link metadata"
grep -F '"url":"https://example.com/compose-smoke"' "$TMP_DIR/metadata.json" >/dev/null

redirect_status=$(curl --silent --show-error --output /dev/null --dump-header "$TMP_DIR/redirect.headers" \
    --write-out '%{http_code}' "$SHORTENER_URL/$ALIAS")
assert_status 302 "$redirect_status" "redirect"
tr -d '\r' < "$TMP_DIR/redirect.headers" | grep -Fi 'location: https://example.com/compose-smoke' >/dev/null

analytics_status=$(curl --silent --show-error --output "$TMP_DIR/analytics.json" --write-out '%{http_code}' \
    "$SHORTENER_URL/api/v1/links/$ALIAS/analytics")
assert_status 200 "$analytics_status" "link analytics"
grep -F "\"shortCode\":\"$ALIAS\"" "$TMP_DIR/analytics.json" >/dev/null

curl --fail --silent --show-error "$SHORTENER_URL/v3/api-docs" > "$TMP_DIR/shortener-openapi.json"
grep -F '"/api/v1/links"' "$TMP_DIR/shortener-openapi.json" >/dev/null
curl --fail --silent --show-error "$ORCHESTRATOR_URL/openapi.json" > "$TMP_DIR/orchestrator-openapi.json"
grep -F '"/health"' "$TMP_DIR/orchestrator-openapi.json" >/dev/null
curl --fail --silent --show-error "$ORCHESTRATOR_URL/metrics" > "$TMP_DIR/metrics.txt"
grep -F 'workflow_started_total' "$TMP_DIR/metrics.txt" >/dev/null

printf '%s\n' "smoke test passed: alias=$ALIAS"
