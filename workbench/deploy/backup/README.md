# Workbench backup & restore

Daily SQLite snapshot of `/var/lib/workbench/db/workbench.db` →
`gs://trade-workbench-backups-gen-lang-client-0229748590/`. 30 daily +
12 monthly retention. Restore is a one-command script.

This directory ships:

| File | Role |
|---|---|
| `workbench-backup.sh` | Snapshot + gzip + upload + retention prune. |
| `workbench-backup.service` | systemd one-shot wrapper running as `deploy`. |
| `workbench-backup.timer` | Daily 03:00 VM-local timer with `Persistent=true`. |
| `workbench-restore.sh` | Download + verify + swap + restart + healthcheck. |
| `logrotate.conf` | Monthly rotation of `/var/log/workbench/backup.log`. |

## Manual prereq — VM service-account scope expansion

The default `kolmatrix-vps` service account is provisioned with
`https://www.googleapis.com/auth/devstorage.read_only`, which the
metadata server returns at boot. Even though IAM grants
`roles/storage.objectAdmin` to the SA, the scope (not the IAM grant)
gates writes through `gcloud storage cp`. The backup script's upload step
fails until this is widened.

**User action (one-time, ~30-60s downtime for kolquest /
staging.kolmatrix / apify-kol / pm2 aigcgateway):**

```bash
gcloud compute instances stop kolmatrix-vps --zone=asia-northeast1-b
gcloud compute instances set-service-account kolmatrix-vps \
  --zone=asia-northeast1-b \
  --service-account=1044753973286-compute@developer.gserviceaccount.com \
  --scopes=cloud-platform
gcloud compute instances start kolmatrix-vps --zone=asia-northeast1-b
```

Pick a low-traffic window for the co-hosted services. The neighbours come
back online when the VM finishes booting (≤60s typically).

Verify after the VM is back up:

```bash
ssh deploy@$DEPLOY_HOST
curl -s -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/scopes
# expect output containing: https://www.googleapis.com/auth/cloud-platform

sudo -u deploy gcloud storage cp /etc/hostname \
  gs://trade-workbench-backups-gen-lang-client-0229748590/test.txt
sudo -u deploy gcloud storage rm \
  gs://trade-workbench-backups-gen-lang-client-0229748590/test.txt
# both should succeed
```

## Install (one-time, on the VM)

```bash
sudo cp /srv/workbench/current/deploy/backup/workbench-backup.service \
        /etc/systemd/system/
sudo cp /srv/workbench/current/deploy/backup/workbench-backup.timer \
        /etc/systemd/system/
sudo cp /srv/workbench/current/deploy/backup/logrotate.conf \
        /etc/logrotate.d/workbench-backup

sudo systemctl daemon-reload
sudo systemctl enable --now workbench-backup.timer
sudo systemctl list-timers --all | grep workbench-backup
# expect: workbench-backup.timer with a next-trigger time after 03:00 local
```

## Smoke test

```bash
sudo systemctl start workbench-backup.service
sudo systemctl status workbench-backup.service     # should be inactive (exited 0)
gcloud storage ls gs://trade-workbench-backups-gen-lang-client-0229748590/daily/
tail /var/log/workbench/backup.log
```

## Restore

```bash
# Pick a backup filename from the daily/ or monthly/ listing above.
sudo -u deploy bash /srv/workbench/current/deploy/backup/workbench-restore.sh \
  workbench-20260515T030000Z.db.gz
# Add --force to bypass the interactive confirmation.
```

The script:

1. Locates the file in `daily/` or `monthly/`.
2. Downloads + gunzips to `/tmp/wb-restore-<ts>.db`.
3. Sanity-checks with `PRAGMA quick_check` before touching the live DB.
4. `systemctl stop workbench-backend.service`.
5. Moves the live DB to `workbench.db.pre-restore.<ts>` so a botched
   restore is itself reversible.
6. Moves the restored DB into place with correct ownership/permissions.
7. `systemctl start workbench-backend.service`.
8. Polls `/api/health` for `"db_connectivity":"ok"` before exiting 0.

If any step fails, the original DB stays in
`workbench.db.pre-restore.<ts>` and the operator can manually flip back.

## Log file

`/var/log/workbench/backup.log` accumulates one line per backup attempt
and per restore. The `logrotate.conf` shipped here rotates monthly,
keeps 12 archives, compresses old ones, and the script appends in
truncation-safe mode (so logrotate's `copytruncate` works without
losing in-flight writes).
