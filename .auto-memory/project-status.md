---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B101 ✅ done（2026-07-06, 1g+1c, Workflow-build）** smart-money 大股东/高管增持 first-look（免费 `ak.stock_ggcg_em '股东增持'`，33400 事件/3233 股；∩B070 流动子集=998 股 30.9%/12249 可交易事件）→ **流动大盘 NO-GO（信号真空）**。★裁定 **全 PASS 2/2**。独立验收（代 Codex, 隔离, 最高怀疑度, 真 998 股面板复算非 fixture）：命门1 PIT 无前视=按公告月分 cohort 入场=月 M+1 首交易日（自写审计 83/83 cohort 0 违规+3 手核+原始事件 announce>=txn min_lag=0，重尾滞后 median3/mean60/p90183）; ★命门2 外推边界=报告**结论限流动大盘子集、小盘 sleeve 未测 caveat 完整保留、未过度外推为增持信号全体无效**; 命门3 我构造 look-ahead 对照（交易月作弊版 h20 IC=-0.018/t=-0.83 亦≈0）坐实 NO-GO 非滞后 artifact+归因正确（与 B099 作弊 t>2 相反）; 命门4 自写独立 IC 实现 h20 逐位吻合(-0.0358/t=-1.58)+bit 可复现+GO 门槛 6 组无一达标（非单调翻号、全|t|<2）; 命门5 覆盖诚实(30.9% liquid tilt 明标)+无扫参; 命门6 零回归(0 产品码)+L1 14 测+CI(python-checks/backend@0472146 success)+HEAD≡prod。signoff docs/test-reports/B101-insider-buying-first-look-signoff-2026-07-06.md。
- **★含义（免费 smart-money 四支已测尽，流动大盘均无 edge）**：① 机构席位覆盖限（B077，80.8% 小盘未覆盖）；② 游资（B094 NO-GO）；③ 机构建仓季度（B099 NO-GO，滞后元凶）；④ **大股东/高管增持（B101 NO-GO，流动大盘信号真空）**。→ 未测=**小盘 sleeve**（需扩数据，增持信号 plausibly 集中处）+ 付费 **¥200/日 top_inst**（用户真实目标的决定性测试，仍待用户决策）。
- **B100 ✅ done** 残差动量完整引擎 A/B（research-only wrapper）→ **INCONCLUSIVE**（残差边际 trailing 裸动量→不切 flagship；与 B085 t=1.98 borderline 一致）。全 PASS 2/2。0 产品码。采纳残差=用户决策。
- **B099–B074 ✅**（免费信号三支 NO-GO / 生产 canary / judge-lint / etc）。活生产 API=`trade.guangai.ai`（非 astock）。
- **接续**：★战略决策待用户（免费策略研究四支无强 edge）。backlog 剩：A股聪明钱[**付费 ¥200 日频 top_inst** 待用户] + test-automation **P5-F2**（独立评审流程, evaluator 域, 注: c5694f7 已固化 evaluator.md §33）+ residual-engine（B100 已测 INCONCLUSIVE, 采纳待用户）。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。

## 遗留 / soft-watch
- **B101 S1/S2/S3**（非阻断）：小盘 sleeve 真未测门（需扩小盘 qfq 才能给增持信号全体定论）/ look-ahead 对照为验收侧新增证据未入交付脚本（与 B099 命门3 互补）/ 复算 json 本机 gitignored（报告 md 承载全数字，已 bit 复现）。
- **B100 S1/S2/S3**（非阻断）：残差臂 scored-pool 中位少 ~1.5%(252d β 窗内生) / Δ−1.33pp 落 7 年路径噪声带 / 复算 json 本机 gitignored。
- **B098–B093**（归档）：§5 门禁 echo 自报叙事 / synthetic→rollback 待产品部署 exercise / judge-lint advisory 无 runtime-gate 消费者 / B094 events 未去重（dedup 后仍 NO-GO）/ B093 proxy 结构天花板。**B089–B081**：见旧注。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True（仅人工解红卡；三重守门）。**残差动量 B100 A/B INCONCLUSIVE，不切入。**
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。**smart-money 免费信号四支 first-look 均 research-only（0 产品码），无一切入生产。**

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点（承接 §30）；test-automation roadmap P0–P5 全完→backlog 移除。
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
