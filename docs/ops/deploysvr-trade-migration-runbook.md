# Trade 生产迁移 Runbook — deploysvr（B107 F002）

> 批次：B107-prod-migrate-deploysvr · 对标已实操验证的 `~/project/joyce/docs/ops/deploysvr-kol-migration-runbook.md`（同一台 deploysvr，2026-07-13 完成）+ 本仓 `docs/dev/B021-vm-setup-runbook.md`（原生栈建机手册）。
> 本文档是**受监督实操**手册。标 🔴 的三个不可逆门禁执行前必须取得用户显式 go/no-go。

## 拓扑（原生 systemd，与 deploysvr 现有 docker 栈共存）

```
用户 → Cloudflare DNS trade.guangai.ai → 194.238.26.173 (deploysvr 公网)
     → deploysvr host nginx :80/:443 (Certbot DNS-01, trade.guangai.ai.conf)
       → 127.0.0.1:8723 (FastAPI backend, systemd workbench-backend.service)
       → 127.0.0.1:3003 (Next.js frontend, systemd workbench-frontend.service)
     → SQLite /var/lib/workbench/db/workbench.db
     → ~19 timer + backtest-worker daemon (systemd, User=deploy)
     → 本地磁盘轮转备份 /var/backups/workbench (B107 F001, 无 gcloud)
外调：LLM → https://aigc.guangai.ai（同机 aigc）；行情 → Tiingo/SEC EDGAR/FRED/AlphaVantage/akshare/baostock（公网）
```

与既有 aigc/kol/invoce/design/tokenizer 块共存：nginx `server_name trade.guangai.ai`（无 default_server）+ loopback 端口 8723/3003（不撞 kol 3000-3002）互不冲突。**Trade 是 deploysvr 首个原生（非容器）应用。**

## 源 / 目标

| | 老机（源，退役中） | 新机（目标 deploysvr） |
|---|---|---|
| Host | `34.180.93.185`（GCP 东京，`ssh tripplezhou@…`） | `194.238.26.173`（`ssh deploysvr`，root，key `~/.ssh/kolmatrix_new`） |
| 运行 | 原生 systemd + venv | 同左（照搬） |
| 账户 | `deploy` 用户 | 新建 `deploy` 用户 |
| DB | SQLite `/var/lib/workbench/db/workbench.db`（个位数 MB） | 同左（文件 copy） |
| data | `/var/lib/workbench/data` | 同左（整体 copy） |
| venv | `/opt/workbench/.venv`（py3.11 + akshare/baostock） | 同左（**需先装 py3.11 + sqlite3 + 编译依赖**） |
| 备份 | SQLite → GCS | 本地磁盘轮转（`WORKBENCH_BACKUP_TARGET=local`，B107 F001） |
| 边缘 | 老机 nginx + certbot | deploysvr host nginx（加 vhost）+ certbot DNS-01（CF token） |
| CI/CD | GitHub Actions（DEPLOY_HOST=老机） | 同左（仅更 secret 值 → 新机） |

**secrets 铁律（H1）：** `NEXTAUTH_SECRET` / OAuth client secret / 各 API key 通过 **bootstrap-env workflow** 从 GitHub Secrets 注入新机 `/etc/workbench/workbench.env`（640 root:deploy），**绝不写入仓库或本文档**。`NEXTAUTH_SECRET` 复用 GitHub Secret 同值 → 会话不失效。

---

## 预检清单（P0 前，均须 ✅）

- [ ] **R3 老机 SSH host key 已变**：`ssh tripplezhou@34.180.93.185` 目前被 strict check 拦下（本机 `~/.ssh/known_hosts` line 33 是旧 key）。**须带外核实老机真实指纹**（GCP 控制台串口/或用户确认），确认非 MITM 后 `ssh-keygen -R 34.180.93.185` 清旧记录 + 重新 `ssh-keyscan` 写入。**未解不能拉数据（P3 阻塞）。**
- [ ] deploysvr 可达：`ssh deploysvr 'echo ok'` → ok ✅（已验）
- [ ] certbot + `/root/.secrets/cloudflare.ini` 就绪 ✅（已验，guangai.ai zone 覆盖）
- [ ] GitHub Secrets 齐备（迁移不新增，复用）：`DEPLOY_HOST/DEPLOY_USER/DEPLOY_SSH_PRIVATE_KEY/DEPLOY_SSH_KNOWN_HOSTS` + `GOOGLE_OAUTH_CLIENT_ID/SECRET` + `NEXTAUTH_SECRET` + `ALLOWED_USER_EMAIL` + `TIINGO_API_KEY` + `SEC_EDGAR_CONTACT_EMAIL` + `AIGC_GATEWAY_API_KEY` + `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY`
- [ ] 记录回滚值：老 `DEPLOY_HOST=34.180.93.185`；老机 Cloudflare A `34.180.93.185`

---

## P0 — 准备（可逆，老机照跑）

### P0.1 老机访问恢复（解 R3）
```bash
# 带外核实指纹后：
ssh-keygen -R 34.180.93.185
ssh-keyscan -t ed25519 34.180.93.185 >> ~/.ssh/known_hosts   # 核实指纹与带外一致后
ssh tripplezhou@34.180.93.185 'echo ok; sudo du -sh /var/lib/workbench/data /var/lib/workbench/db'
```

### P0.2 deploysvr 加 swap（解 H4/R1，无 swap 兜底 OOM）
```bash
ssh deploysvr 'test -f /swapfile || (fallocate -l 6G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && grep -q /swapfile /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab); free -h'
```

### P0.3 装 python3.11 + sqlite3 + 编译依赖（解 R4/R6/F001 gap）
```bash
ssh deploysvr 'apt-get update && apt-get install -y python3.11 python3.11-venv python3.11-dev sqlite3 build-essential nodejs npm; python3.11 --version; sqlite3 --version; node --version'
# 若发行版无 python3.11 → 加 deadsnakes PPA 或 pyenv（B021 runbook 有备选）
```

### P0.4 建 deploy 用户 + 目录（对标 B021 runbook Item #3）
```bash
ssh deploysvr '
  id deploy 2>/dev/null && echo "WARN deploy exists — investigate" || useradd -m -s /bin/bash deploy
  install -d -o deploy -g deploy -m 0755 /srv/workbench /srv/workbench/releases /opt/workbench
  install -d -o deploy -g deploy -m 0750 /var/lib/workbench /var/lib/workbench/db /var/lib/workbench/data
  install -d -o deploy -g deploy -m 0755 /var/log/workbench
  install -d -o deploy -g deploy -m 0750 /var/backups/workbench
  su - deploy -c "python3.11 -m venv /opt/workbench/.venv && /opt/workbench/.venv/bin/pip install --upgrade pip"
'
```

### P0.5 deploy SSH key + sudoers wrapper
```bash
# 生成新 deploy 密钥（新机新钥），公钥授权到 deploysvr 的 deploy；私钥进 GitHub Secret（P4 更）
ssh-keygen -t ed25519 -f ~/.ssh/trade-deploy-deploysvr -N '' -C 'trade-deploy@deploysvr'
ssh deploysvr 'install -d -o deploy -g deploy -m 700 /home/deploy/.ssh'
cat ~/.ssh/trade-deploy-deploysvr.pub | ssh deploysvr 'cat >> /home/deploy/.ssh/authorized_keys && chown deploy:deploy /home/deploy/.ssh/authorized_keys && chmod 600 /home/deploy/.ssh/authorized_keys'
ssh -i ~/.ssh/trade-deploy-deploysvr deploy@194.238.26.173 'echo deploy-login-ok'
# sudoers（从仓库 checkout 或 scp workbench/deploy/sudoers/*）：
#   /etc/sudoers.d/deploy-workbench (444 root:root) — systemctl restart/enable/daemon-reload 白名单
#   /usr/local/bin/workbench-install-unit (0755 root:root) — 单元安装 wrapper（拒路径分隔符）
# 详见 B021-vm-setup-runbook.md §sudoers；`visudo -cf` 校验后生效
```

### P0.6 落生产 env（bootstrap-env workflow，H1）
```bash
# 临时把 deploy secrets 指向 deploysvr（迁移窗口内不推产品码 → 不触发 CI/部署链）：
gh secret set DEPLOY_HOST -b 194.238.26.173
gh secret set DEPLOY_USER -b deploy
gh secret set DEPLOY_SSH_PRIVATE_KEY < ~/.ssh/trade-deploy-deploysvr
ssh-keyscan -t ed25519 194.238.26.173 | gh secret set DEPLOY_SSH_KNOWN_HOSTS
# 跑 bootstrap-env（NEXTAUTH_SECRET 同值 → 会话保）：
gh workflow run bootstrap-env.yml -f confirm=bootstrap-env
# 完成后 admin(root) 装 env + 追加 local 备份 target：
ssh deploysvr '
  install -m 640 -o root -g deploy /home/deploy/.bootstrap/workbench.env /etc/workbench/workbench.env
  rm /home/deploy/.bootstrap/workbench.env
  grep -q WORKBENCH_BACKUP_TARGET /etc/workbench/workbench.env || printf "WORKBENCH_BACKUP_TARGET=local\nWORKBENCH_BACKUP_DIR=/var/backups/workbench\n" >> /etc/workbench/workbench.env
'
```
> ⚠️ DEPLOY_HOST 指向新机后，**迁移窗口内不要向 main 推产品码**（否则绿 CI 会把新机当部署目标）；仅推 paths-ignored 状态/文档文件（不触发 CI）。回滚值 `DEPLOY_HOST=34.180.93.185` 已记。

### P0.7 装 backend/frontend systemd 单元（★实操发现：deploy.sh 不装）
**deploy.sh 假设 backend/frontend `.service` 已由 B021 预装**——首次部署到全新机会在 `systemctl restart workbench-backend.service` 报 `Unit not found` 而 exit 5（deploy.sh 前段 wheel/alembic/price-prime 全成功）。首次 CI deploy 会把 release scp 到 `/srv/workbench/releases/<sha>/`，据此 root 装全部单元：
```bash
ssh deploysvr 'SYSD=/srv/workbench/current/systemd; for u in "$SYSD"/workbench-*.service "$SYSD"/workbench-*.timer; do install -m644 -o root -g root "$u" /etc/systemd/system/; done; systemctl daemon-reload; systemctl enable --now workbench-backend workbench-frontend workbench-backtest-worker; for t in "$SYSD"/workbench-*.timer; do systemctl enable --now "$(basename "$t")"; done'
```

---

## P2 — 起新栈 + 演练（可逆，老机仍主服务，DNS 未切）

> ⚠️ **DNS 切换前 CI deploy 注定红**：workflow 的 healthcheck/synthetic 探 public `trade.guangai.ai`，DNS 仍指老机 → synthetic check(3)「HEAD≡prod SHA」必不匹配 FAIL → 触发 rollback（首次无 prior release，no-op exit 66）→ workflow 红，**但 deploysvr 栈实际已起来**。P2 一律用 **loopback**（`curl 127.0.0.1:8723/api/health`）验收，不看 CI 红绿；P4 DNS 切后 CI deploy 才真绿。

### P2.1 首次部署到新机
```bash
# 手动 dispatch Deploy workflow（DEPLOY_HOST 已指新机）→ build+scp+deploy.sh：
gh workflow run workbench-deploy.yml -f ref=main
# deploy.sh 会：装 backend+trade wheel → alembic upgrade head（空库建 schema）→ symlink flip →
#   restart backend/frontend → install+enable 全部 timer + backtest-worker
```
> 若 akshare/baostock 未随 backend wheel 传递依赖装上 → 补 `su - deploy -c '/opt/workbench/.venv/bin/pip install akshare baostock'`，验 `import akshare, baostock`。

### P2.2 装 nginx vhost（loopback 冒烟用；DNS 未切，公网仍走老机）
```bash
ssh deploysvr '
  install -d -m 755 /var/www/letsencrypt
  cp /srv/workbench/current/deploy/nginx/trade.guangai.ai.conf /etc/nginx/sites-available/trade.guangai.ai.conf
  # 证书未签前不要 symlink 443 块（nginx -t 会红）——先 certbot DNS-01 预签（见 P4.1），或先只放 80 块
'
```

### P2.3 灌老库快照 + data（演练用，非终态）
```bash
# 老机在线快照（.backup WAL 安全）→ 落文件 → scp 老→新直传（H5 勿经本机）：
ssh tripplezhou@34.180.93.185 'sqlite3 /var/lib/workbench/db/workbench.db ".backup /tmp/wb-rehearse.db" && gzip -f /tmp/wb-rehearse.db'
ssh tripplezhou@34.180.93.185 'cat /tmp/wb-rehearse.db.gz' | ssh deploysvr 'systemctl stop workbench-backend; gunzip -c > /var/lib/workbench/db/workbench.db; chown deploy:deploy /var/lib/workbench/db/workbench.db; chmod 600 /var/lib/workbench/db/workbench.db'
# data 目录（rsync 老→新直传；两端云机快路径）：
ssh tripplezhou@34.180.93.185 'sudo tar -C /var/lib/workbench -czf /tmp/wb-data.tgz data' 
ssh tripplezhou@34.180.93.185 'cat /tmp/wb-data.tgz' | ssh deploysvr 'tar -C /var/lib/workbench -xzf - && chown -R deploy:deploy /var/lib/workbench/data'
ssh deploysvr 'cd /srv/workbench/current/backend && /opt/workbench/.venv/bin/python -m alembic upgrade head; systemctl start workbench-backend'
```

### P2.4 loopback 冒烟（不碰公网）
```bash
ssh deploysvr '
  curl -s http://127.0.0.1:8723/api/health          # 200 db_connectivity:ok
  systemctl is-active workbench-backend workbench-frontend
  systemctl is-active workbench-backtest-worker
  systemctl list-timers "workbench-*" --all | head
'
# 端口转发登录（验 NEXTAUTH_SECRET 同值）+ 触一次 recommendations precompute + 一次 backtest。
# F001 备份 local 冒烟：装 backup unit（README §Install）→ systemctl start workbench-backup.service →
#   ls /var/backups/workbench/daily/ 有文件 + tail /var/log/workbench/backup.log。
# 任一失败 → 修 env/venv/单元，不进 P3。
```

---

## P3 — 🔴 数据终态同步（不可逆门禁 1：需用户 go/no-go）

```bash
# 1. 停老机写入（backend + 全 timer + worker），DB 保留可回滚：
ssh tripplezhou@34.180.93.185 'sudo systemctl stop workbench-backend workbench-frontend workbench-backtest-worker "workbench-*.timer"'
# 2. 终态一致快照 → scp 老→新直传（H5）：
ssh tripplezhou@34.180.93.185 'sqlite3 /var/lib/workbench/db/workbench.db ".backup /tmp/wb-final.db" && gzip -f /tmp/wb-final.db'
ssh deploysvr 'systemctl stop workbench-backend "workbench-*.timer" workbench-backtest-worker'
ssh tripplezhou@34.180.93.185 'cat /tmp/wb-final.db.gz' | ssh deploysvr 'gunzip -c > /var/lib/workbench/db/workbench.db; chown deploy:deploy /var/lib/workbench/db/workbench.db; chmod 600 /var/lib/workbench/db/workbench.db'
# data 终态增量（同 P2.3 tar 直传，覆盖演练态）
# 3. alembic no-op + 起全栈：
ssh deploysvr 'cd /srv/workbench/current/backend && /opt/workbench/.venv/bin/python -m alembic upgrade head; systemctl start workbench-backend workbench-frontend; systemctl start "workbench-*.timer" workbench-backtest-worker'
# 4. parity 校验（关键表行数逐表比对）：
SQL="SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
# 对每张关键表：ssh 老机 sqlite3 count(*) vs ssh deploysvr sqlite3 count(*) → 逐表一致
```

---

## P4 — 🔴 边缘割接 / DNS（不可逆门禁 2：需用户 go/no-go）

```bash
# 1. Certbot DNS-01 预签（DNS 未切也能签，零 TLS 空窗）：
ssh deploysvr 'certbot certonly --dns-cloudflare --dns-cloudflare-credentials /root/.secrets/cloudflare.ini -d trade.guangai.ai'
# 2. 启用 nginx vhost（含 443 块）+ reload：
ssh deploysvr 'ln -sf /etc/nginx/sites-available/trade.guangai.ai.conf /etc/nginx/sites-enabled/ && nginx -t && systemctl reload nginx'
# 3. 切 DNS（Cloudflare，proxied=False 直连，与 aigc/kol 一致）：
#    trade.guangai.ai A 记录 34.180.93.185 → 194.238.26.173，TTL 先 60。
# 4. 公网验证（外部）：
curl -I https://trade.guangai.ai/api/health          # 200 + 证书有效
curl -s https://trade.guangai.ai/api/health          # db_connectivity:ok
#    浏览器登录（prod 账号，验会话）；根路径应用重定向 + /api/* 401 应用认证（活面双证，对标 B097）。
# 5. push-to-deploy 打通验证（DEPLOY_HOST 已在 P0.6 指新机）：
gh workflow run workbench-deploy.yml -f ref=main    # 或一次 main code push → 自动链式 → 健康检查全绿
# 6. 装 F001 本地备份 timer（若 P2.4 未装）+ 确认 daily 落文件。
```

---

## P5 — 观察期 + 回滚就绪

- 老机：workbench 全栈 **STOPPED**，DB **冻结不写**（作一致性回退点）。
- 保留：老机 nginx/DNS 旧配置、`DEPLOY_HOST` 旧值 `34.180.93.185`、老 DB 快照。
- 观察窗口由用户定；监控新机健康/错误率/timer 执行/LLM 调用/备份。
- **用户明确验收（含中国访问体验）前不进入 P6。**

## P6 — 🔴 老 VM 整机退役（不可逆门禁 3：需用户 go/no-go）

- 仅在用户显式验收后执行。
- aigc + kolmatrix + trade 三拼图齐 → **老 GCP VM 整机退役/删除**。
- 退役前最后确认：新机稳定 + 本地备份就位（可选补异地）。GCS 备份桶 `gs://trade-workbench-backups-…` 去留由用户定（老机退役后不再写入）。

---

## 🔴 回滚手册

- **流量回滚**：Cloudflare `trade.guangai.ai` A 改回 `34.180.93.185`；`gh secret set DEPLOY_HOST -b 34.180.93.185`；老机 `sudo systemctl start workbench-backend workbench-frontend "workbench-*.timer" workbench-backtest-worker`。
- **DB 回滚（新机内）**：`sudo -u deploy WORKBENCH_BACKUP_TARGET=local bash /srv/workbench/current/deploy/backup/workbench-restore.sh <snapshot> --force`。
- P3 之后老机 DB 冻结未写，回滚无数据丢失窗口（**P3 后新机新写数据在回滚时会丢** → 割接决策须尽早）。单用户研究系统，回滚代价低。

## 不可逆门禁清单（执行前必须用户 go/no-go）
1. 🔴 P3 数据终态同步（停老机写入 + 终态 restore）
2. 🔴 P4 DNS 切换（trade.guangai.ai → 新机）
3. 🔴 P6 老 VM 整机退役

---

## 割接实测记录（待回填）

> 对标 KOL runbook 的 "Last verified / 停机窗口 / Live state / Verified parity / Rollback controls"。P3+P4 完成后回填。

- **Last verified:** 2026-07-13 ~07:26Z（P0→P4 一次性完成，观察期开始）。
- **停机窗口:** 老机冻结 ~07:20Z（P3.1）→ DNS 切 ~07:24Z（TTL60，1.1.1.1/8.8.8.8 已传播）→ 恢复 **~几分钟**。★H5 生效：DB(8.7MB gz)+data(63MB gz) 走 **老机→deploysvr cloud-to-cloud 直传**（本机 Mac 因 Clash fake-ip 代理连老机会打到错机，全程 deploysvr 编排），远快于 KOL 经本机的 28min。
- **Live state:** deploysvr（`vmi3430901`/194.238.26.173，Ubuntu 24.04）三服务 active（workbench-backend 8723 / workbench-frontend 3003 / workbench-backtest-worker）+ 17 timer；release SHA `e5e202e`；venv python3.11.15（akshare/baostock/numpy/pandas via backend wheel）；`/api/health` db-ok。
- **Verified parity:** 18 关键表逐行 **完全一致（DIFFS=0）**：price_snapshot 26986 / price_history 18463 / news 7815 / symbol_price_cache 5022 / recommendation_snapshot 724 / advisor_recommendation 134 / market_context_observation 154 / backtest_run 48 / investment_report 34 / tiingo_budget_log 38 / account_snapshot 7 / symbol_fundamentals_cache 8 / backlog_entry·snapshot_meta·order_ticket·backtest_data_window 各 1 / account·fill_journal_entry 0。alembic upgrade head no-op。
- **DNS / Edge / TLS:** Cloudflare `trade.guangai.ai` A `34.180.93.185`→`194.238.26.173`（proxied=False，TTL60，zone `ca43cb02…`，record `a910644a…`，旧值回滚用）；certbot DNS-01（CF token）证书 CN=trade.guangai.ai 到期 2026-10-11；nginx vhost `/etc/nginx/sites-enabled/trade.guangai.ai.conf`（与 aigc/kol/invoce 共存，SNI 正确）。
- **CI/CD:** GitHub secrets 已更 `DEPLOY_HOST=194.238.26.173 / DEPLOY_USER=deploy / DEPLOY_SSH_PRIVATE_KEY(新 CI 密钥) / DEPLOY_SSH_KNOWN_HOSTS`；旧 `DEPLOY_HOST=34.180.93.185` 回滚记录。★DNS 切前 CI deploy 因 synthetic 探 public(老机)必红——切后才真绿（push-to-deploy 验证在 P5/F003）。本地备份 `WORKBENCH_BACKUP_TARGET=local`（/var/backups/workbench，daily 03:00 timer，smoke 已过）。
- **Rollback controls:** ①流量回滚：Cloudflare `trade.guangai.ai` A 改回 `34.180.93.185`（record `a910644a…`）+ `gh secret set DEPLOY_HOST -b 34.180.93.185` + 老机 `sudo systemctl start workbench-backend workbench-frontend "workbench-*.timer" workbench-backtest-worker`。②DB 回滚：deploysvr `WORKBENCH_BACKUP_TARGET=local workbench-restore.sh <snap> --force`。③老机全栈 **STOPPED 冻结**、DB 未写（P3 后）→ 回滚零丢失（P3 后新机新写会丢，故回滚要早）。
- **⚠️ 观察期门禁:** 用户明确验收前不进 P6（老机 workbench 下线 + 老 VM 整机退役）。老机现仅 workbench 冻结，其它已无租户（aigc+kol 早迁）→ 用户验收后老 VM 可整机退役。
