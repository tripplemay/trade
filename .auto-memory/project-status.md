---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B091 ✅ done（2026-07-05, round1 一轮闭环）** 修 above_200d_ma 多日历 MA bug(B090 真根因, 1g+1c, Workflow-build)。修=新 `_latest_ma_own_calendar`(col.dropna()前置 rolling)各票自身日历算 MA + `above_200d_ma` 用 wide.apply 逐列; close/fillna(False)语义+trend_pass 接口不变(factors.py +23/−1)。独立验收(代 Codex,隔离): ★零回归命门四重坐实(结构性生产宇宙 MCHI/FXI/KWEB/ASHR 单 NYSE 日历 dropna no-op + 真 proxy 16 季末 bit 级 0mismatch + 200 fuzz 帧 0mismatch + VM prod 跑修复 commit b35a638); ★修复有效—真数据 24 季末 OLD above 恒 0→NEW 5-30, regional_risk_off 24/24 恒 True→9/24 翻 False(real sleeve 0%→~37%参与)+0700.HK OLD False→NEW True; 单测有牙(变异回退→(a)红); 2 对抗验证 un-refuted(journal wf_2a2ea377-422); 门禁全绿+CI 三绿(b35a638 自动链式)+HEAD 产品码≡部署≡prod。signoff docs/test-reports/B091-above-200d-ma-fix-signoff-2026-07-05.md。
- **B090 ✅ done** hk_china 真数据重测(纯研究/负结论批, 无生产面)。warmup 假设证伪(NO/WITH 均 real 25/25 全防守)+发现真根因=above_200d_ma calendar bug(200-row 窗×3 日历 union→MA 恒 NaN)→B091 已修。signoff B090-...-2026-07-05。
- **B089/B088 ✅** VIX tail-overlay / smoothed-feedback vol-targeting(纯研究基建, carry/turnover 诚实焊死)。**B087 ✅** bootstrap-seed deploy-chain 治本。**B086–B074 done**(B077 NOT-GO)。
- **接续**：★下阶段 = backlog **决策级 real-vs-proxy 重跑**(B091 已解锁 real sleeve 真参与; 须携 O1 close-NaN + B090 O2 三 caveat)。余 4 项(A股聪明钱[¥200 Tushare 待用户]/test-automation P3-P5/B055 US careful/residual-engine 触冻结待用户)。★战略决策待用户(P0-P2 无强 edge)。34 learnings 待用户确认。

## 遗留 / soft-watch
- **B091 O1**：残留 `close = wide.iloc[-1]` union 最后行 NaN(修复只改 MA 分母, close 分子与修前同→某票最后 union 日未交易则 close=NaN→above_MA=False; 真数据仅 2/24 季触发节假日错配; 生产 proxy 单日历永不触发; 先存非回归非 F001 范围; 须 follow-up 重跑处理)。**B091 O2**：决策级重跑无离散 backlog 条目(仅记于 B090 signoff O2+B091 报告, 建议 Planner 补登)。
- **B090 O2**：可跑窗仅 25 季(2020-06…2026-06)SGOV floor 住+今日流动名单幸存者偏差→决策级 GO/NO-GO 须更长无偏窗+matched top_n 再跑。**B090 O1**（研究脚本未纳 mypy CI）非真缺陷。**B089/B088**：carry/turnover 措辞略强+窗口 caveat。**B087/B086/B081**：见旧注。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
