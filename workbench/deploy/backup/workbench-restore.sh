#!/usr/bin/env bash
# Restore the workbench SQLite DB from a backup snapshot.
#
# Usage:
#   sudo -u deploy bash workbench-restore.sh <backup-filename> [--force]
#
# Target is pluggable via WORKBENCH_BACKUP_TARGET (default `gcs`), matching
# workbench-backup.sh:
#   gcs   — source is gs://$WORKBENCH_BACKUP_BUCKET/{daily,monthly}/.
#   local — source is $WORKBENCH_BACKUP_DIR/{daily,monthly}/ (deploysvr;
#           default /var/backups/workbench). NO gcloud dependency (B107 F001).
#
# The <backup-filename> argument is the bare filename (the script tries
# daily/ first, then monthly/). The script:
#
#   1. Resolves the path (daily first, then monthly).
#   2. Downloads/copies + gunzips to /tmp/wb-restore-<ts>.db.
#   3. Stops workbench-backend.service.
#   4. Moves the live workbench.db aside (.pre-restore suffix with a timestamp).
#   5. Moves the restored file into place.
#   6. Starts workbench-backend.service.
#   7. Polls /api/health for db_connectivity=ok before exiting 0.
#
# `--force` skips the interactive confirmation. Operators running this
# from a runbook (Codex L2 acceptance, post-incident recovery) pass the
# flag; humans testing in a shell should not.
#
# Bash 3.2 compatible.

set -euo pipefail

TARGET="${WORKBENCH_BACKUP_TARGET:-gcs}"
DB_PATH="${WORKBENCH_DB_PATH:-/var/lib/workbench/db/workbench.db}"
BUCKET="${WORKBENCH_BACKUP_BUCKET:-trade-workbench-backups-gen-lang-client-0229748590}"
LOCAL_DIR="${WORKBENCH_BACKUP_DIR:-/var/backups/workbench}"
LOG_FILE="${WORKBENCH_BACKUP_LOG:-/var/log/workbench/backup.log}"
HEALTH_URL="${WORKBENCH_HEALTHCHECK_URL:-https://trade.guangai.ai/api/health}"

case "${TARGET}" in
  gcs|local) ;;
  *) echo "error: WORKBENCH_BACKUP_TARGET must be 'gcs' or 'local', got '${TARGET}'" >&2; exit 64 ;;
esac

FORCE=0
BACKUP_FILE=""

for arg in "$@"; do
  case "${arg}" in
    --force) FORCE=1 ;;
    -h|--help)
      sed -n '/^# Usage:/,/^$/p' "$0" >&2
      exit 0
      ;;
    --*) echo "error: unknown flag ${arg}" >&2; exit 64 ;;
    *)   BACKUP_FILE="${arg}" ;;
  esac
done

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "usage: $(basename "$0") <backup-filename> [--force]" >&2
  exit 64
fi

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "${LOG_FILE}" >&2
}

RESTORE_TS="$(date -u +%Y%m%dT%H%M%SZ)"
STAGE_GZ="/tmp/wb-restore-${RESTORE_TS}.db.gz"
STAGE_DB="/tmp/wb-restore-${RESTORE_TS}.db"

cleanup() {
  rm -f "${STAGE_GZ}" "${STAGE_DB}"
}
trap cleanup EXIT

# --- Target-agnostic source resolution + fetch. `src_exists` / `src_fetch`
# take a full identifier (gs:// URL for gcs, filesystem path for local). ---

src_exists() {
  local candidate="$1"
  case "${TARGET}" in
    gcs)   gcloud storage ls "${candidate}" >/dev/null 2>&1 ;;
    local) [[ -f "${candidate}" ]] ;;
  esac
}

src_fetch() {  # <identifier> <dest_gz>
  local candidate="$1" dest="$2"
  case "${TARGET}" in
    gcs)   gcloud storage cp "${candidate}" "${dest}" >/dev/null ;;
    local) cp "${candidate}" "${dest}" ;;
  esac
}

candidate_path() {  # <prefix>
  case "${TARGET}" in
    gcs)   echo "gs://${BUCKET}/$1/${BACKUP_FILE}" ;;
    local) echo "${LOCAL_DIR}/$1/${BACKUP_FILE}" ;;
  esac
}

REMOTE=""
for prefix in daily monthly; do
  candidate="$(candidate_path "${prefix}")"
  if src_exists "${candidate}"; then
    REMOTE="${candidate}"
    break
  fi
done

if [[ -z "${REMOTE}" ]]; then
  if [[ "${TARGET}" == "gcs" ]]; then
    echo "error: ${BACKUP_FILE} not found in gs://${BUCKET}/daily/ or /monthly/" >&2
  else
    echo "error: ${BACKUP_FILE} not found in ${LOCAL_DIR}/daily/ or /monthly/" >&2
  fi
  exit 65
fi

log "RESTORE target=${TARGET} source=${REMOTE} → ${DB_PATH}"

if (( FORCE != 1 )); then
  echo -n "About to overwrite ${DB_PATH} from ${REMOTE}. Continue? [y/N] " >&2
  read -r confirm
  case "${confirm}" in
    y|Y|yes|Yes|YES) ;;
    *) echo "Aborted by operator." >&2; exit 1 ;;
  esac
fi

src_fetch "${REMOTE}" "${STAGE_GZ}"
gunzip "${STAGE_GZ}"

# Sanity check: the restored file must be a real SQLite database before we
# touch the live file.
if ! sqlite3 "${STAGE_DB}" "PRAGMA quick_check;" | grep -q '^ok$'; then
  echo "error: ${BACKUP_FILE} failed PRAGMA quick_check — refusing to swap" >&2
  exit 66
fi

log "STOPPING workbench-backend.service"
sudo /bin/systemctl stop workbench-backend.service

LIVE_BACKUP="${DB_PATH}.pre-restore.${RESTORE_TS}"
if [[ -f "${DB_PATH}" ]]; then
  mv "${DB_PATH}" "${LIVE_BACKUP}"
  log "MOVED live db → ${LIVE_BACKUP}"
fi
mv "${STAGE_DB}" "${DB_PATH}"
chown deploy:deploy "${DB_PATH}"
chmod 600 "${DB_PATH}"

log "STARTING workbench-backend.service"
sudo /bin/systemctl start workbench-backend.service

# Verify the new DB is healthy from the app's point of view before we
# declare success.
for i in 1 2 3 4 5; do
  body="$(curl --silent --show-error --max-time 5 --location "${HEALTH_URL}" || true)"
  if echo "${body}" | grep -q '"db_connectivity":"ok"'; then
    log "OK restore complete — body=${body}"
    exit 0
  fi
  sleep 2
done

log "FAIL post-restore healthcheck never returned db_connectivity=ok"
exit 1
