---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B080 🔧 fixing（2026-07-04）**(策略生命周期监控 L0+L1) = F005 独立 L2 真机验收→**FIXING(1 BLOCKING)**。**BLOCKING**: 生产 trial_registry=0 行(spec 要求>=15/清单>=27) — 回填只在手动 workbench-bootstrap CLI(迁移 0029 只建表), 不在自动部署链(deploy.sh 只 alembic), 部署后未在生产跑, 无调度器自愈; 同源缺口静默影响 B079(curated symbol_name=0)。代码本身正确(HISTORICAL_TRIALS==27)。修复: 生产落库 27 条+治本接部署链或改 data-migration→复验 trial_registry>=27。**其余全 PASS(VM 只读实测)**: HEAD≡prod(46ba83b)/monitoring+reverify 两 timer 装载带显式 TimeoutStartSec/红卡 DB 化零回归(oos card 2 行+快照 caveat 逐字一致)/paper 三口径(cn_attack CNY+master USD 0032, benchmark 映射, 首日 annotation)/signal_scores 前向积累生产实测/no-validated→True 三重守门/no-execution/L1 223 passed。monitoring_metric=0(周 job 首跑 07-06 自愈, 计算路径 L1 已证)。长任务 reverify 未在生产触发(故意)。报告 docs/test-reports/B080-...-verifying-r1-2026-07-04.md。
- **B079 ✅ done（2026-07-03）**(标的名称显示,名主码次)= F001-F004 PASS。**soft-watch 关闭(2026-07-04)**: 07-04 日刷落库 symbol_name 5203 行(akshare_spot), cn_attack 快照 25/26 解析中文名。signoff docs/test-reports/B079-...-2026-07-03.md。
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
