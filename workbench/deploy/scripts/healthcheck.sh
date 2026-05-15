#!/usr/bin/env bash
# Post-deploy healthcheck. Polls /api/health and requires:
#   - HTTP 200
#   - "db_connectivity":"ok" in the JSON body
#
# Up to 10 attempts at 2-second intervals (≈20s total) before declaring
# failure. The B021 F004 workflow uses the exit code to decide whether to
# call rollback.sh.
#
# Bash 3.2 compatible.

set -euo pipefail

HEALTH_URL="${WORKBENCH_HEALTHCHECK_URL:-https://trade.guangai.ai/api/health}"
ATTEMPTS="${WORKBENCH_HEALTHCHECK_ATTEMPTS:-10}"
INTERVAL="${WORKBENCH_HEALTHCHECK_INTERVAL_SECONDS:-2}"

for i in $(seq 1 "${ATTEMPTS}"); do
  # `--silent --show-error --fail-with-body` gives us the body even on 5xx,
  # which we want for the operator-friendly log line.
  body="$(curl --silent --show-error --max-time 10 --location "${HEALTH_URL}" || true)"
  http_status="$(curl --silent --show-error --max-time 10 --location \
    --output /dev/null --write-out '%{http_code}' "${HEALTH_URL}" || echo 000)"

  if [[ "${http_status}" == "200" ]] && echo "${body}" | grep -q '"db_connectivity":"ok"'; then
    echo "✓ healthcheck pass attempt=${i}: ${body}"
    exit 0
  fi

  echo "… healthcheck attempt=${i}/${ATTEMPTS} status=${http_status} body=${body}" >&2
  sleep "${INTERVAL}"
done

echo "✗ healthcheck failed after ${ATTEMPTS} attempts (last status=${http_status})." >&2
exit 1
