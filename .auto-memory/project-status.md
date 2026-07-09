---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B106 ✅ done（2026-07-09, 2g+1c, 组合层落地阶段 A）** 红利低波防守腿并入 Master 组杠铃 + 权重方案参数化（fixed/risk_parity/hrp/vol_target），5 方案回测对照。★裁定 **NO-GO 保持现状**（default 4-sleeve fixed）。★Evaluator 独立验收 **全 PASS 3/3**。
- **verdict 独立复现为真**（numpy 自写指标数学不调 runner；runner 重跑 JSON 逐字节复现）：对齐窗口 2015-09~2026-04（116m）Sharpe ①1.222 基线 ②1.141 ③1.234 ④1.168 ⑤1.092，最优 ③ risk_parity ΔSharpe 仅 **+0.0117（<0.15 门槛）**且拖 CAGR −2.5pp，无方案过 ΔSharpe≥0.15∧ΔMaxDD≥3pp 双门。
- **★核心机理**：红利低波 vs 进攻腿相关性 USD +0.20~+0.48 / CNY 原生 +0.11~+0.41（**弱正非负**）——spec 的负相关是 vs A股动量（本组持美股/全球动量不迁移）；FX 换算把防守腿波动抬 15.8% / MaxDD −31.8%（CNY-native Sharpe 0.480 → USD-converted 0.365）。跨市场+跨币种双错配，分散前提不成立，加防守腿纯稀释高 Sharpe 进攻腿。
- **★byte-identical 零回归独立证实（最强形式）**：前 B106 源码 f7adc15 默认 Master parameter_hash = 守门单测金值 726f9ce6… = HEAD 默认 hash 三者逐位相等；barbell/weight_scheme 纯 opt-in 研究未接生产（precompute/services 仍用 default_master_portfolio_parameters）。signoff `docs/test-reports/B106-portfolio-uplift-signoff-2026-07-09.md`；独立复算 `docs/test-cases/b106_independent_recompute.py`。HEAD≡prod：prod=c7acc30 含全部产品码，diff 仅 progress.json。
- **B105 ✅**（inst_buy_net rank-weighted 多空：信号 REAL/IC~0.15 但可落地 long-only edge 弱，~90% 纸面利润在 A股不可做空的短腿）。**B104/B103/B102–B074 ✅**。活生产 API=`trade.guangai.ai`。

## 接续 / 待决策
- **★阶段 B（B106 后启动）**：新配置 paper 前向验证（≥12 月统计门槛）——但 B106 裁定 NO-GO 保持 default，阶段 B 焦点转为下述隔离测试。
- **★S3 建议下批补测**：**「4-sleeve risk_parity（无防守腿）」隔离风险加权本身效应**——③ 的 Sharpe 微增+波动大降提示对现有 4 条 USD 腿做 risk_parity/HRP（尤其压 hk_china 17.65% 波动权重）可能才是真杠杆；替换拖累的 hk_china（Sharpe 0.358/MaxDD −35.3%）比加防守腿更直接。
- backlog 剩：A股聪明钱付费 ¥200（收窄 confirm/kill，期望须低）+ residual-engine（B100 INCONCLUSIVE）。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。
- **★负责人纪律**：验收结论 git 核实才采信（B104/B105 幻觉消息教训）——B106 signoff 真落盘+status 真 done+commit 真推。

## 永久硬边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO）**。红利低波留 A股本土组合才兑现负相关分散（跨进 USD 组是放错市场）。
- cn_attack 研究态/OOS 红卡不可配资。冻结再验证 pipeline **永不** validated→True。golden 只进测试 fixture seam。**smart-money 免费信号 first-look 均 research-only（0 产品码）无一切入生产。**

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点。
- **v0.9.55**（f67332e, 2026-07-06）：B080-B098 队列 9 条 learnings 沉淀。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（改 trade/ 后须重装）。scipy 本机未装，独立复算自写 Pearson/秩相关。
