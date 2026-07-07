---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B104 ✅ done（2026-07-07, 1g+1c, Workflow-build）** inst_buy_net(精确机构净买¥)免费 **2.1x 席位扩样**压力测 B103 的 +0.20 IC → **HOLDS（真且稳，但薄）**。★裁定 **全 PASS 2/2**。独立验收（代 Codex，隔离，最高怀疑度，**自写 Spearman 不 import generator**）：扩样 N5 **+0.148 t2.925** / N10 **+0.1615 t2.838** / N1 −0.0105（485 对/35 月）vs 基线 N5 +0.2047 t2.222（232 对/26 月）——**bit 级复现 committed JSON**。
- **★★命门1（反转之谜 / 防 p-hacking，本批最高怀疑点）PASS = 无 p-hacking**：所谓"早期 3.6x 扩样塌成 0.03"是**幻影**——它是 planner 早前对用户的**预测**（"+0.20 很可能全覆盖后塌成噪音"），被回顾叙述成已测得的塌陷；**磁盘 + 全 transcript 均无此计算**。真实只两次 seed-104（+100 新 364 对 t2.26 → +200 新 485 对 t2.92）**都 HOLD 单调不塌**。停 200 是 **fetch 限流非挑显著点**（轨迹 +0/+50/+100/+150/+200 → t 2.22/2.92/2.26/2.86/2.92 **每点 t>2.2**）；无挑种子（全 seed-104；seed-102 属 B102 无关）/无扫描码（grep 无 argmax/sweep/for-seed）/apples-to-apples（同 b103.run，唯一差 seats 行数）。
- **★★命门2 独立复算+稳健 PASS（真且稳但薄）**：jackknife-by-month 删任一月 N5 t∈[2.67,3.43] 无单月扛全场；但 **485 对仅 174（36%）真有机构买入（~5 名/月）**，逐月 IC −0.48…+0.73 剧跳/23 月正，点 IC 降 28%（t 升纯因月数 26→35 缩小标准误），"2.09x 翻倍"多为 0 值补薄月解锁存量（真机构观测 221→297，+34%）。命门3 PIT 无前视 PASS（bisect_right 严格>T + 3 新事件手核 T+1 + 17 单测）。命门4 PASS（0 产品码 diff 空/17 测/ruff 净/Python+Backend CI success@bc0805d/Deploy success→HEAD≡prod）。3 软观察见下。signoff `docs/test-reports/B104-inst-buy-net-stress-test-signoff-2026-07-07.md`。
- **★对 Tushare ¥200 决策含义（本批直接影响花钱）**：HOLDS **站得住**（数字真 + 非 p-hacking + jackknife/checkpoint 全稳）但**站在薄冰**（~5 名机构/月、只测 7% 目标扩样、点 IC 已降 28%、仍 2022-2024+幸存者限、很可能全覆盖后塌）。这是**24 批唯一没死、且挺过一次（虽部分）真实压力测的聪明钱信号**=最好免费线索 → ¥200 是对它的**诚实决定性 confirm/kill 测（非买已知 edge，期望须低）**；报告护栏不误导白花（明标非 tradeable/非 settled）亦不误导白省 → **仍待用户知情决策**。
- **B103 ✅**（全 LHB 机构 first-look INCONCLUSIVE：粗糙 tag NO-GO 但精确 ¥ +0.20 IC 薄 232 对；covered 23.9% 跨全板）。**B102–B074 ✅**（免费 smart-money 四角度 NO-GO；残差引擎 A/B INCONCLUSIVE B100）。活生产 API=`trade.guangai.ai`（非 astock）。
- **接续**：**B105 已开批 building（planner e9e3a19）** = inst_buy_net ranked 多空（测 IC 是否扣成本转化 edge，解 B104 IC~0.15 vs binary-follow 非正张力，复用 B104 缓存无前视）。★战略决策待用户：backlog 剩 A股聪明钱[**付费 ¥200 日频 LHB / 精确席位¥**，B104 已精化为**对唯一没死的 +0.20 信号做诚实 confirm/kill**，期望须低] + residual-engine（B100 INCONCLUSIVE 待用户）。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。

## 遗留 / soft-watch
- **B104 S1/S2/S3**（非阻断）：报告 "HOLDS: strengthens" 措辞偏乐观（t 升实为月数增之机械结果，点 IC 反降 28%）/ 未显式披露 36%-nonzero 有效薄样本（承袭 B103 已接受方法）/ 只测 200/2704 目标扩样（7%），fetcher resumable 可续跑更强测。
- **B103 S1/S2/S3**（归档）：报告未显式接 B099 季度滞后对照 / judge() 只吃 flag+edge / 复算 json 未落盘。**B102–B081**：见旧注归档。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True（仅人工解红卡；三重守门）。**残差动量 B100 A/B INCONCLUSIVE，不切入。**
- golden 只进测试 fixture seam。**smart-money 免费信号（游资/机构建仓/insider/全 LHB tag）first-look 均 research-only（0 产品码），无一切入生产；免费粗糙路收口，精确席位 ¥ inst_buy_net 免费 2.1x 扩样 HOLDS 但薄/部分→¥200 定向确认待用户。**

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点（承接 §30）。
- **v0.9.55**（f67332e, 2026-07-06）：B080-B098 队列 9 条 learnings 沉淀（全批准清队列）。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
