# Certbot setup for `trade.guangai.ai`

The nginx vhost in `workbench/deploy/nginx/trade.guangai.ai.conf` references
TLS certificate paths under `/etc/letsencrypt/live/trade.guangai.ai/`.
Those files do not exist until certbot has issued the cert. This is a
**one-time user-action** during the first deploy and is **not** something
the CI workflow performs.

## Prerequisites

| Item | Status |
|---|---|
| DNS A record `trade.guangai.ai → 34.180.93.185` | ✅ Set in B021 prep (2026-05-15) |
| `/var/www/letsencrypt/` directory writeable by certbot | Created on first run |
| Existing certbot installation (the VM already serves `kolquest.com`) | ✅ Present |
| nginx running with kolquest + staging.kolmatrix vhosts | ✅ Present |

## One-time issuance

```bash
# 1. Drop the vhost file into sites-available — but DO NOT enable it yet,
#    because the ssl_certificate paths don't exist.
sudo cp workbench/deploy/nginx/trade.guangai.ai.conf /etc/nginx/sites-available/

# 2. Use certbot's standalone webroot challenge so we don't need the cert
#    to be present in nginx to issue it. The webroot uses the existing
#    /var/www/letsencrypt directory that's already configured for
#    kolquest.com renewals.
sudo certbot certonly --webroot \
  -w /var/www/letsencrypt \
  -d trade.guangai.ai \
  --agree-tos \
  --email YOUR_EMAIL_HERE \
  --no-eff-email

# 3. Now the cert files exist. Symlink the vhost into sites-enabled and
#    reload nginx.
sudo ln -s /etc/nginx/sites-available/trade.guangai.ai.conf \
           /etc/nginx/sites-enabled/trade.guangai.ai.conf
sudo nginx -t && sudo systemctl reload nginx
```

Verify with a remote curl from the user's laptop:

```bash
curl -I https://trade.guangai.ai/api/health
# expect: HTTP/2 200 (after the systemd units come up via F004 deploy)
```

## Automatic renewal

The existing host already runs `certbot.timer` for `kolquest.com`. Once
`trade.guangai.ai` is in `/etc/letsencrypt/live/`, the same timer renews it
on the standard 60-day cycle. Confirm:

```bash
sudo systemctl list-timers --all | grep certbot
sudo certbot certificates  # should list trade.guangai.ai alongside kolquest.com
```

The post-renewal hook in `/etc/letsencrypt/renewal-hooks/deploy/` already
issues `systemctl reload nginx`; no workbench-specific hook required.

## Why this isn't in CI

The certbot issuance flow needs root on the VM and writes to
`/etc/letsencrypt/`. The CI `deploy` user (per the B021 sudoers grant) can
only restart the workbench services and run `daemon-reload`; intentionally
nothing else. Issuing a cert from CI would require widening that surface,
which is exactly what we said no to in the B021 spec safety boundaries.

## Rollback

If certbot issuance is botched (rate limit hit, A record stale, etc.):

```bash
sudo certbot delete --cert-name trade.guangai.ai
sudo rm /etc/nginx/sites-enabled/trade.guangai.ai.conf
sudo nginx -t && sudo systemctl reload nginx
```

Then fix the prerequisite and re-run the one-time issuance block above.
