# B021 VM Setup Runbook (User Manual Actions)

> Forward-looking document. Created during B020 (Dev Infrastructure) batch because the user is doing B021 (Cloud Deploy & Auth) preparation in parallel. This runbook collects all 5 manual prep actions the user must complete before B021 F001 can land. B021 spec (drafted later) will reference this runbook as canonical.

## Overview of the 5 prep items

| # | Item | Where | Who | Status (fill as you complete) |
|---|---|---|---|---|
| 1 | Google OAuth 2.0 client created | Google Cloud Console | User | ✅ done; secret rotated 2026-05-15 06:53Z (user reported; verified indirectly via GitHub Secret update timestamp) |
| 2 | DNS `trade.guangai.ai` A record | DNS provider | User | ✅ done (per user 2026-05-15) |
| 3 | VM `deploy` user + dirs + SSH key | GCP VM (SSH session) | User | ✅ done 2026-05-15 (executed by Planner under user authorization — see "Item #3 — executed" section below) |
| 4 | GCS bucket for SQLite backups | Google Cloud Console | User | ✅ done 2026-05-15 (executed by Planner via `gcloud` on VM after user `gcloud auth login`; bucket `gs://trade-workbench-backups-gen-lang-client-0229748590/`, region `ASIA-NORTHEAST1`, versioning ON, lifecycle 365d delete, public access prevention enforced, uniform IAM, VM SA pre-granted `roles/storage.objectAdmin`) |
| 5 | GitHub Secrets uploaded | GitHub repo Settings | User | ✅ 7/7 done — `GOOGLE_OAUTH_CLIENT_ID` updated 06:52:40Z + `GOOGLE_OAUTH_CLIENT_SECRET` updated 06:53:24Z (both > placeholder timestamps 06:45). User-update confirmed via `gh secret list` timestamp shift. |

---

## Item #3 — VM `deploy` user + workbench dirs + SSH authorized_keys

### Prerequisites

- You can SSH into the GCP VM as a user with `sudo` access (presumably your own account).
- You already generated an ed25519 SSH keypair on your local machine (file: `~/.ssh/trade-deploy.pub` is the public key).
- You know the OS family (Ubuntu/Debian assumed below; commands are nearly identical on Debian; on RHEL/CentOS swap `useradd` flags slightly).

### Step 1 — SSH into the VM

```bash
# From your local machine, not from any chat window:
ssh -i ~/.ssh/your-existing-key your-user@<VM-public-IP>
```

### Step 2 — Pre-flight check (fail-safe: confirm deploy user does NOT already exist)

```bash
# Run on VM:
id deploy 2>/dev/null && echo "WARN: deploy user already exists — investigate before proceeding" || echo "OK: deploy user does not exist; safe to create"
```

If `WARN` appears: `cat /etc/passwd | grep deploy` and decide whether to reuse, rename, or back out. **Do NOT continue blindly** — the existing user may belong to aigcgateway or another service.

### Step 3 — Create the `deploy` user (system user with bash shell)

```bash
sudo useradd \
  --system \
  --create-home \
  --home-dir /home/deploy \
  --shell /bin/bash \
  --user-group \
  deploy

# Verify:
id deploy
ls -ld /home/deploy
```

Expected: `id deploy` shows uid=999+ (system uid range) gid=999+ groups=deploy. `/home/deploy` exists, owned by `deploy:deploy`.

### Step 4 — Create workbench data directories

```bash
sudo mkdir -p /var/lib/workbench/{db,snapshots,runs,backups,logs}
sudo chown -R deploy:deploy /var/lib/workbench
sudo chmod 750 /var/lib/workbench
sudo chmod 700 /var/lib/workbench/db    # SQLite db — only deploy can read

# Verify:
ls -la /var/lib/workbench/
```

Expected: 5 sub-dirs (`db / snapshots / runs / backups / logs`), all `deploy:deploy`, permissions look right.

### Step 5 — Configure SSH `authorized_keys` for deploy user

```bash
# Create .ssh dir
sudo -u deploy mkdir -p /home/deploy/.ssh
sudo -u deploy chmod 700 /home/deploy/.ssh

# Open authorized_keys for editing — paste the contents of your local ~/.ssh/trade-deploy.pub
sudo -u deploy nano /home/deploy/.ssh/authorized_keys
# (or: sudo -u deploy vim, etc.)

# IMPORTANT: paste the entire single line of the public key, including the comment at the end
# It looks like:  ssh-ed25519 AAAAC3Nz...XYZ== github-actions-deploy@trade-workbench
# Save and exit.

sudo -u deploy chmod 600 /home/deploy/.ssh/authorized_keys

# Verify the key was added correctly:
sudo -u deploy cat /home/deploy/.ssh/authorized_keys
sudo -u deploy ssh-keygen -lf /home/deploy/.ssh/authorized_keys
```

Expected: `ssh-keygen -lf` shows the key fingerprint + key type `(ED25519)` + the comment.

### Step 6 — Restrict deploy user `sudo` privileges to only what GitHub Actions needs

The deploy user should NOT have full root. It should be allowed to (a) restart the workbench services and (b) read service status. Nothing else.

```bash
# Edit a sudoers drop-in:
sudo visudo -f /etc/sudoers.d/deploy-workbench
```

Paste exactly:

```
# Generated 2026-05-15 for B021 workbench deploy user
# This user can ONLY restart and inspect the two workbench services.
# It cannot install packages, edit other configs, or sudo anything else.
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart workbench-backend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart workbench-frontend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status workbench-backend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status workbench-frontend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload
```

Save (visudo will syntax-check on save; if it complains, fix and re-save — never bypass).

```bash
# Set perms:
sudo chmod 440 /etc/sudoers.d/deploy-workbench

# Verify syntax explicitly:
sudo visudo -c -f /etc/sudoers.d/deploy-workbench
# Expected: "/etc/sudoers.d/deploy-workbench: parsed OK"
```

> Note: the two systemd unit files (`workbench-backend.service` and `workbench-frontend.service`) **don't exist yet** — they're created by B021 F003. The sudoers entry is intentionally pre-staged so the deploy user has the right perms the moment the units land.

### Step 7 — Test the deploy user can SSH in (from your local machine, not VM)

```bash
# Back on your local machine, with your locally-generated private key:
ssh -i ~/.ssh/trade-deploy deploy@<VM-public-IP> "echo 'ssh works' && id && ls /var/lib/workbench/"
```

Expected: `ssh works` + `uid=... deploy ...` + listing of 5 subdirs.

If this fails: check that `/home/deploy/.ssh/authorized_keys` contains the public key on a single line, has `chmod 600`, and that the public key on the VM matches what `ssh-keygen -lf ~/.ssh/trade-deploy.pub` shows on your local machine.

### Step 8 — Mark item #3 done

Set this row in the table at the top of this file to ✅ done. Commit + push (it's just a doc edit, no secret).

---

## Item #3 — executed 2026-05-15 (Planner ran it under user authorization)

> **Role-boundary note:** Per `harness-rules.md` the Planner agent normally does not touch product / infrastructure code. On 2026-05-15 the user explicitly authorized the Planner to SSH into the VM and execute item #3 directly ("本机可以访问这台生产服务器，我要求你直接上去做"). Future similar work should follow normal Generator/Codex execution flow unless again explicitly authorized; this entry documents the exception.

**SSH target:** `kolmatrix-vps` alias → 34.180.93.185, login user `tripplezhou` with key `~/.ssh/id_ed25519_kolmatrix` (existing personal key).

**Deploy keypair generated locally on this WSL** (private kept local, never transmitted):
- Path: `~/.ssh/trade-deploy` (private), `~/.ssh/trade-deploy.pub` (public)
- Type: ed25519
- Comment: `github-actions-deploy@trade-workbench`
- Fingerprint: `SHA256:Q7FSvAbFRbKTvh1Y0WMd4c5AdRXQJe7Y4052bqfNHQY`

**VM state after execution (verified via SSH):**

```
$ id deploy
uid=997(deploy) gid=997(deploy) groups=997(deploy)

$ sudo ls -la /var/lib/workbench/
drwxr-x---  7 deploy deploy 4096 May 15 06:15 .
drwxr-xr-x 48 root   root   4096 May 15 06:15 ..
drwxr-xr-x  2 deploy deploy 4096 May 15 06:15 backups
drwx------  2 deploy deploy 4096 May 15 06:15 db          # chmod 700 — SQLite db only readable by deploy
drwxr-xr-x  2 deploy deploy 4096 May 15 06:15 logs
drwxr-xr-x  2 deploy deploy 4096 May 15 06:15 runs
drwxr-xr-x  2 deploy deploy 4096 May 15 06:15 snapshots

$ sudo cat /home/deploy/.ssh/authorized_keys
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPucZnfYlQPvIbFYupbGf/ObmJ7TctrSyEru20sMbew0 github-actions-deploy@trade-workbench
# (perms: chmod 700 .ssh, chmod 600 authorized_keys, deploy:deploy)

$ sudo visudo -c -f /etc/sudoers.d/deploy-workbench
/etc/sudoers.d/deploy-workbench: parsed OK

$ sudo cat /etc/sudoers.d/deploy-workbench
# Generated 2026-05-15 (B021 prep) for workbench deploy user
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart workbench-backend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart workbench-frontend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status workbench-backend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status workbench-frontend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload
```

**Verification (from local WSL using `~/.ssh/trade-deploy`):**

```
$ ssh -i ~/.ssh/trade-deploy deploy@34.180.93.185 'echo SSH_AS_DEPLOY_OK; id; ls /var/lib/workbench/'
SSH_AS_DEPLOY_OK
uid=997(deploy) gid=997(deploy) groups=997(deploy)
backups  db  logs  runs  snapshots

$ ssh -i ~/.ssh/trade-deploy deploy@34.180.93.185 'sudo -n /bin/systemctl daemon-reload && echo SUDO_DAEMON_RELOAD_OK'
SUDO_DAEMON_RELOAD_OK              # ✅ allowlisted command works

$ ssh -i ~/.ssh/trade-deploy deploy@34.180.93.185 'sudo -n /bin/cat /etc/shadow 2>&1'
sudo: a password is required        # ✅ non-allowlisted command correctly blocked
```

**Pre-existing services on VM (will share resources with workbench):**

- nginx (systemd) serving `kolquest.com` + `staging.kolmatrix`
- pm2-managed `aigcgateway` process (user confirmed 2026-05-15 — pm2 not systemd, hence original pre-flight grep missed it)
- docker containers: `apify-kol-service-service-1` + `apify-kol-service-postgres-1`

**B021 spec impact:**

- "Reuse aigcgateway nginx" assumption holds (nginx is global, used by multiple services on this VM).
- New nginx server block for `trade.guangai.ai` will sit alongside existing `kolquest.com` and `staging.kolmatrix` blocks. F003 should `nginx -t` validate before reload.
- Resource quota (systemd `CPUQuota` + `MemoryMax`) must fence workbench from kolmatrix + apify-kol + pm2 aigcgateway — same intent as original ADR, just more concrete neighbor list.

---

## Item #4 — executed 2026-05-15 (Planner ran it after user `gcloud auth login`)

> Planner executed via `gcloud` from VM after user completed interactive `gcloud auth login --no-launch-browser` on the VM. User's credentials cached at `~/.config/gcloud/legacy_credentials/tripplezhou@gmail.com/`; user can `gcloud auth revoke tripplezhou@gmail.com` on VM after B021 setup if desired.

**Bucket configuration (verified):**

```
location: ASIA-NORTHEAST1                  # same as VM zone asia-northeast1-b → zero egress
versioning_enabled: True                   # delete-recovery safety net
public_access_prevention: enforced         # bucket can never be made public
uniform_bucket_level_access: True          # IAM-only, no legacy ACLs
storage_class: STANDARD                    # appropriate for hot-access backups
lifecycle_config:
  rule:
    - action: { type: Delete }
      condition: { age: 365 }              # 365-day auto-delete safety net beyond B021 F005 retention script
```

**IAM bindings on bucket:**

```
serviceAccount:1044753973286-compute@developer.gserviceaccount.com
  → roles/storage.objectAdmin
```

(plus default project-level Owner/Editor/Viewer bindings — standard)

**Write test (via user `tripplezhou@gmail.com` auth, project owner):**

```
$ echo "test" | gcloud storage cp - gs://trade-workbench-backups-gen-lang-client-0229748590/.planner-verify-*.txt
$ gcloud storage ls gs://trade-workbench-backups-gen-lang-client-0229748590/   # showed the file
$ gcloud storage rm gs://trade-workbench-backups-gen-lang-client-0229748590/.planner-verify-*.txt
Write/list/delete: OK
```

**⚠️ Outstanding scope issue (B021 F005 will fix):**

The VM's default service account has OAuth scope `devstorage.read_only`:

```
$ curl -s -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/scopes
https://www.googleapis.com/auth/devstorage.read_only
https://www.googleapis.com/auth/logging.write
https://www.googleapis.com/auth/monitoring.write
https://www.googleapis.com/auth/service.management.readonly
https://www.googleapis.com/auth/servicecontrol
https://www.googleapis.com/auth/trace.append
```

Instance scopes are an upper bound on what a SA can do via instance metadata — IAM grants beyond scope are ignored. **The IAM `objectAdmin` grant added above will only become effective once the scope is expanded to `devstorage.read_write` (or `cloud-platform`).**

Expansion requires VM stop → modify scopes → start. Operation impact: kolquest.com + staging.kolmatrix + apify-kol-service + pm2 aigcgateway briefly offline (~30-60s for stop+start). B021 F005 will include this as a planned-downtime manual step before deploying backup automation.

**B021 spec impact:** F005 (backup automation) prerequisites section must add:

1. User performs VM scope expansion (`gcloud compute instances stop kolmatrix-vps && gcloud compute instances set-service-account kolmatrix-vps --service-account=$VM_SA --scopes=cloud-platform && gcloud compute instances start kolmatrix-vps`) — with explicit "this causes ~60s downtime for all VM-hosted services" warning.
2. After restart, verify scope via metadata server.
3. Verify VM SA can write to bucket (`gcloud storage cp` from VM as deploy user).
4. Then proceed with backup cron + restore script implementation.

## Item #4 — GCS bucket for SQLite backups

### Prerequisites

- You have access to GCP project (same project as the VM, or a project with billing enabled).
- `gcloud` CLI is installed locally OR you use Cloud Console UI.

### Option A: Via Cloud Console UI

1. Open https://console.cloud.google.com/storage/browser
2. Click **CREATE BUCKET**
3. **Name:** `trade-workbench-backups-<your-project-id>` (must be globally unique; suggest project-id suffix)
4. **Location type:** Region
5. **Location:** **same region as your VM** (e.g., `asia-east1` or whatever your VM is in — egress between VM and bucket in same region is free)
6. **Storage class:** Standard
7. **Access control:** Uniform (recommended)
8. **Public access prevention:** **Enforce public access prevention** (critical — backups contain account state)
9. **Encryption:** Google-managed (default; sufficient)
10. **Object versioning:** **Enable** (allows restore of accidentally-deleted backups)
11. **Lifecycle rules:** add 1 rule:
    - "Delete objects" if "Age > 365 days"
    - (Combined with our 30-daily + 12-monthly retention script in B021 F005, this is a safety net)
12. Click **CREATE**

### Option B: Via gcloud CLI

```bash
# Set project + region (replace with yours):
PROJECT_ID="your-gcp-project-id"
REGION="asia-east1"
BUCKET="trade-workbench-backups-${PROJECT_ID}"

gcloud storage buckets create "gs://${BUCKET}" \
  --project="${PROJECT_ID}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention \
  --enable-versioning

# Add lifecycle rule (delete after 365 days):
cat > /tmp/lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 365}
      }
    ]
  }
}
EOF
gcloud storage buckets update "gs://${BUCKET}" --lifecycle-file=/tmp/lifecycle.json
rm /tmp/lifecycle.json

# Verify:
gcloud storage buckets describe "gs://${BUCKET}" --format="value(name,location,uniformBucketLevelAccess.enabled,publicAccessPrevention,versioning.enabled)"
```

### Service account for VM → GCS write access

The VM's `deploy` user needs write perm to this bucket. Two ways:

- **A (recommended):** Use the VM's default service account, grant it `roles/storage.objectAdmin` on this specific bucket only:
  ```bash
  VM_SA=$(gcloud compute instances describe <vm-name> --zone=<vm-zone> --format='value(serviceAccounts.email)')
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="serviceAccount:${VM_SA}" \
    --role="roles/storage.objectAdmin"
  ```
- **B:** Create a dedicated service account, download JSON key, store on VM. More setup, more rotation burden. Skip unless A doesn't work.

### Verify deploy user on VM can write

```bash
# SSH to VM as deploy:
ssh -i ~/.ssh/trade-deploy deploy@<VM-public-IP>

# On VM:
echo "test backup $(date)" | gcloud storage cp - gs://${BUCKET}/test.txt
gcloud storage ls gs://${BUCKET}/
gcloud storage rm gs://${BUCKET}/test.txt
```

If this works: ✅ done.

If permission denied: check that VM's service account has the role + that `gcloud` is installed on VM (`gcloud --version`).

---

## Item #5 — GitHub Secrets

### Prerequisites

- Item #1 OAuth client secret has been **rotated** (the original was leaked in chat — generate a fresh secret in Google Cloud Console first).
- Item #3 SSH private key file at `~/.ssh/trade-deploy` (the private key, not the `.pub`).
- Generate a NextAuth secret: `openssl rand -hex 32`.

### Steps (Web UI only — never via API or chat)

1. Open https://github.com/tripplemay/trade/settings/secrets/actions
2. Click **New repository secret** for each:

| Secret name | Value source |
|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | from Google Cloud Console → OAuth client detail page |
| `GOOGLE_OAUTH_CLIENT_SECRET` | the **rotated** secret (NEVER the one leaked in chat) |
| `NEXTAUTH_SECRET` | output of `openssl rand -hex 32` (run locally) |
| `ALLOWED_USER_EMAIL` | your single allowlisted Google account email |
| `DEPLOY_SSH_PRIVATE_KEY` | content of `~/.ssh/trade-deploy` (the **private** key file, full multi-line content) |
| `DEPLOY_HOST` | the VM's public IP or hostname |
| `DEPLOY_USER` | `deploy` |

3. After save: each secret shows as `*****` and is unreadable (only updatable / deletable). This is correct.

### Verify

There's no programmatic way to read back a secret. The verification is when B021 F004 (CI/CD pipeline) ships and the GitHub Actions workflow runs successfully against the VM.

---

## Item #5 — partial executed 2026-05-15 (Planner uploaded 5/7 via `gh` CLI)

Planner used the local `gh` CLI (auth `tripplemay` token with `repo` scope) to upload the 5 secrets whose values exist on the local WSL or can be safely generated locally. Values were piped via stdin to `gh secret set` so they never appeared in stdout/stderr/shell-history/git.

| Secret name | Source | Set at |
|---|---|---|
| `NEXTAUTH_SECRET` | `openssl rand -hex 32` generated fresh; not retained anywhere outside GitHub vault | 2026-05-15 06:33:27Z |
| `DEPLOY_SSH_PRIVATE_KEY` | `~/.ssh/trade-deploy` (local WSL only) | 06:33:29Z |
| `ALLOWED_USER_EMAIL` | `tripplezhou@gmail.com` | 06:33:30Z |
| `DEPLOY_USER` | `deploy` | 06:33:32Z |
| `DEPLOY_HOST` | `34.180.93.185` | 06:33:34Z |

**Remaining 2 — pre-staged with placeholder values 2026-05-15 06:45 UTC** at user's request. Slots exist; user must **replace values** via UI before B021 F004 CI/CD ships.

| Secret | Current placeholder | Why placeholder ≠ silent acceptance |
|---|---|---|
| `GOOGLE_OAUTH_CLIENT_ID` | `PLACEHOLDER-REPLACE-ME.apps.googleusercontent.com` | Wrong format for real `<project-number>-<random>.apps.googleusercontent.com`; Google OAuth library will not even accept it as a valid client ID at parse time. |
| `GOOGLE_OAUTH_CLIENT_SECRET` | `PLACEHOLDER-REPLACE-ME-WITH-ROTATED-SECRET` | Wrong prefix (real secrets start with `GOCSPX-`); Google's token endpoint will return `invalid_client` immediately. The literal text `PLACEHOLDER-REPLACE-ME` appears in CI logs, making the cause obvious. |

**Sequence to complete item #5 from here:**

1. User opens Google Cloud Console → Credentials → the OAuth client → "Reset client secret" (deletes the old leaked secret, generates a new one).
2. User opens https://github.com/tripplemay/trade/settings/secrets/actions → click `GOOGLE_OAUTH_CLIENT_ID` → "Update value" → paste real client_id → save.
3. Same UI → click `GOOGLE_OAUTH_CLIENT_SECRET` → "Update value" → paste the **rotated** secret → save.
4. Verify: `gh secret list --repo tripplemay/trade` shows updated timestamps (newer than `2026-05-15T06:45`) on both. Done.

> **Hard rule for B021 F004 CI workflow:** must include a pre-flight step that grep-checks the inflated secrets for the literal text `PLACEHOLDER-REPLACE-ME` and fails the workflow with a clear error message if matched. This is cheap belt-and-braces against the placeholders accidentally going to production.

---

## Done checklist

- [x] #1 OAuth client (rotated 2026-05-15 06:53Z)
- [x] #2 DNS A record `trade.guangai.ai` → VM IP
- [x] #3 VM deploy user + dirs + authorized_keys + sudoers (Planner executed under user auth)
- [x] #4 GCS backup bucket + IAM grant + write test passed (Planner executed via user `gcloud auth login`)
- [x] #5 GitHub Secrets uploaded (7 secrets total: 5 by Planner via `gh`, 2 by user via UI after rotation)

**All 5 prep items ✅ as of 2026-05-15 06:53Z.** B021 F001 prerequisites are complete; spec drafting can proceed when B020 reaches done wrap-up.

### Outstanding B021 F005 prerequisite (separate from prep)

VM service account scope expansion (`devstorage.read_only` → `cloud-platform` or `devstorage.read_write`) requires VM stop / set-scopes / start (~30-60s downtime for kolquest.com + staging.kolmatrix + apify-kol + pm2 aigcgateway). This is **not part of these 5 prep items** — it's part of B021 F005 (backup automation) and will be flagged as a planned-downtime step in that feature's spec.

---

_Disclaimer: research-only; never authorizes paper or live trading._
