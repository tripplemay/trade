---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B105 ✅ done（2026-07-07, 1g+1c, Workflow-build）** inst_buy_net **rank-weighted dollar-neutral 多空**（测 B104 +0.15 IC 扣成本能否转化 edge，解 B103 binary-follow 非正 ↔ B104 IC 正张力：IC 在排名里）。★裁定 **全 PASS 2/2**。⚠️ 前一次"B105 验收"是**幻觉**（声称推 `f4e2b1c`/NO-GO，commit 不存在/无 signoff/status 仍 verifying）→ Evaluator 从零重做。
- **GO（纸面）算术为真且逐位独立复现**（自写平均秩 `np.unique`+自写 Spearman，**不 import 任何 b105 函数**，真实 485 对面板）：GROSS 5d cum **+0.6843 Sharpe1.151 t1.97** / 10d **+1.3322 Sharpe1.612 t2.75**；NET@40bp 5d **+0.4667** / 10d **+1.0334**，30/40/50/80bp 全档净正；1d 负控制 flat→NET 每档负；corr(IC,ret) 0.879/0.825——与 committed `result.json` bit 级一致。
- **★★命门2 拆腿（generator 没做，我补，对 ¥200 最关键）**：dollar-neutral 净收益 **~90–107% 来自 A 股不可行的空头腿**（5d 空 107%/10d 91%, Sharpe1.74），**多头腿绝对≈0 甚至负**（5d −0.0011/月 Sharpe−0.08 / 10d +0.0022/月 Sharpe0.12）。根因=LHB 异动 universe 事件后整体**下漂 −2.70%(5d)/−3.29%(10d) 每月**，空头做空跌最狠的最差名赚钱、多头只是跌得比平均少。散户无法融券做空小盘→纸面 GO 里能落地的多头恰是不赚钱那侧。long-only 绝对≈0；long-only-vs-异动篮子 alpha Sharpe 净~1.0–1.4 但是相对下跌篮子非绝对钱。
- **★对 Tushare ¥200 诚实判断**：信号 **REAL**（24 批唯一没死聪明钱线索，IC~0.15 挺过扩样+扣成本）但**可落地多头 edge 弱**。¥200 能解决幸存者/更长窗(2005+)/50x 样本/干净席位/confirm-kill + 测 long-only 是否有绝对残值；**解决不了 A 股做空限制（市场结构，付费改不了）→ ~90% 纸面利润在结构性关闭的空头腿**。= **well-motivated 但收窄的 confirm/kill，非买已知 edge**；报告护栏（明标 upper bound/非 tradeable/短腿不可行/¥200 decisive）不误导白花亦不误导白省 → **仍待用户知情决策**。命门4 PASS（无前视 4 事件手核 T+1 / 无 p-hacking horizon=B094 固定+成本预声明+无 sweep/挑权重 / 产品码 0 diff research-only / CI 双绿@09387c3 / HEAD≡prod / 21 测 / ruff 净）。signoff `docs/test-reports/B105-inst-net-ranked-longshort-signoff-2026-07-07.md`；独立复算脚本 `docs/test-cases/b105_independent_recompute.py`。
- **B104 ✅**（inst_buy_net 免费 2.1x 席位扩样 HOLDS 真且稳但薄，全 PASS 2/2）。**B103 ✅**（全 LHB first-look INCONCLUSIVE）。**B102–B074 ✅**。活生产 API=`trade.guangai.ai`（非 astock）。
- **接续**：免费探索**已给出 definitive 结论**——inst_buy_net 是真排名信号（IC~0.15 挺过扩样+纸面挺过成本），但**实盘 long-only 落地弱（多头绝对≈0，~90% 纸面利润在不可交易空头腿）**。★战略决策待用户：backlog 剩 A股聪明钱[**付费 ¥200 日频/全史/退市 LHB** = 收窄的 confirm/kill，期望须低] + residual-engine（B100 INCONCLUSIVE）。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。

## 遗留 / soft-watch
- **B105 S1/S2/S3**（非阻断）：S1 报告 "materially weaker" 未量化"多头绝对≈0/空头腿占~90%"（signoff §5 补齐，后续转述 GO 须附此条否则易读成可交易多头 edge）；S2 corr(IC,ret)0.88 是近机械一致性检验非独立盈利证据（承重是 GROSS t-stat）；S3 485 对仅 174（36%）nonzero 有效样本（承袭 B104）。
- **B104 S1/S2/S3**（归档）：报告 "strengthens" 措辞偏乐观 / 未披露 36%-nonzero / 只测 7% 目标扩样。**B103 及更早**：见旧注归档。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True（仅人工解红卡；三重守门）。**残差动量 B100 A/B INCONCLUSIVE，不切入。**
- golden 只进测试 fixture seam。**smart-money 免费信号（游资/机构建仓/insider/全 LHB tag/inst_buy_net ¥）first-look 均 research-only（0 产品码），无一切入生产；免费探索收口——inst_buy_net 真但 long-only 落地弱→¥200 收窄 confirm/kill 待用户。**

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点（承接 §30）。
- **v0.9.55**（f67332e, 2026-07-06）：B080-B098 队列 9 条 learnings 沉淀（全批准清队列）。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。scipy 本机未装，独立复算脚本自写平均秩/Spearman。
