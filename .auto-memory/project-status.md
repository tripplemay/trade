---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B107 生产迁移 🔨 building（2026-07-12, 2g+1c）** trade 从退役中 GCP VM（`34.180.93.185`）迁至 **deploysvr（`194.238.26.173`）**。trade 是老 VM 最后活租户（aigc+kol 已迁）→ 迁完老 VM 整机退役。原生 systemd 栈照搬（不容器化）；域名 `trade.guangai.ai` 不变（OAuth/会话保）；单用户高停机容忍。spec `docs/specs/B107-prod-migrate-deploysvr-spec.md`；runbook `docs/ops/deploysvr-trade-migration-runbook.md`。
- **F001 ✅ done**：备份改道 `WORKBENCH_BACKUP_TARGET=gcs|local`（default gcs 不变；local=`/var/backups/workbench` 轮转，无 gcloud）。真代码验：local prune 保 N 最新+存活快照 sqlite quick_check ok。
- **F002 ✅ 割接完成（2026-07-13 ~07:26Z，用户「直接割接」go，P5 观察期中）**：P0 provisioning（swap/py3.11/node20/sqlite3/deploy 用户+目录+venv/sudoers/37 单元/env/CD secrets）→ P3 数据终态割接（**parity 18 表 DIFFS=0**）→ P4 DNS 切（Cloudflare A→194.238.26.173，proxied=false TTL60）→ F001 本地备份 smoke 过。runbook 实测已回填。
- **★活生产已切 deploysvr**：`https://trade.guangai.ai` 命中 `194.238.26.173`（db-ok+活面双证+证书 CN 对）；老机 `34.180.93.185` 全栈**冻结作回滚点**（DB 未写=零丢失）。
- **★关键坑（本机专属）**：本机 Mac 在 Clash fake-ip 代理后，连老机 `34.180.93.185` 会被路由到**错的机器**（host key mHOXFC≠真机 a6Hui）→ 一律 `ssh deploysvr` 再跳 `tripplezhou@34.180.93.185`（key `/root/.ssh/oldvm_migrate`）。data/DB 直传全走 deploysvr cloud-to-cloud（H5）。
- **B106/B105/B104/B103/B102–B074 ✅**。

## 接续 / 待决策
- **★F002 收尾**：push-to-deploy 验证（DNS 切后 CI deploy 应真绿）→ 交 F003 Codex 验收（公网冒烟/parity/回滚就绪/signoff）。
- **★P6 🔴 老 VM 退役**：观察期后用户明确验收才做（老机仅 workbench 冻结，aigc+kol 早迁 → 拼图齐，可整机退役）。
- **回滚值已记**：老 `DEPLOY_HOST=34.180.93.185`；Cloudflare `trade.guangai.ai` A 旧值 `34.180.93.185`（record `a910644a…`）；老机全栈可 `systemctl start` 拉起。
- backlog 剩（迁移后再议）：A股聪明钱 ¥200 + residual-engine（B100 INCONCLUSIVE）+ B106-S3（4-sleeve risk_parity 无防守腿隔离测）。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。
- **★负责人纪律**：验收结论 git 核实才采信（B104/B105 幻觉消息教训）。

## 永久硬边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO）**。红利低波留 A股本土组合才兑现负相关分散（跨进 USD 组是放错市场）。
- cn_attack 研究态/OOS 红卡不可配资。冻结再验证 pipeline **永不** validated→True。golden 只进测试 fixture seam。**smart-money 免费信号 first-look 均 research-only（0 产品码）无一切入生产。**

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点。
- **v0.9.55**（f67332e, 2026-07-06）：B080-B098 队列 9 条 learnings 沉淀。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（改 trade/ 后须重装）。scipy 本机未装，独立复算自写 Pearson/秩相关。
