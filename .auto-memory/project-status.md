---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B107 生产迁移 ✅ done（2026-07-20 用户手工置 done）** trade 已从退役中 GCP VM（`34.180.93.185`）迁至 **deploysvr（`194.238.26.173`）**，原生 systemd 栈照搬，域名 `trade.guangai.ai` 不变。F001✅ F002✅ **F003=waived（Codex 独立验收未跑，无 signoff——git 里不要当通过读）**。
- **★活生产健康（2026-07-20 实测）**：公网 health `status:ok`/`db_connectivity:ok`/uptime ~7d/`version=f9c56be`；backend+frontend+backtest-worker 三单元 active；定时任务真跑通（cn_attack×2 saved=25、cn_dividend_lowvol saved=1、canonical-backtest Finished）；F001 本地备份工作中（最近 6.9h 前 10MB）。老机 `34.180.93.185` 全栈**冻结作回滚点**。
- **B106/B105/B104/B103/B102–B074 ✅**。

## 接续 / 待决策
- **★下一方向（用户已选定）**：修**巨潮 cninfo PDF parser** — A股纯 E/P 数据地基的前置。采购决策已定：**先不花钱**，先验证「免费源 + 自建 parser」天花板。
  - 根因已诊断（`scripts/test/ashare_as_filed_data_pilot.py`）：`extract_parent_profit` 取 `numbers[0]` 且**无任何自检** → ①附注列误认（`600436` 抽出 1 元）②`_unit_scale` 取 `matches[-1]` 跨表错绑（`601113` 差 10⁴）③`selected_index` 硬编码列号 ④单行匹配「归属于母公」旧模板断行失配。**4 类同源。**
  - 拟修法：**文档内多源交叉验证**（合并利润表 vs 主要会计数据 vs EPS×股本），不依赖外部对照物，不一致返 `NEEDS_REVIEW` 而非猜测值。
  - ★纪律：原 50 份已被 agent 看过=样本内，**重评必须新抽样本**；`600787`(0.87%)/`601992`(29.28%) 需人工翻 PDF 裁定。
- **★遗留1（非迁移缺陷，未修）**：`workbench-advisor.service` failed = `aigc.guangai.ai` **402**，但 AIGC 余额 **$22.34 非零**且同日 07:52 其他 client 正常 → 是 **trade 这把 key/project 的配额或权限问题，修在 aigc 侧**。
- **★遗留2**：**Production(`f9c56be`) ≢ HEAD(`c69da4c`)**，落后 4 个 docs/chore commit（paths-ignore 不触发 CI→不触发链式），需手动 dispatch Deploy 才对齐（§12.7 兜底）。
- **★P6 🔴 老 VM 退役**仍未做（老机冻结中）。回滚值已记：老 `DEPLOY_HOST=34.180.93.185`；Cloudflare A 旧值 record `a910644a…`。
- **★关键坑（本机专属）**：本机 Mac 在 Clash fake-ip 代理后连老机会被路由到**错的机器**（host key mHOXFC≠真机 a6Hui）→ 一律 `ssh deploysvr` 再跳。
- backlog 剩：A股聪明钱 ¥200 + residual-engine（B100 INCONCLUSIVE）+ B106-S3。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。
- **★负责人纪律**：验收结论 git 核实才采信（B104/B105 幻觉教训）。

## 永久硬边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO）**。红利低波留 A股本土组合才兑现负相关分散。
- cn_attack 研究态/OOS 红卡不可配资。冻结再验证 pipeline **永不** validated→True。golden 只进测试 fixture seam。**smart-money 免费信号 first-look 均 research-only（0 产品码）无一切入生产。**
- **A股 PIT 数据禁令**（`docs/audits/ashare-pure-ep-data-foundation-implementation-handoff-2026-07-13.md` §14）：禁 `(ticker,quarter)` latest-wins / 禁法定截止日代公告日 / 禁流通市值代总市值 / 禁当前股本×历史价 / 禁只拉 `list_status=L`。当前裁定 `DATA_NO_GO`。

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点。
- **v0.9.55**（f67332e, 2026-07-06）：B080-B098 队列 9 条 learnings 沉淀。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（改 trade/ 后须重装）。scipy 本机未装，独立复算自写 Pearson/秩相关。
