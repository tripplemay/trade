---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B103 ✅ done（2026-07-07, 1g+1c, Workflow-build）** 全 LHB **机构买入** first-look（用户 PRIMARY 信号=日频 LHB 机构席位；复用 B094 缓存 52,337 事件，补 B094 只测游资 + B077 只测 b070 19% 双缺口）→ **INCONCLUSIVE**（粗糙 tag≈NO-GO，精确 ¥ +0.20 IC 薄）。★裁定 **全 PASS 2/2**。独立验收（代 Codex，隔离，最高怀疑度，真 52k 事件面板复算非 fixture）：**报告全部数字 bit 级复现**——覆盖 **23.9%（12,502/52,337）/35 月**；`inst_buy_flag` 平（|t|<0.6）；`inst_count`（有符号家数）N5/N10 **显著负 t=−2.74/−3.49**（机构越买越跌=马甲/派发印证先验）；`inst_buy_net`（精确席位¥）N5 **+0.205 t=2.22 但仅 232 对/26 月/~9 名/月**；follow edge 全非正（N10 −0.76% t=−1.70）。
- **★★命门1（覆盖 vs B077 + Tushare ¥200 含义，本批最关键）PASS**：B103 免费**仍覆盖受限（~24%，非近全）**→ ¥200 全覆盖仍**决定性未测**；精修=covered 1,279 ticker **跨全板**（SH主板/SZ主板/ChiNext/STAR，比 B077 大盘 only 19% 更具代表性），仍漏退市（幸存者）+BJ 全缺。**关键：粗糙「N家机构」tag 这条免费路这次已被否（NO-GO）**→ ¥200 不是重测粗糙 tag，而是**定向 confirm/kill 精确 inst_buy_net 的 +0.20**（免费只凑 232 对薄样本，方向且与粗糙 count 相反）。报告**双向不误导**：不误导白花（明写 +0.20「fragile n≈232 / hypothesis not result」，不承诺 ¥200 找 edge）+ 不误导白省（不宣称 PRIMARY 信号已死，因精确 ¥ 覆盖子集是正的）。**我独立 fragility 压测坐实 +0.20 薄**：26 月仅 15 月为正，逐月 IC ±0.9 剧烈跳（5-11 名/月单股主导）。命门2 PIT 无前视 PASS（bisect_right 严格>T + 3 真实事件手核 + 16 单测）。命门3 及时性/B099 PASS+软观察 S1（及时粗糙 tag 仍 NO-GO=及时单靠免费粗糙 tag 不能救；精确 ¥ 薄正留住 ¥200；但报告未显式接 B099 季度滞后对照）。命门4 PASS（禁扫参 grep 净+0 产品码 diff 空+L1 16 测+Python/Backend CI success@34767a4+Deploy success HEAD≡prod+对抗 2 CONFIRMED 我复现）。3 软观察见下。signoff `docs/test-reports/B103-full-lhb-institutional-first-look-signoff-2026-07-07.md`。
- **★对 Tushare ¥200 决策含义**：免费全 LHB 仍 ~24% 覆盖（比 B077 19% 跨板但非近全）→ **¥200 全覆盖仍决定性未测**；不同的是**粗糙 N家机构路已否（NO-GO）**，¥200 独立价值收窄为**精确席位 ¥ 在全覆盖 + 退市 + 全史上定向 confirm/kill 那条 +0.20 薄正信号**——**既未被证明白花（+0.20 是活假设）也未被证明可省（免费无法否定精确 ¥）**，仍待用户决策。
- **B102–B074 ✅**（免费 smart-money 四角度 NO-GO：游资 B094/机构建仓 B099/insider 大盘 B101/小盘 B102；残差引擎 A/B INCONCLUSIVE B100）。活生产 API=`trade.guangai.ai`（非 astock）。
- **接续**：★战略决策待用户。backlog 剩：A股聪明钱[**付费 ¥200 日频 LHB top_inst / 精确席位¥** 待用户，B103 已把它精化为**定向确认 inst_buy_net +0.20** 的干净测试] + residual-engine（B100 INCONCLUSIVE，采纳待用户）。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。

## 遗留 / soft-watch
- **B103 S1/S2/S3**（非阻断）：报告 §5 关系表未显式接 B099「季度滞后 vs 日频及时」层→不改裁定/数字 / 程序化 judge() 只吃 ic_flag+follow-edge 不吃显著负 count+正 net（标签比正文薄，但正文 foreground 分歧更诚实）/ 复算 json 未落盘（.md 承载全数字，我直接跑 probe 解析 JSON bit 复现）。
- **B102 S1/S2/S3**（归档）：打分月时间聚集 / 「optimistic upper bound」措辞非严格 / 复算 json gitignored。**B101–B081**：见旧注归档。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True（仅人工解红卡；三重守门）。**残差动量 B100 A/B INCONCLUSIVE，不切入。**
- golden 只进测试 fixture seam，不碰生产真数据路径。**smart-money 免费信号（游资/机构建仓/insider/全 LHB 机构 tag）first-look 均 research-only（0 产品码），无一切入生产；免费粗糙路收口，精确席位 ¥ 待 ¥200 定向验。**

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点（承接 §30）；test-automation roadmap P0–P5 全完→backlog 移除。
- **v0.9.55**（f67332e, 2026-07-06）：B080-B098 队列 9 条 learnings 沉淀（全批准清队列）。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
