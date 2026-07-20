---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B109 Tushare PIT 数据层 v0 🔨 building（2026-07-20, 2g+1c）** spec `docs/specs/B109-tushare-pit-foundation-spec.md`。F001 追加 vintage 探针 → F002 PIT 数据层（`f_ann_date` as-of resolver + `daily_basic` 分母 + B108 框架转巨潮对拍审计器）→ F003 Codex 对拍验收。
- **★★三问探针实测（¥500 + 15 分钟；`docs/audits/tushare-three-question-probe-2026-07-20.md`）——本仓第一次实测 Tushare：**
  - **归母净利润真实修订率 = 0.712%**（7 个年报期 / 38,207 股票-期 / 272 个被改）。★上游 handoff 报告用「90.83% 记录在 120 天后仍更新／中位 365 天」论证的**重装三时钟 bitemporal 底座，必要性未被实测支持**——那衡量的是记录被 touch 时间，不是数值被改比例。**但修订稀有 ≠ 可忽略：61% 幅度 >1%、22% >10%、2018 年 p90 达 101.79%** → 需「记录已知修订并能重放」，不需整套版本链。
  - **as-of 只需两个字段**：取 `f_ann_date <= 形成日` 中最大的一条。`update_flag=0` 保首次披露值、`=1` 的 `f_ann_date` 标修正可知日（滞后中位 372 天，70/87 为此干净形态）。★**未决**：`flag=0` 保留率随期间波动 **10.5%–95.4%**（2019/2020 保留 95%/91% 却近零修订 → 低修订率是**真的**；2023 仅保 10.5% → 该期是**下界**）。
  - **`total_mv` 身份校验 100.000% 在 0.5% 内、中位误差 0.00000%**（2015/2020/2023 三日）→ **分母问题直接解决**，修掉 B076 `b076_fetch_pit_marketcap.py:83` 用换手率反推**流通市值**（禁令 #6）。
  - 退市名 **338 只**（263 只在 2013 年后）→ 幸存者偏差可解（禁令 #11）。
  - **★许可证：用户 2026-07-20 确认允许内部长期归档** → 上游报告 §10 的 snapshot/hydrate/离线复现契约**首次有合规基础**。
- **B108 巨潮 parser ⏹ 转向收尾**：F001/F002 done，**★F003=superseded — 硬门从未通过，不得读作验收通过**。两轮独立验收均 FAIL（首轮 5.3% coverage / 11 缺陷 E01-E11；复验 16.7% / 新引入 10³ 错值 N01-N05）。★**年报三轮仍 1/34**，parser 实质只在半年报工作。**就获取归母净利润而言性价比输给 Tushare**；巨潮回归 **truth anchor** 定位（上游 §8.1 原本的 P0 角色），代码转审计工具入 B109。
- **B107 生产迁移 ✅ done**（手工置 done，F003=waived）。生产在 deploysvr（`194.238.26.173`），健康，version 对齐 HEAD。老机冻结作回滚点。
- **B106–B074 ✅**。

## 接续 / 待决策
- **F001 先行的理由**：`flag=0` 保留率波动是唯一能推翻 F002 设计的未知数；且三问探针**只测了年报**，而 TTM 需四个连续单季——**季报 vintage 若显著更差，PIT 分子直接不成立**。
- **★Tushare token 建议轮换**（用户对话中明文提供，已提出未执行）。当前存 `.env.local`（600、`.gitignore` `.env.*` 覆盖、已 `git check-ignore` 验证未入仓）。
- **★遗留（非本批）**：`600787`(0.87%)/`601992`(29.28%) 两份人工裁定；`workbench-advisor.service` **402** = **aigc 侧 key 配额/权限问题**（AIGC 余额 $22.34 非零、同日其他 client 正常）；**P6 🔴 老 VM 退役**未做。
- **★关键坑（本机专属）**：Clash fake-ip 代理下连老机会路由到**错的机器** → 一律 `ssh deploysvr` 再跳。
- backlog 剩：residual-engine（B100 INCONCLUSIVE）+ B106-S3。34+ learnings 待用户确认。
- **★负责人纪律**：验收结论 git 核实才采信（B104/B105 幻觉教训）。

## 永久硬边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO）**。红利低波留 A股本土组合才兑现负相关分散。
- cn_attack 研究态/OOS 红卡不可配资。冻结再验证 pipeline **永不** validated→True。golden 只进测试 fixture seam。**smart-money 免费信号 first-look 均 research-only（0 产品码）无一切入生产。**
- **A股 PIT 数据禁令**（handoff §14）：禁 `(ticker,quarter)` latest-wins / 禁法定截止日代公告日 / 禁流通市值代总市值 / 禁当前股本×历史价 / 禁只拉 `list_status=L`。**当前仍 `DATA_NO_GO`，B109 不改变该裁定。**
- **★B108 沉淀的方法论纪律（跨批次适用）**：最终测量必须在**全新 seed** 的 holdout 上（两轮都出现「在已看过的语料上调参」，样本内 26.3% vs 样本外 16.7% = 高估 57%）；Generator 不得抽评测样本；**被规则挡住不等于被验证过**（E01 联网路径因 H3 禁止而零执行却标了 done）；**每轮修复都可能引入同类新缺陷**，跨模块相互作用（N01 = E03×E04）只有独立 holdout + 对拍旧实现才暴露。

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点。
- **v0.9.55**（f67332e, 2026-07-06）：B080-B098 队列 9 条 learnings 沉淀。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（改 trade/ 后须重装）。scipy 未装。**`tushare` 1.4.29 已装入 `.venv`。**
