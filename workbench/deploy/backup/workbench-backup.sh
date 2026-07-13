#!/usr/bin/env bash
# Workbench SQLite backup (runs as deploy via systemd one-shot).
#
# Target is pluggable via WORKBENCH_BACKUP_TARGET (default `gcs`):
#   gcs   — upload to gs://$WORKBENCH_BACKUP_BUCKET/{daily,monthly}/ (GCP VM;
#           requires apt gcloud + a service account with devstorage.read_write).
#   local — copy to $WORKBENCH_BACKUP_DIR/{daily,monthly}/ (default
#           /var/backups/workbench). NO gcloud dependency — this is what
#           deploysvr (194.238.26.173, non-GCP) uses since it has no gcloud
#           and no GCP service account (B107 F001).
#
# Each invocation:
#   1. Consistent snapshot via `sqlite3 workbench.db ".backup ..."` to /tmp.
#   2. gzip the snapshot.
#   3. Store to <target>/daily/<filename>.
#   4. On the 1st of the month, also store to <target>/monthly/.
#   5. Prune: keep 30 newest in daily/, 12 newest in monthly/, delete the rest.
#   6. rm /tmp/wb-* staging files.
#   7. Append a summary line to /var/log/workbench/backup.log.
#
# Manual prereq (gcs target only, B021 F005 spec): the VM SA must have
# `cloud-platform` scope (or at minimum devstorage.read_write). See
# workbench/deploy/backup/README.md for the one-time `gcloud compute
# instances set-service-account ... --scopes=cloud-platform` runbook. The
# `local` target has no such prereq.
#
# Bash 3.2 compatible.

set -euo pipefail

# --- Defaults the systemd EnvironmentFile may override ---
TARGET="${WORKBENCH_BACKUP_TARGET:-gcs}"
DB_PATH="${WORKBENCH_DB_PATH:-/var/lib/workbench/db/workbench.db}"
BUCKET="${WORKBENCH_BACKUP_BUCKET:-trade-workbench-backups-gen-lang-client-0229748590}"
LOCAL_DIR="${WORKBENCH_BACKUP_DIR:-/var/backups/workbench}"
LOG_FILE="${WORKBENCH_BACKUP_LOG:-/var/log/workbench/backup.log}"
DAILY_RETAIN="${WORKBENCH_BACKUP_DAILY_RETAIN:-30}"
MONTHLY_RETAIN="${WORKBENCH_BACKUP_MONTHLY_RETAIN:-12}"

case "${TARGET}" in
  gcs|local) ;;
  *) echo "error: WORKBENCH_BACKUP_TARGET must be 'gcs' or 'local', got '${TARGET}'" >&2; exit 64 ;;
esac

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

# --- Target-agnostic store primitives. All target-specific behaviour is
# confined to these three functions + remote_desc; the snapshot / gzip /
# retention logic below is shared. ---

# store_put <local_gz> <prefix> <remote_name>
store_put() {
  local src="$1" prefix="$2" name="$3"
  case "${TARGET}" in
    gcs)   gcloud storage cp "${src}" "gs://${BUCKET}/${prefix}/${name}" >/dev/null ;;
    local) mkdir -p "${LOCAL_DIR}/${prefix}"; cp "${src}" "${LOCAL_DIR}/${prefix}/${name}" ;;
  esac
}

# store_list <prefix> — print one deletable identifier per line (a gs:// URL
# for gcs, a full filesystem path for local). Constant-length prefix + ISO
# 8601 timestamp filename means `sort -r` orders newest-first for both.
store_list() {
  local prefix="$1"
  case "${TARGET}" in
    gcs)   gcloud storage ls "gs://${BUCKET}/${prefix}/" 2>/dev/null || true ;;
    local)
      if [[ -d "${LOCAL_DIR}/${prefix}" ]]; then
        find "${LOCAL_DIR}/${prefix}" -maxdepth 1 -type f -name '*.db.gz' 2>/dev/null || true
      fi
      ;;
  esac
}

# store_rm <identifier>
store_rm() {
  local obj="$1"
  case "${TARGET}" in
    gcs)   gcloud storage rm "${obj}" >/dev/null ;;
    local) rm -f "${obj}" ;;
  esac
}

# remote_desc <prefix> <name> — human-readable destination for the log.
remote_desc() {
  case "${TARGET}" in
    gcs)   echo "gs://${BUCKET}/$1/$2" ;;
    local) echo "${LOCAL_DIR}/$1/$2" ;;
  esac
}

if [[ ! -r "${DB_PATH}" ]]; then
  log "FAIL: DB not readable at ${DB_PATH}"
  exit 1
fi

log "BEGIN backup target=${TARGET} db=${DB_PATH} → $(remote_desc daily "${REMOTE_FILE}")"

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
store_put "${STAGE_GZ}" daily "${REMOTE_FILE}"

# 4. First-of-month → monthly archive as well.
DAY_OF_MONTH="$(date -u +%d)"
if [[ "${DAY_OF_MONTH}" == "01" ]]; then
  store_put "${STAGE_GZ}" monthly "${REMOTE_FILE}"
  log "MONTHLY: also copied to $(remote_desc monthly "${REMOTE_FILE}")"
fi

# 5. Retention prune. The store lists newest-last by name (timestamp-sorted
# prefixes work because we use ISO 8601 in the filename). Reverse with
# `sort -r` and skip the top N, then delete the rest one-at-a-time so a
# transient failure on one object does not abort the whole prune.
prune_prefix() {
  local prefix="$1"
  local retain="$2"
  local list
  list="$(store_list "${prefix}")"
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
    store_rm "${object}" || log "PRUNE-FAIL ${prefix}: ${object}"
  done <<<"$(printf '%s\n' "${list}" | sort -r)"
}

prune_prefix daily "${DAILY_RETAIN}"
prune_prefix monthly "${MONTHLY_RETAIN}"

END_TS="$(date -u +%s)"
START_EPOCH="$(date -d "$(date -u -d "${START_TS:0:4}-${START_TS:4:2}-${START_TS:6:2}T${START_TS:9:2}:${START_TS:11:2}:${START_TS:13:2}Z")" +%s 2>/dev/null || date -u +%s)"
DURATION="$((END_TS - START_EPOCH))"

log "OK backup target=${TARGET} snapshot_bytes=${SNAPSHOT_BYTES} gzip_bytes=${GZIP_BYTES} duration_s=${DURATION} remote=$(remote_desc daily "${REMOTE_FILE}")"
