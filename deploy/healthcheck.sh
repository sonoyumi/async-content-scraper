#!/usr/bin/env bash
# Fails (exit 1) if the scraper's heartbeat file is missing or older than
# MAX_AGE_SEC. The scheduler (scraper/scheduler/runner.py) touches this file
# every 60s while its event loop is alive and responsive -- a plain process/
# PID check can't tell a wedged event loop from a healthy one, but a stale
# heartbeat can.
#
# Usage:
#   ./healthcheck.sh                       # checks ./data/heartbeat
#   HEARTBEAT_FILE=/opt/scraper/data/heartbeat ./healthcheck.sh
#
# Docker: add to docker-compose.yml under the `scraper` service:
#   healthcheck:
#     test: ["CMD", "/app/deploy/healthcheck.sh"]
#     interval: 60s
#     timeout: 5s
#     retries: 3
#     start_period: 30s

set -euo pipefail

HEARTBEAT_FILE="${HEARTBEAT_FILE:-data/heartbeat}"
MAX_AGE_SEC="${MAX_AGE_SEC:-180}"

if [[ ! -f "$HEARTBEAT_FILE" ]]; then
  echo "healthcheck: heartbeat file not found: $HEARTBEAT_FILE" >&2
  exit 1
fi

last_modified_epoch=$(date -r "$HEARTBEAT_FILE" +%s)
now_epoch=$(date +%s)
age_sec=$((now_epoch - last_modified_epoch))

if (( age_sec > MAX_AGE_SEC )); then
  echo "healthcheck: heartbeat is stale (${age_sec}s old, max ${MAX_AGE_SEC}s)" >&2
  exit 1
fi

echo "healthcheck: OK (heartbeat ${age_sec}s old)"
exit 0
