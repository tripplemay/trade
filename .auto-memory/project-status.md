---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B108 巨潮 parser 自检重构 🔍 verifying（2026-07-20, 2g+1c）** F001✅ F002✅ → **F003 交 Codex**。spec `docs/specs/B108-cninfo-parser-selfcheck-spec.md`。
  - **起因**：复核 as-filed pilot 的 65.789% `NO_GO`，发现 13 份失败里 **≥10 份是本仓 parser 自身 bug**（附注列误认/单位跨表错绑/硬编码列位/旧模板断行，四类同源＝抽取器无任何自检），且对照物是 Eastmoney 当前快照**非人工真值**。
  - **采购决策：先不花钱**，先验证「免费源+自建 parser」天花板，再决定是否买 Tushare（¥500/5000 积分）。★调研确认 **Tushare 在本仓从未实测**（零集成/无 token，实跑是 akshare+baostock），报告里 13 个 P1 接口全是二手文档调研。
  - **F001 ✅**：`scripts/research/ashare_ep/` 多源交叉验证抽取器（S1 合并利润表 / S2 主要会计数据 / S3 数量级哨兵），冲突返 `None` 而非猜测值 + 7 个 failure code。★差分证据：旧 parser 在附注列 fixture 返回 **35.0**、在三季报四列 fixture 返回**上期金额** 198000000.00；新 parser 分别 252300000.00 / CONFIRMED（双源一致）。
  - **F002 ✅**：seed 化分层抽样 CLI。★实测同 seed 两跑 sha256 `47aede26…21d6` 字节相同；`--exclude-manifest` 从 pilot 报告解析出**恰好 50 个** ID。
  - 40 新单测，全量 **1534 passed 零回归**，ruff 净。
- **B107 生产迁移 ✅ done（手工置 done，F003=waived 无 signoff）**。活生产 `https://trade.guangai.ai` 在 deploysvr（`194.238.26.173`），**version 已对齐 HEAD**，db-ok，三单元 active，定时任务真跑通，F001 本地备份工作中。老机 `34.180.93.185` 全栈**冻结作回滚点**。
- **B106–B074 ✅**。

## 接续 / 待决策
- **★F003（Codex）**：自选 seed → `sample_cli --exclude-manifest docs/test-reports/ashare-as-filed-data-pilot-2026-07-12.json` 抽 ≥60 份 holdout → manifest+hash **先冻结再评测** → 硬门 **confirmed precision ≥99% 且 CONFIRMED 中 10ⁿ 错误=0**（coverage 只报告不设门）→ 冲突有效性检查（真抓到 bug vs 误报）→ signoff 给出「免费源+自建 parser 够不够用」结论。
- **★三处偏离待 Codex 判**：(1) F001 S3 用 `|利润|/|EPS|→推算股本∈[1e6,1e12]` 取代 spec §3.1 的「EPS×期末股本」（季报常无期末股本）；(2) F002 manifest 不含生成时间（与逐字节复现硬冲突，拆 provenance 旁文件）；(3) F002 manifest 不含 `pdf_sha256`（抽样阶段不可得）。
- **★F001 诚实限制**：bug ④（旧模板断行）单测**非差分回归**——旧 parser 同样能过该 fixture，真实失败样本（600843/600639/600688）无原始 PDF 不可复现，**本批次内无法自证**，须 F003 在 holdout 上检验。
- **★用户人工事项**：`600787`(0.87%) / `601992`(29.28%) 需翻原始 PDF 裁定属真实修订、口径差异还是 parser 错。
- **★遗留（非本批）**：`workbench-advisor.service` failed = `aigc.guangai.ai` **402**，但 AIGC 余额 **$22.34 非零**、同日其他 client 正常 → **trade 这把 key/project 的配额或权限问题，修在 aigc 侧**。**P6 🔴 老 VM 退役**未做。
- **★关键坑（本机专属）**：本机 Mac 在 Clash fake-ip 代理后连老机会被路由到**错的机器** → 一律 `ssh deploysvr` 再跳。
- backlog 剩：A股聪明钱 ¥200 + residual-engine（B100 INCONCLUSIVE）+ B106-S3。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。
- **★负责人纪律**：验收结论 git 核实才采信（B104/B105 幻觉教训）。

## 永久硬边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO）**。红利低波留 A股本土组合才兑现负相关分散。
- cn_attack 研究态/OOS 红卡不可配资。冻结再验证 pipeline **永不** validated→True。golden 只进测试 fixture seam。**smart-money 免费信号 first-look 均 research-only（0 产品码）无一切入生产。**
- **A股 PIT 数据禁令**（`docs/audits/ashare-pure-ep-data-foundation-implementation-handoff-2026-07-13.md` §14）：禁 `(ticker,quarter)` latest-wins / 禁法定截止日代公告日 / 禁流通市值代总市值 / 禁当前股本×历史价 / 禁只拉 `list_status=L`。当前裁定 `DATA_NO_GO`，**B108 不改变该裁定**。

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点。
- **v0.9.55**（f67332e, 2026-07-06）：B080-B098 队列 9 条 learnings 沉淀。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（改 trade/ 后须重装）。scipy 本机未装，独立复算自写 Pearson/秩相关。
