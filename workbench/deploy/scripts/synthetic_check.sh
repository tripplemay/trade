#!/usr/bin/env bash
# Synthetic monitoring suite (P3-F1 / B097 F001).
#
# A READ-ONLY, GET-only probe of the production Workbench API that extends the
# single-endpoint post-deploy healthcheck (healthcheck.sh) into a fuller set of
# synthetic checks:
#
#   (1) /api/health -> HTTP 200 + "db_connectivity":"ok"   [public]
#   (2) recent-errors == 0                                  [auth-gated, opt-in]
#   (3) HEAD == prod : deployed git SHA equals expected SHA [public field]
#   (4) key endpoints return sane-SHAPED data               [public]
#
# ─── PRODUCTION-SAFETY CONTRACT ──────────────────────────────────────────────
#   * READ-ONLY. Every request is an HTTP GET. This script NEVER issues
#     POST/PUT/DELETE/PATCH and touches no mutation endpoint. It cannot change
#     any production state.
#   * ZERO FALSE-REDS. Each check retries and asserts only conditions that are
#     reliably true on a *healthy* production (HTTP status, JSON shape, SHA
#     format), never brittle values that legitimately vary (uptime, counts,
#     backup ages). A check that cannot be evaluated SKIPs — it never FAILs.
#   * NO CREDENTIAL LEAK. The only secret this suite can use is an optional
#     Auth.js session cookie, read from the WORKBENCH_SYNTHETIC_SESSION_COOKIE
#     environment variable. No token/cookie/key is ever written to disk or
#     hard-coded here. Without that env var the suite runs PUBLIC-ONLY.
#   * ADDITIVE. This file is standalone. It does NOT modify healthcheck.sh and
#     is NOT wired into the deploy's rollback path (that is P3-F2). Running it
#     changes nothing about the existing rollback trigger.
#
# Exit status: 0 if no check FAILed (PASS/SKIP are both non-fatal), 1 otherwise.
#
# Bash 3.2 compatible; no jq dependency (JSON parsed with grep/sed).

set -euo pipefail

# ─── Configuration (all overridable via env) ─────────────────────────────────
BASE_URL="${WORKBENCH_SYNTHETIC_BASE_URL:-https://trade.guangai.ai}"
HEALTH_URL="${WORKBENCH_HEALTHCHECK_URL:-${BASE_URL}/api/health}"
ATTEMPTS="${WORKBENCH_SYNTHETIC_ATTEMPTS:-5}"
INTERVAL="${WORKBENCH_SYNTHETIC_INTERVAL_SECONDS:-2}"
MAX_TIME="${WORKBENCH_SYNTHETIC_MAX_TIME_SECONDS:-10}"

# Check (3): expected deployed SHA. The deploy workflow knows RELEASE_SHA and
# can pass it in; when unset we can only shape-check the version field.
EXPECTED_SHA="${WORKBENCH_SYNTHETIC_EXPECTED_SHA:-}"

# Check (2): optional Auth.js session cookie VALUE (not name=value), read from
# env ONLY. When empty, the recent-errors check is skipped (public-only mode).
SESSION_COOKIE="${WORKBENCH_SYNTHETIC_SESSION_COOKIE:-}"
COOKIE_NAME="${WORKBENCH_SYNTHETIC_COOKIE_NAME:-__Secure-authjs.session-token}"

# Check (4b): auth-gated endpoints that must reject an unauthenticated GET with
# 401 (proves routing + auth middleware are alive, not 500/404). Space list.
AUTH_ENDPOINTS="${WORKBENCH_SYNTHETIC_AUTH_ENDPOINTS:-/api/market-context /api/home /api/reports}"

FAILURES=0
SHA_RE='^[0-9a-f]\{40\}$'

# ─── Small helpers ───────────────────────────────────────────────────────────
pass() { echo "  ✓ PASS  $*"; }
skip() { echo "  – SKIP  $*"; }
fail() { echo "  ✗ FAIL  $*" >&2; FAILURES=$((FAILURES + 1)); }

# GET the status code for a URL (read-only; --output discards the body).
http_status() {
  curl --silent --show-error --max-time "${MAX_TIME}" --location \
    --output /dev/null --write-out '%{http_code}' "$1" 2>/dev/null || echo 000
}

# GET the body for a URL (read-only).
http_body() {
  curl --silent --show-error --max-time "${MAX_TIME}" --location "$1" 2>/dev/null || true
}

# Extract a string JSON field value: json_field <field> <body>
json_field() {
  # '|| true' swallows grep's no-match exit 1 so that under 'set -e'/pipefail a
  # missing field yields "" (-> caller SKIPs), never aborts the whole script.
  echo "$2" | grep -o "\"$1\":\"[^\"]*\"" | head -n1 | sed "s/\"$1\":\"//;s/\"$//" || true
}

echo "── synthetic monitoring suite (READ-ONLY GET probes) ──"
echo "base=${BASE_URL} attempts=${ATTEMPTS} interval=${INTERVAL}s"

# ─── Fetch /api/health with retries (shared by checks 1, 3, 4a) ──────────────
HEALTH_BODY=""
HEALTH_STATUS="000"
for i in $(seq 1 "${ATTEMPTS}"); do
  HEALTH_BODY="$(http_body "${HEALTH_URL}")"
  HEALTH_STATUS="$(http_status "${HEALTH_URL}")"
  if [[ "${HEALTH_STATUS}" == "200" ]]; then
    break
  fi
  echo "  … health attempt ${i}/${ATTEMPTS} status=${HEALTH_STATUS}" >&2
  [[ "${i}" -lt "${ATTEMPTS}" ]] && sleep "${INTERVAL}"
done

# ─── Check (1): health 200 + db_connectivity ok ──────────────────────────────
echo "[1] health reachable + DB connectivity"
if [[ "${HEALTH_STATUS}" == "200" ]] \
  && echo "${HEALTH_BODY}" | grep -q '"db_connectivity":"ok"'; then
  pass "HTTP 200 and db_connectivity=ok"
else
  fail "health not 200/db-ok (status=${HEALTH_STATUS} body=${HEALTH_BODY})"
fi

# ─── Check (4a): health JSON has sane SHAPE ──────────────────────────────────
# Assert presence + type/format only — never the volatile values (uptime,
# counts, backup ages all legitimately vary between deploys).
echo "[4a] health JSON shape"
H_STATUS_FIELD="$(json_field status "${HEALTH_BODY}")"
H_VERSION="$(json_field version "${HEALTH_BODY}")"
H_DBOK="$(json_field db_connectivity "${HEALTH_BODY}")"
if [[ "${H_STATUS_FIELD}" == "ok" ]] \
  && [[ "${H_DBOK}" == "ok" ]] \
  && echo "${H_VERSION}" | grep -q "${SHA_RE}" \
  && echo "${HEALTH_BODY}" | grep -q '"uptime_seconds":[0-9]'; then
  pass "status/db_connectivity=ok, version is 40-hex, uptime present"
else
  fail "health shape unexpected (status=${H_STATUS_FIELD} db=${H_DBOK} version=${H_VERSION})"
fi

# ─── Check (3): HEAD == prod (deployed SHA equals expected) ──────────────────
echo "[3] HEAD ≡ prod (deployed git SHA)"
if ! echo "${H_VERSION}" | grep -q "${SHA_RE}"; then
  fail "no valid 40-hex version SHA in /api/health to compare"
elif [[ -z "${EXPECTED_SHA}" ]]; then
  skip "WORKBENCH_SYNTHETIC_EXPECTED_SHA unset — version present (${H_VERSION}), equality not asserted (deploy passes RELEASE_SHA; wiring is P3-F2)"
elif [[ "${H_VERSION}" == "${EXPECTED_SHA}" ]]; then
  pass "prod version == expected SHA (${H_VERSION})"
else
  fail "prod SHA ${H_VERSION} != expected ${EXPECTED_SHA}"
fi

# ─── Check (2): recent-errors == 0 (auth-gated, opt-in) ──────────────────────
echo "[2] recent server errors == 0"
RE_URL="${BASE_URL}/api/debug/recent-errors"
if [[ -z "${SESSION_COOKIE}" ]]; then
  skip "public-only mode — set WORKBENCH_SYNTHETIC_SESSION_COOKIE (env, never committed) to enable /api/debug/recent-errors"
else
  re_status="000"
  re_body=""
  for i in $(seq 1 "${ATTEMPTS}"); do
    # Read-only GET; cookie value comes from env, never persisted.
    re_body="$(curl --silent --show-error --max-time "${MAX_TIME}" --location \
      --cookie "${COOKIE_NAME}=${SESSION_COOKIE}" "${RE_URL}" 2>/dev/null || true)"
    re_status="$(curl --silent --show-error --max-time "${MAX_TIME}" --location \
      --cookie "${COOKIE_NAME}=${SESSION_COOKIE}" \
      --output /dev/null --write-out '%{http_code}' "${RE_URL}" 2>/dev/null || echo 000)"
    [[ "${re_status}" == "200" ]] && break
    [[ "${i}" -lt "${ATTEMPTS}" ]] && sleep "${INTERVAL}"
  done
  # '|| true' keeps a no-match (rejected/odd cookie body has no count) from
  # aborting under 'set -e'/pipefail; empty re_count -> the SKIP branch below.
  re_count="$(echo "${re_body}" | grep -o '"count":[0-9]*' | head -n1 | sed 's/"count"://' || true)"
  if [[ "${re_status}" == "401" || "${re_status}" == "403" ]]; then
    # Credential problem, not a prod fault — do NOT false-red a good deploy.
    skip "cookie rejected (HTTP ${re_status}); recent-errors not asserted"
  elif [[ "${re_status}" != "200" || -z "${re_count}" ]]; then
    skip "recent-errors unreadable (status=${re_status}); not asserted"
  elif [[ "${re_count}" == "0" ]]; then
    pass "recent-errors count == 0"
  else
    fail "recent-errors count == ${re_count} (expected 0)"
  fi
fi

# ─── Check (4b): key auth-gated endpoints reject anon GET with 401 ───────────
# A 401 (not 500, not 404) proves routing + auth middleware are alive. This is
# public-safe: we send NO cookie, so we cannot read protected data.
echo "[4b] auth-gated endpoints return 401 (routing + auth alive)"
for ep in ${AUTH_ENDPOINTS}; do
  url="${BASE_URL}${ep}"
  ep_status="000"
  for i in $(seq 1 "${ATTEMPTS}"); do
    ep_status="$(http_status "${url}")"
    # Pass as soon as we see the healthy 401 (tolerate transient blips).
    [[ "${ep_status}" == "401" ]] && break
    [[ "${i}" -lt "${ATTEMPTS}" ]] && sleep "${INTERVAL}"
  done
  if [[ "${ep_status}" == "401" ]]; then
    pass "${ep} -> 401"
  else
    fail "${ep} -> ${ep_status} (expected 401)"
  fi
done

# ─── Verdict ─────────────────────────────────────────────────────────────────
echo "──────────────────────────────────────────────────────"
if [[ "${FAILURES}" -eq 0 ]]; then
  echo "✓ synthetic suite PASS (no FAILs; SKIPs are non-fatal)"
  exit 0
fi
echo "✗ synthetic suite FAIL — ${FAILURES} check(s) failed" >&2
exit 1
