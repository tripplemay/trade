---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B107 生产迁移 🔨 building（2026-07-12, 2g+1c）** trade 从退役中 GCP VM（`34.180.93.185`）迁至 **deploysvr（`194.238.26.173`）**。trade 是老 VM 最后活租户（aigc+kol 已迁）→ 迁完老 VM 整机退役。原生 systemd 栈照搬（不容器化）；域名 `trade.guangai.ai` 不变（OAuth/会话保）；单用户高停机容忍。spec `docs/specs/B107-prod-migrate-deploysvr-spec.md`；runbook `docs/ops/deploysvr-trade-migration-runbook.md`。
- **F001 ✅ done**：备份改道 `WORKBENCH_BACKUP_TARGET=gcs|local`（default gcs 不变；local=`/var/backups/workbench` 轮转，无 gcloud）。真代码验：local prune 保 N 最新+存活快照 sqlite quick_check ok。
- **F002 🔨 runbook 已落地，execution 停在 P0 边界待用户 go**：P0 provisioning + P2 演练 + P3🔴 数据 + P4🔴 DNS + P5 观察 + P6🔴 退役。
- **★实测 deploysvr**：磁盘 121G 足；内存 7.8G 无 swap 已托 kol/aigc/invoce（P0.2 加 6G swap 兜 OOM）；无 py3.11/sqlite3/deploy 用户/gcloud。端口 8723+3003 不撞 kol。无 workflow 改写（仅翻 DEPLOY_HOST 等 secret 值）。
- **B106/B105/B104/B103/B102–B074 ✅**。活生产 API=`trade.guangai.ai`（当前仍老机服务）。

## 接续 / 待决策
- **★F002 三阻塞/门禁需用户**：(a) **R3 老机 SSH host key 已变** → 带外核实指纹后修 `~/.ssh/known_hosts` line 33（否则 P3 拉数据阻塞）；(b) P0 系统变更+翻 deploy secrets 须 go；(c) P3 数据/P4 DNS/P6 退役三 🔴 逐个 go/no-go。用户 go 后按 runbook 逐阶段执行，每 🔴 前停 → 完成回填 runbook 实测 → 交 F003 Codex 验收。
- **回滚值已记**：老 `DEPLOY_HOST=34.180.93.185`；Cloudflare A `34.180.93.185`。
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
