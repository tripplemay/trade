---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B080 🔄 verifying（2026-07-03）**(策略生命周期监控 L0+L1) = generator 全 4 特性 F001-F004 **DONE + CI 绿 + 部署**，交 Codex **F005 独立 L2 验收**。F001 trial_registry 表+27 回填+oos 红卡 DB 化+`/monitoring/trials`；F002 监控指标(rolling-IC 持仓保真/tracking/exposure/turnover)+周 timer+`/monitoring/metrics`+signal_scores 前向积累；F003 冻结再验证 pipeline(kernel 移植 b070 参数冻结+CPCV-lite K=4+三落地 no-validated→True 三重守门+baostock data-append+reverify_job 异步+触发 API+季度 timer+worker 接入)；F004 paper 三口径(① benchmark cn_attack SPY→CSI300 读 cn_csi300.csv/master 保 SPY byte-identical / ② base_currency CNY migration 0032/master 保 USD / ③ 首日 annotation-only 不重算)+前端 /monitoring 页(健康卡+trial DataTable+reverify 触发钮+双语 e2e no-execution 守门)。**F005=Codex L2 真机**：VM timer 装载/指标真数据抽查/reverify 手动触发(或标注长任务未跑)/红卡零回归/trial 回填抽查/paper 口径实测/截图/no-execution。migration head 0032。
- **B079 ✅ done（2026-07-03）**(标的名称显示,名主码次)= F001-F003 generator+F004 独立 Evaluator 真机 PASS。A股 中文名待日刷落库(诚实边界,非 FAIL)。signoff docs/test-reports/B079-...-2026-07-03.md。
- **B078 ✅ done（2026-06-26）** A股 data-refresh 卡死修复。**B077 NOT-GO（2026-06-25）** 聪明钱摸底。B076/B075/B074 done。
- **接续**：B080 done 后 backlog 20 项(B081 引擎修真 P0.5 spec 草稿已备 / B048 安全风控 / B0XX-ashare 数据源等)。

## 遗留 / soft-watch
- **B080 F004 坑**：api.ts 加带默认值字段仍 TS-required → 前端 fixture tsc 红；api.ts 与 fixture 须**同 commit**(本批 dd9f703 红→46ba83b 绿,见 proposed-learnings)。
- **★聪明钱方向**：backlog `B0XX-ashare-smart-money-following`，结论存docs/research/。
- **B070 follow-on**：2因子去偏baostock；港股P3（backlog B055）。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 4 版）
- **v0.9.54**（B078）：generator.md §38 宽集刷超时含 bulk discovery / §39 paper round-trip 成本 / §40 静默冻结守门 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。
- **v0.9.52**（B076）：§35 baostock 补退市名市值 + 双 cut / planner.md 策略改动双门禁 verdict。
- **v0.9.51**（B075）：environment VM /tmp PYTHONPATH / §33 探针复用真 loader / §34 宽集 partial-failure exit-code。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
