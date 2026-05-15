#!/usr/bin/env bash
# Workbench SQLite → GCS backup (runs as deploy via systemd one-shot).
#
# Each invocation:
#   1. Consistent snapshot via `sqlite3 workbench.db ".backup ..."` to /tmp.
#   2. gzip the snapshot.
#   3. Upload to gs://$WORKBENCH_BACKUP_BUCKET/daily/<filename>.
#   4. On the 1st of the month, copy to gs://$WORKBENCH_BACKUP_BUCKET/monthly/
#      as well.
#   5. Prune: keep 30 newest in daily/, 12 newest in monthly/, delete the rest.
#   6. rm /tmp/wb-* staging files.
#   7. Append a summary line to /var/log/workbench/backup.log.
#
# Manual prereq (B021 F005 spec): the VM SA must have `cloud-platform` scope
# (or at minimum devstorage.read_write). The default `devstorage.read_only`
# makes step 3 fail even though IAM grants storage.objectAdmin. See
# workbench/deploy/backup/README.md for the one-time `gcloud compute
# instances set-service-account ... --scopes=cloud-platform` runbook.
#
# Bash 3.2 compatible.

set -euo pipefail

# --- Defaults the systemd EnvironmentFile may override ---
DB_PATH="${WORKBENCH_DB_PATH:-/var/lib/workbench/db/workbench.db}"
BUCKET="${WORKBENCH_BACKUP_BUCKET:-trade-workbench-backups-gen-lang-client-0229748590}"
LOG_FILE="${WORKBENCH_BACKUP_LOG:-/var/log/workbench/backup.log}"
DAILY_RETAIN="${WORKBENCH_BACKUP_DAILY_RETAIN:-30}"
MONTHLY_RETAIN="${WORKBENCH_BACKUP_MONTHLY_RETAIN:-12}"

START_TS="$(date -u +%Y%m%dT%H%M%SZ)"
STAGE_FILE="/tmp/wb-${START_TS}.db"
STAGE_GZ="${STAGE_FILE}.gz"
REMOTE_FILE="workbench-${START_TS}.db.gz"

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "${LOG_FILE}" >&2
}

cleanup_stage() {
  rm -f /tmp/wb-*.db /tmp/wb-*.db.gz
}
trap cleanup_stage EXIT

if [[ ! -r "${DB_PATH}" ]]; then
  log "FAIL: DB not readable at ${DB_PATH}"
  exit 1
fi

log "BEGIN backup db=${DB_PATH} → gs://${BUCKET}/daily/${REMOTE_FILE}"

# 1. SQLite-native online snapshot. `.backup` cooperates with WAL so the
# running app never sees a partial write; no app-level lock needed.
sqlite3 "${DB_PATH}" ".backup '${STAGE_FILE}'"
SNAPSHOT_BYTES="$(stat -c '%s' "${STAGE_FILE}")"

# 2. gzip in place (gzip removes the source). `-9` is overkill for the file
# sizes we expect (single-digit MB), but the savings are real on
# multi-month retention and the wall time is negligible.
gzip -9 "${STAGE_FILE}"
GZIP_BYTES="$(stat -c '%s' "${STAGE_GZ}")"

# 3. Daily copy.
gcloud storage cp "${STAGE_GZ}" "gs://${BUCKET}/daily/${REMOTE_FILE}" >/dev/null

# 4. First-of-month → monthly archive as well.
DAY_OF_MONTH="$(date -u +%d)"
if [[ "${DAY_OF_MONTH}" == "01" ]]; then
  gcloud storage cp "${STAGE_GZ}" "gs://${BUCKET}/monthly/${REMOTE_FILE}" >/dev/null
  log "MONTHLY: also copied to gs://${BUCKET}/monthly/${REMOTE_FILE}"
fi

# 5. Retention prune. `gcloud storage ls --json` would be neater on
# newer gcloud versions, but the line-oriented output works on the
# Ubuntu 22.04 default and is Bash 3.2 friendly.
prune_bucket_prefix() {
  local prefix="$1"
  local retain="$2"
  # The bucket lists newest-last by name (timestamp-sorted prefixes work
  # because we use ISO 8601 in the filename). Reverse with `sort -r` and
  # skip the top N, then delete the rest one-at-a-time so a transient
  # 5xx on one object does not abort the whole prune.
  local list
  list="$(gcloud storage ls "gs://${BUCKET}/${prefix}/" 2>/dev/null || true)"
  if [[ -z "${list}" ]]; then
    return 0
  fi
  local i=0
  while IFS= read -r object; do
    if [[ -z "${object}" ]]; then
      continue
    fi
    i=$((i + 1))
    if (( i <= retain )); then
      continue
    fi
    log "PRUNE ${prefix}: ${object}"
    gcloud storage rm "${object}" >/dev/null || log "PRUNE-FAIL ${prefix}: ${object}"
  done <<<"$(printf '%s\n' "${list}" | sort -r)"
}

prune_bucket_prefix daily "${DAILY_RETAIN}"
prune_bucket_prefix monthly "${MONTHLY_RETAIN}"

END_TS="$(date -u +%s)"
START_EPOCH="$(date -d "$(date -u -d "${START_TS:0:4}-${START_TS:4:2}-${START_TS:6:2}T${START_TS:9:2}:${START_TS:11:2}:${START_TS:13:2}Z")" +%s 2>/dev/null || date -u +%s)"
DURATION="$((END_TS - START_EPOCH))"

log "OK backup snapshot_bytes=${SNAPSHOT_BYTES} gzip_bytes=${GZIP_BYTES} duration_s=${DURATION} remote=gs://${BUCKET}/daily/${REMOTE_FILE}"
