---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B108 巨潮 parser 自检重构 🔴 fixing（2026-07-20, fix round 1 复验 FAIL）** F001✅ F002✅ → **F003 复验 FAIL**。报告 `docs/test-reports/B108-cninfo-parser-selfcheck-reverify-2026-07-20.md`。
  - **★样本争议已裁定：换新 seed 重抽**（依据：修复代码注释/单测直接点名 300432/002670/002605/002382，grep 可复现 = 照着样本写的；spec H2 自身判据即认定已烧掉）。实测印证 **样本内 26.3% vs 样本外 16.7%，相对高估 57%**。
  - **新 holdout 实测（seed 5590431，120 份，排除 50+76=126 交集 0，PDF 字节已冻结）**：CONFIRMED **20/120=16.7%**（首轮 5.3%）；EXTRACTION_FAILED **20.8%**（首轮 48.7%）；单源 54.2%；冲突 7.5%。
  - **precision 硬门 PASS（字面）**：**20/20=100%**、10ⁿ 错误=0，acceptance(3) 的 ≥20 份首次可执行。**★但 n=20 的 95% 下界仅 86.1%**，断言 ≥99% 需 n≥299（≈1794 份）——**勿读成「已证明 ≥99%」**。
  - **★★仍 FAIL 三条**：(1)**N01 阻断 = 本轮新引入 10ⁿ 错值**——E03 表头带吞掉「单位：万元/千元」行、header_line 抬到声明之上，E04 的 resolve_unit 只向上扫 → 本表单位不可达；601186/601187 **带值返回缩小 10³**；已**对拍旧实现 8c85f03 证明三例均本轮引入**。(2) 冲突误报 40%→**66.7%**（主因换成 S2 命中「分季度主要财务指标」取单季度格，E07 表格优先规则对它无效）。(3) **N02 违 spec §3.1**——S1 实际取自**所有者权益变动表**非合并利润表，30 份走此路径，≥3 份口径不同（000835 差 0.401% 返错值）。
  - **★N03：年报 FY 0/34 CONFIRMED**（首轮 0/18，**未泛化**）。根因行级定位：锚点词表 `_HEADER_TOKENS` 不含裸年份，而年报表头是「2018 年/2017 年/本年比上年增减」→ 列模型永远建不起。**H1 半年报 53.6%（20 份 CONFIRMED 里 15 份是半年报）、Q1 11.1%、Q3 6.5%、FY 0% — parser 实质只在半年报上工作。**
  - **E01-E11**：E01/E05/E06/E07/E09/E10/E11 **七条干净 FIXED**；E02 FIXED 但 tail_appended 误伤多段折行标签；E03 PARTIALLY（失败率减半、盲区消除，但裸年份未解且是 N01 成因）；**E04 REGRESSED**（002670 已修正但反方向打开）。首轮 11 条点名反例**全部解决**。
  - **★采购结论：仍不够用，仍不判「免费源天花板已到」**——缺陷是实现问题非数据源问题，三条主缺陷都有结构化修法。统计差距**从 5681 份降到 1794 份 / 约 5.5 小时机时**。**★新增判断：自建 parser 真实成本 = 每轮修复都需一次独立 holdout 验收**（N01 是 E03×E04 跨模块相互作用，单看 diff 发现不了），验收成本与开发成本同量级，与 Tushare ¥500 相比经济性优势没想象中大。Tushare 仍从未实测。
- **B107 生产迁移 ✅ done（手工置 done，F003=waived 无 signoff）**。活生产 `https://trade.guangai.ai` 在 deploysvr（`194.238.26.173`），**version 已对齐 HEAD**，db-ok，三单元 active，定时任务真跑通，F001 本地备份工作中。老机 `34.180.93.185` 全栈**冻结作回滚点**。
- **B106–B074 ✅**。

## 接续 / 待决策
- **★F003 fix round 2（Generator）**：修 **N01（阻断，10³ 错值；建议 resolve_unit 从表头带**末行**起扫，或表头带排除「单位：」行）→ N03（裸年份加进 `_HEADER_TOKENS` 锚点，与 `select_target_column` 兜底对齐）→ N02（S1 限定合并利润表，或「加：本期…」降为独立第四来源）→ 冲突误报（排除分季度主要财务指标表）→ N04/N05**。★**复评必须再换新 seed**，排除清单扩到 50+76+120=**246 份**（`docs/test-reports/B108-holdout-r2/exclude-merged.json` 是可直接扩充的格式）——本轮 120 份自复验报告发布起即已烧掉。
- **三处偏离首轮已裁定**：S3 区间方向 ACCEPT / manifest 拆 provenance ACCEPT / 无 pdf_sha256 ACCEPT 且 E11 已补（`build_pdf_freeze` 本轮实跑 120/0 缺失）。
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
