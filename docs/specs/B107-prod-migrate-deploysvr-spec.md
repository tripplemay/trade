# B107 — Trade 生产环境迁移 → deploysvr（规格）

> 批次类型：混合（2 generator + 1 codex）· 状态流转 planning → building → verifying → done
> 对标已实操验证：`~/project/joyce/docs/ops/deploysvr-kol-migration-runbook.md`（同一台 deploysvr，2026-07-13 P3+P4 完成）+ 本仓 `docs/dev/B021-vm-setup-runbook.md`（原生栈建机手册）
> 本批含**受监督实操**：标 🔴 的三个不可逆门禁执行前必须取得用户显式 go/no-go。

## 1. 背景与目标

老 GCP VM（`34.180.93.185`，东京，hostname `instance-20260403-154049`）即将退役。aigc、KOLMatrix 已先后迁至 **deploysvr**（`194.238.26.173`，ssh 别名 `deploysvr`，key `~/.ssh/kolmatrix_new`，User root）。**Trade（`trade.guangai.ai`）是老 VM 上最后一个活租户**——迁完 → 老 VM 可整机退役。

**目标：** 把 trade 生产（backend + frontend + 全部 systemd timer/worker + SQLite DB + data 快照 + 备份）迁到 deploysvr，域名/会话/OAuth 不变，push-to-deploy 指向新机，老机冻结作回滚点，用户验收后退役老 VM。

## 2. 源 / 目标拓扑

| | 老机（源，退役中） | 新机（目标 deploysvr） |
|---|---|---|
| Host | `34.180.93.185`（GCP，`ssh tripplezhou@…`） | `194.238.26.173`（`ssh deploysvr`，root，key `~/.ssh/kolmatrix_new`） |
| 运行模型 | **原生 systemd + venv**（保持不变） | 同左（deploysvr 首个非容器应用，与 kol/aigc/invoce docker 栈共存） |
| 部署账户 | `deploy` 用户 + sudoers wrapper | 同左（**新建 `deploy` 用户**——37 unit 全 `User=deploy`，改动最小） |
| 部署路径 | `/srv/workbench/{releases,current}` | 同左 |
| venv | `/opt/workbench/.venv`（py3.11 + akshare/baostock） | 同左（**deploysvr 需先装 python3.11 + 编译依赖**） |
| DB | SQLite `/var/lib/workbench/db/workbench.db` | 同左（**文件级 copy 割接**） |
| data | `/var/lib/workbench/data`（news/market-context/price 快照） | 同左（整体 copy，保已抓限流快照） |
| 端口 | backend 127.0.0.1:8723 / frontend 127.0.0.1:3003 | 同左（与 kol 3000-3002、aigc 无冲突） |
| 备份 | SQLite → **GCS**（`gcloud storage cp`） | **本地磁盘轮转**（deploysvr 无 gcloud）→ 见 F001 |
| 边缘 | 老机 nginx + certbot | deploysvr host nginx（加 trade vhost 共存）+ certbot DNS-01（CF token，guangai.ai zone 已覆盖） |
| CI/CD | GitHub Actions（绿 CI 自动链式部署） | 同左（**无 workflow 改写**——只更 secret 值 DEPLOY_HOST/KEY/KNOWN_HOSTS） |

**不变量（降风险）：** 域名 `trade.guangai.ai` 不变 → Google OAuth 回调 URI 无需改；`NEXTAUTH_SECRET` 从 GitHub Secret 复用同值（bootstrap-env workflow）→ 会话不失效。单用户研究系统（`ALLOWED_USER_EMAIL` 单人）→ 停机容忍度高。

## 3. 硬约束（H）

- **H1 secrets 铁律：** `NEXTAUTH_SECRET` / OAuth client secret / 各 API key 通过 bootstrap-env workflow 从 GitHub Secrets 注入新机 `/etc/workbench/workbench.env`（640 root:deploy），**绝不写入仓库或本文档**。`NEXTAUTH_SECRET` 须与老机同值（复用 GitHub Secret）否则会话失效。
- **H2 不可逆门禁 go/no-go：** P3 数据终态割接（停老机写）/ P4 DNS 切换 / P6 老 VM 退役——三处执行前必须用户显式 go/no-go。
- **H3 老机冻结回滚点：** P3 后老机全栈 STOPPED + DB 冻结不写，作零丢失回退点；保留旧 DNS 值 `34.180.93.185` + 旧 DEPLOY_HOST secret 值。
- **H4 内存/OOM：** deploysvr 7.8G 无 swap，已托 kol/aigc/invoce。迁移前先加 4–8G swap；backend/frontend systemd `MemoryMax=2G`+`OOMScoreAdjust=500` 保护邻居（workbench 做优先 OOM 牺牲者）。
- **H5 直传铁律（KOL 教训）：** 大文件（DB/data）终态同步走**老机落文件 → scp 老→新直传**（两端云机快路径），**勿经本机 Mac 管道中转**（KOL 割接因此慢 28min）。
- **H6 research-safe 边界不破：** 迁移不碰任何策略/product 代码逻辑；no-broker / no 自动下单 / research-only 边界原样保持。

## 4. 功能列表（features.json 权威，此处为设计说明）

- **F001（generator）备份改道**：`workbench-backup.sh` / `workbench-restore.sh` 增加目标分派（`WORKBENCH_BACKUP_TARGET=gcs|local`），default `gcs` 向后兼容（老机零回归），deploysvr 用 `local`（`/var/backups/workbench/{daily,monthly}` 轮转，无 gcloud 依赖）。快照/gzip/保留-prune 逻辑目标无关复用。README 增补 deploysvr local 段。
- **F002（generator）provisioning + runbook + P0-P6 割接实操**：新增 `docs/ops/deploysvr-trade-migration-runbook.md`；照 B021 runbook 在 deploysvr 建 deploy 用户/目录/venv/sudoers/swap；bootstrap-env 落 env；rsync release + deploy.sh 起栈演练；P3🔴 数据终态割接；P4🔴 DNS+nginx+certbot+更新 GitHub Secrets；P5 观察；P6🔴 老 VM 退役。回写实测 live state/parity/rollback。
- **F003（codex）验收 + signoff**：公网 `https://trade.guangai.ai` 冒烟（/api/health + 登录会话 + 一次 recommendations/backtest）+ DB 表行数 parity + push-to-deploy 打通验证 + 回滚就绪核实 + signoff（含命令/日志证据）。

## 5. 割接阶段（runbook 权威，此处为门禁摘要）

| 阶段 | 可逆性 | 门禁 |
|---|---|---|
| P0 准备（swap/py3.11/deploy 用户/目录/venv/sudoers/env） | 可逆 | 无 |
| P2 起新栈 + 灌快照演练 + loopback 冒烟 | 可逆（老机主服务） | 无 |
| **P3 数据终态割接**（停老机写→snapshot→scp 直传→起新栈→parity） | **不可逆** | 🔴 go/no-go |
| **P4 边缘割接**（certbot DNS-01→nginx vhost→Cloudflare A 切→更新 secrets） | **不可逆** | 🔴 go/no-go |
| P5 观察期 + 回滚就绪 | — | 用户验收前不进 P6 |
| **P6 老 VM 退役** | **不可逆** | 🔴 go/no-go |

## 6. 验收标准（F003）

1. 公网 `https://trade.guangai.ai/api/health` 200 + `db_connectivity:ok` + 证书有效；根路径应用重定向 + `/api/*` 401 应用认证（活面双证，对标 B097）。
2. 用 prod 账号登录会话正常（验 `NEXTAUTH_SECRET` 同值 + OAuth 域不变）。
3. DB 关键表行数与老机冻结态一致（零丢失）；alembic at head。
4. 至少一次 recommendations precompute + 一次 backtest 在新机跑通（验 venv trade wheel + akshare/baostock + timer/worker）。
5. push-to-deploy 打通：手动 dispatch 或一次 main push → 自动链式部署到新机健康检查全绿。
6. 回滚路径成立（Cloudflare A 可回 `34.180.93.185` + 旧 secret 值 + 老机可拉起），不真正回滚。
7. signoff `docs/test-reports/B107-prod-migrate-deploysvr-signoff-YYYY-MM-DD.md` 逐条证据 + PASS/FAIL。

## 7. 回滚

- **流量回滚：** Cloudflare `trade.guangai.ai` A 改回 `34.180.93.185`；`gh secret set DEPLOY_HOST -b 34.180.93.185`；老机 `sudo systemctl start workbench-backend workbench-frontend + timers`。
- **数据：** P3 后老机 DB 冻结未写 → 回滚零丢失窗口（新机 P3 后新写数据回滚会丢，故割接决策要早）。
- **DB 级：** 新机 `workbench-restore.sh`（local target）从本地轮转备份恢复。

## 8. 风险登记（详见 plan 对话）

R1 内存/OOM(HIGH,H4 swap) · R2 GCS 备份断(HIGH,F001) · R3 老机 SSH host key 已变(MED,P0 带外核实指纹) · R4 原生栈 provisioning 面大(MED,B021 照搬) · R5 push-to-deploy secret 重指(MED,P4) · R6 akshare/baostock 原生编译(LOW,P0 rehearse) · R7 TLS DNS-01 vs HTTP-01(LOW,预签) · R8 会话/OAuth(LOW,同值+域不变)。
