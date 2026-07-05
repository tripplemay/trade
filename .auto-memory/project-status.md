---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B092 ✅ done（2026-07-05, first-look, round1 一轮闭环）** B055 US 进攻选股 first-look(research-only 低承诺, 1g+1c, Workflow-build)。~100 S&P100(akshare qfq 价 + SEC EDGAR PIT 财报 94/100)动量+质量 top-15 月度 vs 同宇宙 EW/SPY, walk-forward 样本内/外。★裁定 **INCONCLUSIVE**: 策略 full 26.53%/1.36 胜 SPY 但仅靠等权 tilt(EW 亦胜 SPY); 对正确基线(同宇宙 EW)样本内胜(1.30>0.97)**OOS 反转**(策略 Sharpe 1.45 < EW 1.54)=edge-decay/过拟合→不推荐建全 P1(合 survivorship 偏+单牛市窗+A股姊妹 B070 OOS-negative)。数据发现: akshare 免费 US qfq 2017 前腐败(spike remover+2017 floor 非调参)。独立验收(代 Codex,隔离): ★数字独立重跑 9 指标格 bit 级复现; ★2017 floor 独立坐实真数据边界(pre-2017 1018 不可能移动 vs 2017+ 19, UNH +2845% 坐实 +2800%); ★裁定一致(OOS 风险调整 edge 负→GO 未达→INCONCLUSIVE 纪律); ★幸存者偏方向性正确(美化→无偏更悲观→INCONCLUSIVE 更可信); 先验无扫参+新构≠生产 us_quality_momentum 5 因子; 2 对抗验证 un-refuted(wf_0478a172); research-only 零回归(trade/+workbench/ diff 空)+ruff+18 单测+CI 三绿(b285566)+HEAD≡prod。signoff docs/test-reports/B092-us-attack-first-look-signoff-2026-07-05.md。
- **B091 ✅ done** 修 above_200d_ma 多日历 MA bug(B090 真根因, `_latest_ma_own_calendar` 各票自身日历 dropna 前置 rolling)。独立验收零回归四重坐实(结构性+真 proxy 16 季末 bit 级+200 fuzz+VM b35a638)+修复有效(regional_risk_off 9/24 翻 False)+2 对抗验证 un-refuted。signoff B091-...-2026-07-05。
- **B090 ✅** hk_china 真数据重测(纯研究/负结论)。warmup 证伪+发现 above_200d_ma calendar bug→B091 已修。**B089/B088 ✅** VIX tail-overlay / vol-targeting(研究基建)。**B087 ✅** deploy-chain 治本。**B086–B074 done**(B077 NOT-GO)。
- **接续**：★战略决策待用户(P0-P2 无强 edge; B092 first-look 亦无样本外 edge)。backlog: **决策级 real-vs-proxy 重跑**(B091 解锁; 携 B091 O1 close-NaN + B090 O2 三 caveat) + A股聪明钱[¥200 Tushare 待用户] + test-automation P3-P5 + residual-engine(触冻结待用户)。34 learnings 待用户确认。

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
