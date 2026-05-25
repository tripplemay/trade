---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B025-us-quality-momentum-satellite：`done`**；F001-F006 全部完成并签收。Signoff：`docs/test-reports/B025-us-quality-signoff-2026-05-25.md`。
- Production HEAD = main HEAD = `abaaf6e6a162d0ce73305e71ec1c29b54512da5f`（签收时；v0.9.25 §Production/HEAD 等价性 验证通过）。
- F006 经历 4 轮 fix-round（round-1 缺独立 /risk + Playwright 套件不足 / round-2 stale dev process / round-3+4 chore commit deploy drift），产品代码自 `afa154d` 后未变；framework v0.9.27 已沉淀这 3 个跨批次教训以防 B026+ 再撞。
- 目标已达成：把 Master Portfolio 的 `satellite_us_quality` sleeve 从 stub 升级为 implemented + 5 因子美股个股策略 + workbench UI 5 路由双语展示。
- 决策矩阵（2026-05-25 用户已批）：全栈（strategy + backtest + Master + UI）；纯 fixture / mock（synthetic 明示）；因子权重 `0.35 mom + 0.30 quality + 0.15 lowvol + 0.10 value + 0.10 trend`；股票池 30-50 ticker ≥7 GICS sector；Top 15 等权 + 单股 ≤7% + 行业 ≤30% + 财报前 5d 不新开仓；月度信号 + Master quarterly cadence。
- ML 边界：禁止 LightGBM/XGBoost/CatBoost/任何 fit-predict 路径；sklearn 仅允许 ranking 工具函数。
- Master Portfolio 改动：精准 1 处（`satellite_us_quality` SATELLITE_STUB → IMPLEMENTED + strategy_id），其他 3 sleeve（momentum / risk_parity / satellite_hk_china）完全不动。

## 已完成签收 + MVP 完工
- B001-B025 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B025 US Quality Momentum Satellite signoff 2026-05-25；B024 i18n zh-CN + en signoff 2026-05-22。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench（默认 zh-CN，可切 en）+ OAuth + /api/health + /api/debug/recent-errors + daily 03:00 UTC backup + 4 sleeve 完整持仓展示（含新落地的 satellite_us_quality 5 因子）。

## 永久硬边界（B025 起继续；v0.9.28 AI 边界精细化）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：任何按钮 labelled execute/place order/send to broker 禁 + 中文等价禁词同级（v0.9.26）/ Order ticket Markdown 双语 disclaimer 永存
- 数据 / CI 层：fixture-first 离线 CI / framework v0.9.21-v0.9.28 全约束 / cloud-deploy 批次 deploy workflow 含 workflow_dispatch + Generator chore commit 后 dispatch deploy（v0.9.27）
- **AI 边界（v0.9.28 精细化，取代 v0.9.21-v0.9.27 一刀切 "no-AI fit/predict"）：**
  - (a) `no-AI auto-execution`：AI 不可触发任何自动下单 / 交易 / 调仓
  - (b) `no-AI 收益预测数字输出`：AI 不输出"预期年化 X%" / 任何收益预测数字
  - (c) `no-AI 替代 quant 评分作为唯一决策依据`：AI 是 quant signal 的叠加层，不可跳过 Master Portfolio 评分直接给 buy/sell
  - (d) `AI 输出必须基于 quant signal + real data + 可引用 news`：无引用的黑盒建议禁止；每条建议必带 quant_signal SHA / news source URL
  - (e) AI 做以下事项**允许**：解释（quant signal / 指标 / Sharpe 等术语 tooltip）/ summarize（news / SEC filings）/ translate（zh ↔ en）/ context aggregation / Robinhood-style 简化文案。

## Framework 状态
- 最新版本 **v0.9.28**（2026-05-25 沉淀完成）：B025 done 阶段结构澄清 + AI 边界精细化合并 sink。删除项目根 3 个 stale .md（planner/generator/evaluator）；harness-rules.md + CLAUDE.md 明确加载路径为 `.auto-memory/role-context/{角色}.md`（active）+ `framework/harness/{角色}.md`（按需查阅）；新建 `framework/STRUCTURE.md` 澄清目录语义；AI 边界从 `no-AI fit/predict` 一刀切改为 5 子条（auto-execution / 收益预测 / 替代 quant / 必须可引用 / 允许的解释 summarize translate context aggregation）。
- 上一版本 **v0.9.27**（2026-05-25）：B025 F006 4-round 实战教训 3 条（chore-only deploy 逃生口 / Playwright stale process / signoff Post-deploy 模板）；详见 v0.9.27 归档。

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（HK-China satellite；US Quality 已在 B025 落地剥离）→ 候选 B026
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium` 下载浏览器。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
