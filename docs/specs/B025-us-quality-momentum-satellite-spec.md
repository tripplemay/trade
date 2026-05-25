# B025 — US Quality Momentum Satellite

> Status：active (planning → building)
> Owner：Generator (F001-F005) + Codex (F006)
> Predecessor：B024 (Workbench i18n zh-CN + en) — done 2026-05-22
> 估时：3-4 周
> 范围分类：post-MVP feature batch（不在 PRD §10/§11/§12 内；BL-B011-S2 high 拆解的 US Quality 部分；HK-China satellite 留 B026 候选）

## 1. 目标

把 Master Portfolio 的 `satellite_us_quality` sleeve 从 `satellite_stub`（当前 fall-through 到 defensive/SGOV）升级为 `implemented_strategy`，对应一个全新的 5 因子美股个股策略 `us_quality_momentum`。

落地范围：策略实现 + 回测 + Master Portfolio 接入 + workbench UI 双语展示（继承 B024 i18n），用户在生产 `trade.guangai.ai` 上可以看到 satellite_us_quality 实际持仓与回测指标。

所有 PRD §5 非 MVP 边界 + B012/B021/B022/B023/B024 永久硬边界 100% 继承。本批次不引入 broker SDK / 不引入 live / paper / paid 数据源 / 不引入 ML 模型。

## 2. 决策矩阵（用户已批，2026-05-25）

| 维度 | 决策 |
|---|---|
| 范围 | 全栈：strategy + factor + portfolio construction + Master Portfolio 接入 + backtest + workbench UI 展示 |
| 数据策略 | **纯 fixture / mock**（最严格 no-live；fixture 文件入 `data/fixtures/us_quality_momentum/` 且包含 universe + 价格 + 基本面 + 行业 + 财报日全集；point-in-time enforced） |
| 因子权重 | strategy doc §7 **完整版**：`total = 0.35 momentum + 0.30 quality + 0.15 low_vol + 0.10 value + 0.10 trend` |
| 股票池 | S&P 500 + Nasdaq 100 的代表性子集（30-50 ticker，跨 11 GICS sector）。fixture 固定 universe，研究阶段不动；HK-China 不进本批次 |
| 持仓数量 | Top 15（首版默认；测试需对比 Top 10 / 15 / 20 / 30 至少在回测附录中给出） |
| 权重方法 | 等权 `weight_i = 1/N`，单股 ≤7% / 行业 ≤30%（按 strategy doc §9.1） |
| 调仓频率 | 月度信号；首版接入 Master Portfolio 时复用 quarterly cadence（B011 已固定）；月度信号文件归档但不强制 Master 月度调仓 |
| 财报规避 | 财报日前 3-5 个交易日不主动新开大仓位（fixture 中的 earnings_date 字段驱动） |
| 行业约束 | 单行业 ≤30%；不要求严格行业中性 |
| ML 边界 | 禁止 LightGBM / XGBoost / CatBoost / 任何 ML 模型出现在 strategy 代码或 fixture 生成脚本；规则型加权评分 only |
| Master sleeve 改动 | `satellite_us_quality.sleeve_type` SATELLITE_STUB → IMPLEMENTED；`strategy_id` = `"us_quality_momentum"`；planning_weight 保持 0.20；其他 3 sleeves 完全不动；保留双 helper（`default_master_portfolio_parameters()` 与 `_with_regime_adaptive()`） |
| UI 双语 | 继承 B024 i18n，新 sleeve 文案 zh-CN + en 同步加入 messages bundle；专业术语保留英文（`quality_score` / `momentum_12_1` / `Top 15` / GICS sector names） |

## 3. 永久硬边界（B025 起继续 enforced）

继承 B012/B021/B022/B023/B024 全部边界，**本批次不放宽任何一条**：

- 无 broker SDK 引入 / 无 paper/live API URL / 无凭证 / 无自动下单
- 单用户 / 无注册 UI / 单 email allowlist / 无 multi-user 路径
- 同源 `/api/*`（v0.9.24 #3）/ Repository pattern / auth-gated
- 中文按钮禁词（B024 v0.9.26）：`执行 / 下单 / 发送券商 / 立即买入 / 实盘 / 真实交易 / 自动交易 / 一键交易` 与英文 `execute / place order / send to broker` 同级 enforced
- Order ticket Markdown 含英文 + 中文 disclaimer 双语字面串（B024 v0.9.26 不可破）
- Production HEAD ≡ main HEAD（v0.9.25 §Production/HEAD 等价性）
- fixture-first：所有数据来源 = 仓库内 fixture 文件 + 生成脚本；CI 跑测试**完全离线**（no network / no secret / no env-dependent path）
- ML 边界：禁止 ML 模型代码、ML 库 import（sklearn 仅允许用于 deterministic ranking / scoring 工具函数，禁止 model fit / predict 调用）

## 4. 技术架构

### 4.1 Fixture 设计

```
data/fixtures/us_quality_momentum/
├── universe.csv              # ticker, name, exchange, gics_sector, gics_industry, listing_date, market_cap_initial
├── prices_daily.csv          # date, ticker, open, high, low, close, adj_close, volume; ≥10 年；split-adjusted
├── fundamentals.csv          # report_date, ticker, roe, gross_margin, fcf_yield, debt_to_assets, pe, pb, ev_ebitda, earnings_yield; report_date = 财报披露当天（point-in-time）
├── earnings_calendar.csv     # ticker, earnings_date, fiscal_quarter
└── README.md                 # fixture 生成方式、字段定义、point-in-time 规则
```

**约束：**
- universe 固定 30-50 ticker，跨 GICS 11 行业，至少 5 行业 ≥3 ticker
- 价格 fixture 跨 ≥10 年（覆盖 2008 / 2011 / 2015-16 / 2018 / 2020 / 2022 / 2023-25 七个市场阶段中的至少 5 个）
- 基本面 report_date **必须晚于** fiscal quarter end（最少 30 天），且因子计算时 `effective_date = report_date + 1 trading day`
- 所有数据 deterministic：fixture 生成脚本输出可复现的 CSV（同一 seed 生成同一文件）；csv 内容入仓库（≤2 MB）
- 禁止 fixture 中包含真实公司财报数据；ticker 名用真实 S&P/Nasdaq 字母代码但所有 numerical 字段为合成数据（spec 明示 `# synthetic data, not actual filings`）

### 4.2 策略代码结构

```
trade/strategies/us_quality_momentum/
├── __init__.py                   # __all__: UsQualityMomentumParameters, signal()
├── parameters.py                 # @dataclass(frozen=True, slots=True) UsQualityMomentumParameters + parameter_hash()
├── factors.py                    # momentum / quality / low_vol / value / trend 5 因子计算函数（pure functions）
├── ranking.py                    # rank-based 标准化 + 综合评分聚合
├── construction.py               # Top-N 选股 + 等权 + 单股/行业约束 + 财报日规避
└── signal.py                     # signal(parameters, universe, prices, fundamentals, earnings, as_of_date) -> SignalResult
```

**模式：** 复用 `trade/strategies/global_etf_momentum.py` 模式（frozen dataclass parameters + parameter_hash + signal pure function；不引入 class hierarchy）。

### 4.3 Master Portfolio 接入

`trade/portfolio/master.py` 改动（精准 1 处）：

```python
# Before (B011 默认 sleeve 3 of 4)
MasterSleeveConfig(
    sleeve_id="satellite_us_quality",
    sleeve_type=SLEEVE_TYPE_SATELLITE_STUB,
    strategy_id=None,
    planning_weight=0.20,
    role_label="satellite_alpha_stub",
),

# After
MasterSleeveConfig(
    sleeve_id="satellite_us_quality",
    sleeve_type=SLEEVE_TYPE_IMPLEMENTED,
    strategy_id="us_quality_momentum",
    planning_weight=0.20,
    role_label="satellite_alpha",
),
```

- 其他 3 sleeve（momentum / risk_parity / satellite_hk_china）**完全不动**
- `_REGIME_ADAPTIVE_SLEEVE` 与 `default_master_portfolio_parameters_with_regime_adaptive()` 保持原样
- B011 既有测试断言（`tests/unit/test_master_portfolio_config.py`）若包含「satellite_us_quality 是 SATELLITE_STUB」断言，本批次需同步更新该断言并新增「satellite_us_quality 是 IMPLEMENTED + strategy_id」断言；不删原 satellite_hk_china stub 断言

### 4.4 Backtest 接入

```
trade/backtest/us_quality_momentum/
├── __init__.py
├── engine.py                     # 单 sleeve 回测 driver (复用 trade/backtest/ 既有 BacktestRunner 模式)
└── metrics.py                    # 输出指标计算（年化 / Sharpe / Sortino / Calmar / MDD / 换手率 / 胜率 / 盈亏比 / 行业暴露 / 因子贡献 / SPY-QQQ 超额）
```

**输出位置：**
- 报告 JSON：`reports/us_quality_momentum/<as_of_date>.json`
- 报告 Markdown：`reports/us_quality_momentum/<as_of_date>.md`（双语：英文指标名 + 中文译名并列；继承 B024 §4.3 模式）

**基准：**
- SPY（fixture 价格序列）
- QQQ（fixture 价格序列）
- RSP（fixture 价格序列，等权 S&P 500）
- 静态持有 Top 15（同一天选股后冻结持仓全期）

**Master Portfolio 回测：** 4-sleeve 加权 + quarterly cadence + drawdown_threshold=0.15 kill-switch（B011 既有路径），验证接入新 sleeve 后 Master 回测 deterministic（同 fixture + 同 seed → 同输出）。

### 4.5 workbench UI 接入

**前端改动范围（5 路由）：**

| 页面 | 改动 |
|---|---|
| `/strategies` | strategies 列表新增 `us_quality_momentum` 条目（按 strategy_id 索引到中英 messages） |
| `/strategies/[id]`（如有详情页）或新建 sleeve detail 卡片 | 展示 5 因子权重、Top 15、单股/行业约束、调仓频率（zh + en） |
| `/recommendations` | satellite_us_quality 区块显示 target positions（来自 strategy signal 输出） |
| `/risk` | Risk panel 加 satellite_us_quality sleeve 的 drawdown / exposure / kill-switch 状态条 |
| `/reports`（含 `/reports/[slug]`） | 新增 us_quality_momentum 回测报告条目（指标 + 行业暴露饼图 + 累积收益曲线） |

**双语 messages（继承 B024 v0.9.26 i18n）：**
- 新 namespace `strategies.usQualityMomentum.*` 在 `messages/zh-CN.json` 与 `messages/en.json`，key set bit-identical
- 专业术语保留英文：`Top 15`, `Sharpe`, `Sortino`, `Calmar`, `momentum_12_1`, `quality_score`, `low_vol_60d/120d/252d`, `GICS sector`, `bps`
- 禁词检查：本批次不引入任何新按钮（UI 只是展示；不需要「生成清单」「作废」类按钮）；safety regression spec 跑通

**no-execution-buttons regression：** F006 必须验证新 UI 路径 0 命中 `tests/safety/no-execution-buttons.spec.ts`（含英文 + 中文禁词集）。

### 4.6 backend API（如有）

**默认假设：** 回测报告 JSON 已经由 backtest 流程落到 `reports/us_quality_momentum/`，workbench backend 现有 `/api/reports/*` endpoint 可直接复用。新增 endpoint 仅在以下情况引入：

- `/api/strategies/us_quality_momentum/signal/current` — 若 Recommendations 页面要展示当前 target positions（按 strategy signal 实时计算）
- 上述 endpoint 必须走 Repository pattern 读 fixture，**不读真实文件系统** runtime data path；HTTPException detail 全部走 B024 i18n `t()` 函数；Accept-Language 协议继承

**API 不动的部分：**
- 不动 B023 manual execution endpoint
- 不动 B024 i18n module
- 不动 `/api/execution/account` PUT 路径（continue to honor B024 `cash<0` locale 422）

## 5. Feature 拆分

### F001 — Fixture + Universe + 流动性过滤（generator，4-5 天）

**Acceptance：**
- 新建 `data/fixtures/us_quality_momentum/` 子目录与 4 个 CSV + README.md
  - `universe.csv`：30-50 ticker，跨 ≥7 GICS sector，每 sector ≥2 ticker；含字段 `ticker, name, exchange, gics_sector, gics_industry, listing_date, market_cap_initial`
  - `prices_daily.csv`：跨 ≥10 年 deterministic 合成序列；含字段 `date, ticker, open, high, low, close, adj_close, volume`
  - `fundamentals.csv`：每 ticker 每季度一行（4 / 年 × 10 年 × N ticker），含字段 `report_date, ticker, fiscal_quarter, roe, gross_margin, fcf_yield, debt_to_assets, pe, pb, ev_ebitda, earnings_yield`；`report_date >= fiscal_quarter_end + 30d`
  - `earnings_calendar.csv`：每 ticker 每季度 1 个 earnings_date，`earnings_date <= report_date`
- `README.md` 标注 **synthetic data, not actual filings**，记录 fixture 生成脚本与 seed
- 新建 `data/fixtures/us_quality_momentum/_generate.py`（不入 pytest CI 路径，仅作为 fixture 再生工具；运行 deterministic with `--seed` 参数）；CSV 文件入仓库，CI 不重新生成
- 新建 `trade/data/us_quality_universe.py` Repository：`load_universe()` / `load_prices(as_of)` / `load_fundamentals(as_of)` / `load_earnings_calendar(as_of)` — 全部 point-in-time，返回 `as_of_date` 之前可见的数据
- 新建 `trade/data/us_quality_filter.py` 流动性过滤：`apply_liquidity_filter(universe, prices, as_of, market_cap_threshold=10e9, adv60_threshold=50e6, price_threshold=10, listing_age_years=2)`
- pytest 新增 ≥15 测试：universe loader / point-in-time 隔离（确保 as_of 前看不到未来数据） / filter 边界 / earnings calendar 一致性 / fixture schema 完整性
- ruff + mypy 清
- `python3 -c "import json; json.load(...)"` 校验不适用（CSV 路径），但 `python -c "import pandas as pd; pd.read_csv(...)"` smoke 进入 F001 pytest

### F002 — 5 因子计算 + 标准化（generator，5-6 天）

**Acceptance：**
- 新建 `trade/strategies/us_quality_momentum/factors.py`，5 个 pure function：
  - `momentum_12_1(prices, as_of, lookback_months=12, skip_months=1) -> Series` （主力）
  - `momentum_6m(prices, as_of) -> Series`（辅助，可选输出）
  - `quality_score(fundamentals, as_of) -> Series` = `rank(roe) + rank(gross_margin) + rank(fcf_yield) - rank(debt_to_assets)`
  - `low_vol_score(prices, as_of, windows=(60, 120, 252)) -> Series`（倒数 vol 排名）
  - `value_score(fundamentals, as_of) -> Series` = avg(rank(1/pe), rank(1/pb), rank(1/ev_ebitda), rank(fcf_yield), rank(earnings_yield))
  - `trend_score(prices, as_of) -> Series`：`price > MA200 AND MA50 > MA200 AND MA200_slope > 0` → 1.0；否则 0.0；中间状态按斜率插值 [0, 1]
- 新建 `trade/strategies/us_quality_momentum/ranking.py`：`standardize(series) -> Series` rank-based（min-max normalize 到 [0, 1] 或 z-score；spec 推荐 percent_rank）
- 全部因子函数接收 pandas DataFrame / Series 输入，纯函数无 IO，无副作用
- pytest 新增 ≥25 测试：
  - 每因子 happy path + edge case（缺失数据 / 全相等 / 单 ticker）
  - point-in-time 严格性（财报数据 report_date 之前不可见）
  - 标准化函数（zero-variance / NaN 处理 / order preservation）
  - 跨因子组合：同 as_of 多次计算结果一致（deterministic）
- ruff + mypy 清

### F003 — 综合评分 + 选股 + 权重 + 约束（generator，4-5 天）

**Acceptance：**
- 新建 `trade/strategies/us_quality_momentum/parameters.py`：

  ```python
  @dataclass(frozen=True, slots=True)
  class UsQualityMomentumParameters:
      strategy_id: str = "us_quality_momentum"
      top_n: int = 15
      factor_weights: FactorWeights = FactorWeights(
          momentum=0.35, quality=0.30, low_vol=0.15, value=0.10, trend=0.10
      )
      max_position_weight: float = 0.07
      max_sector_weight: float = 0.30
      earnings_window_days: int = 5  # 财报前 5 个交易日不新开仓
      rebalance_frequency: str = "monthly"
      def parameter_hash(self) -> str: ...
  ```

- 新建 `trade/strategies/us_quality_momentum/construction.py`：`build_portfolio(scores, universe, sector_map, earnings_dates, as_of, parameters) -> PortfolioWeights`
  - Step 1: total_score 加权聚合（5 因子）
  - Step 2: 排序取 Top N（默认 15）
  - Step 3: 财报规避（如 ticker 在 [as_of, as_of + earnings_window_days] 内有 earnings_date，且**当前未持仓**，则跳过；已持仓 ticker 在财报窗口内**不调整权重**）
  - Step 4: 等权 1/N
  - Step 5: 单股上限 7% / 行业上限 30%（超限按比例缩减 + 余额按行业内非超限分摊）
  - Step 6: 返回 `PortfolioWeights = dict[ticker, float]`（sum 接近 1.0 ± 1e-8，未填满部分计入 cash buffer）
- 新建 `trade/strategies/us_quality_momentum/signal.py`：`generate_signal(parameters, as_of_date) -> SignalResult` 完整 pipeline，输入 as_of_date，输出 `SignalResult = (parameters_hash, weights, sector_exposure, factor_contributions)`
- pytest 新增 ≥20 测试：
  - 评分聚合（5 因子权重和 = 1.0）
  - Top N 选股
  - 单股上限触发
  - 行业上限触发（一个行业 6 ticker 但 ≤30% 总仓位）
  - 财报规避（已持仓 ticker / 新候选 ticker / 已过财报日 ticker 三场景）
  - 不可重复 ticker
  - 等权 sum 接近 1.0
  - parameter_hash deterministic
- ruff + mypy 清

### F004 — Master Portfolio 接入 + Backtest + 报告（generator，6-7 天）

**Acceptance：**
- 改 `trade/portfolio/master.py`（§4.3）：satellite_us_quality 单 sleeve stub → implemented，其他 3 sleeve 完全不动
- 改 `tests/unit/test_master_portfolio_config.py`：satellite_us_quality 既有 stub 断言改为 implemented 断言；strategy_id 断言 = `"us_quality_momentum"`；satellite_hk_china 仍是 stub 不动
- 新建 `trade/backtest/us_quality_momentum/engine.py` + `metrics.py`
- 单 sleeve backtest 跑 ≥10 年（fixture 范围），输出 JSON + Markdown 报告到 `reports/us_quality_momentum/<as_of_date>.{json,md}`
- 指标必输出：年化收益 / 年化波动 / Sharpe / Sortino / Calmar / MDD / 月度收益矩阵 / 年度收益表 / 换手率 / 胜率 / 盈亏比 / 行业暴露 / 单股贡献 / 因子贡献 / 相对 SPY / QQQ / RSP / 静态 Top 15 超额收益
- Markdown 报告双语字段（继承 B024 §4.3 模式，英文指标名 + 中文译名并列；专业术语 Sharpe/Sortino/Calmar/MDD/bps 不译）
- 报告头部含「**research-only; not a trading instruction / 仅供研究使用；不构成交易指令**」双语 disclaimer（继承 B024 v0.9.26）
- Master Portfolio 回测：4-sleeve 加权 deterministic 跑通；既有 `tests/unit/test_master_portfolio_backtest.py` 全过；新增 ≥5 个 Master backtest 测试覆盖 satellite_us_quality 实际持仓 + kill-switch 触发场景
- pytest 新增 ≥30 测试（单 sleeve backtest + master integration + metrics + report serialization）
- 基准对比断言：单 sleeve backtest annualized return + 关键 metrics 落 spec 预期范围（年化 [5%, 25%]、Sharpe [0.3, 1.5]、MDD < 50%）—— 注意：fixture 是合成数据，断言落 deterministic 范围，不强求达成 strategy doc §3 实盘目标
- ruff + mypy 清

### F005 — workbench UI 全栈双语展示（generator，6-8 天）

**Acceptance：**

**前端：**
- 5 路由覆盖：`/strategies` / `/strategies/[id]`（或 sleeve detail 卡片）/ `/recommendations` / `/risk` / `/reports` + `/reports/[slug]`
- 新 namespace `strategies.usQualityMomentum.*` 加入 `messages/zh-CN.json` 与 `messages/en.json`，key set bit-identical（vitest `messages-key-parity.spec.ts` 不破）
- 双语字段（每条至少 2 处）：
  - 策略名（zh: `美股质量动量` / en: `US Quality Momentum`）
  - 5 因子标签（zh: `动量 / 质量 / 低波 / 价值 / 趋势` / en: `Momentum / Quality / Low Vol / Value / Trend`）
  - 行业名（继承 GICS 英文不译；中文展示英文术语保留括号注释）
  - Risk panel sleeve 名称 / drawdown / exposure / kill-switch 状态
- Recommendations 页面展示 satellite_us_quality target positions table（ticker / weight / sector）
- Risk panel 加新 sleeve 一行（drawdown / exposure 条 + kill-switch indicator）
- Reports 列表 + 报告详情页展示双语 Markdown
- vitest 新增 ≥10 测试（renderWithIntl helper，沿用 B024 F002 模式）
- Playwright zh-CN + en 双 locale 跑 5 路由 smoke，≥10 个 H1 / label assertion 双 locale
- 截图 5 页 × 2 locale = 10 PNG 存 `docs/screenshots/B025-us-quality/{zh-CN,en}/` ≤300 KB each

**Backend（如需）：**
- 若引入 `/api/strategies/us_quality_momentum/signal/current` endpoint：走 Repository pattern（不动 file system runtime）+ HTTPException detail 用 `t()` + Accept-Language 协议继承 + pytest parametrize zh-CN/en
- 若不引入新 endpoint，直接复用 `/api/reports/*`：spec 中明示 "no new backend endpoint" 并跑通 reports 路径

**Gate（共有）：**
- 中文按钮禁词 vitest grep 0 命中（safety regression 不破）
- B024 既有 146 vitest 全过 + B025 新增测试
- lint / typecheck / build 绿；build artifact 无 127.0.0.1 / :872x
- npm audit --omit=dev --audit-level=high exit 0
- ruff + mypy（若动 backend）清

### F006 — Codex L1 + L2 真 VM 验收 + signoff + framework v0.9.27 候选（codex，3-4 天）

**L1 (CI 内)：**
- F001-F005 全部 generator 验收脚本跑通：
  - backend：`pytest tests` (≥240 baseline + 新增 ≥80 = ≥320) / `ruff check .` / `mypy workbench_api tests` + `mypy trade`
  - frontend：`npm run lint` / `npm run typecheck` / `npm test` (≥146 baseline + 新增 ≥10 = ≥156) / `npm run build` / `npm audit --omit=dev --audit-level=high` exit 0
  - frontend safety：`tests/safety/no-execution-buttons.spec.ts`（含 B024 中文禁词）≥15 spec assertions 0 命中
  - frontend artifact：`grep -rE 'http://127\.0\.0\.1:|http://(127\.0\.0\.1|localhost):872[0-9]' .next/static/` exit=0
  - frontend i18n key parity：`messages-key-parity.spec.ts` 严格相等
  - backend i18n parity：B024 既有 31 i18n 测试不破 + 新批次（若引入新 endpoint）pytest parametrize zh-CN / en
  - Playwright：≥19 baseline + 新增 ≥10 双 locale = ≥29 passed
- 同源 regression、Repository pattern regression、no-broker-sdk-imports、no-hardcoded-backend-host 全绿
- fixture 离线验证：`pytest` 在 `--no-network` / 无网络环境下全过

**L2 (真 VM)：**
- OAuth → Home zh-CN 默认渲染 ✓
- 导航至 `/strategies`、`/strategies/[id]`、`/recommendations`、`/risk`、`/reports` 各页面：satellite_us_quality 名称、5 因子标签、target positions、risk panel sleeve 行、回测报告链接全部显示
- 切换 en → 整站英文（含 satellite 名称 + 因子标签 + GICS sector）
- 切回 zh-CN cookie 持久
- 至少 1 个回测报告 Markdown 落盘到 `reports/us_quality_momentum/`，双语 disclaimer + 双语字段都出现
- Production HEAD ≡ main HEAD（同 SHA）
- `/api/debug/recent-errors` count=0 after full L2 flow
- 副作用恢复：账户 cash=0 / positions=[]（沿用 B023 / B024 模式；本批次不引入新写入路径，理论上 L2 也不动 account state）

**Signoff 产物：**
- `docs/test-reports/B025-us-quality-signoff-2026-MM-DD.md` 用 `framework/templates/signoff-report.md`（含 §Production/HEAD 等价性 段）
- `docs/screenshots/B025-us-quality/{zh-CN,en}/` ≥10 PNG 已在 F005 落地，签收报告引用
- `framework/proposed-learnings.md` 追加 v0.9.27 候选：
  1. **多因子策略 fixture 设计模式**（point-in-time + multi-factor + 合成数据明示；写入 `framework/harness/generator.md` 新 §16 或 patterns 章节）
  2. **Master Portfolio sleeve stub → implemented 转换流程**（精准 1 处改动 + B011 既有测试同步 + 其他 sleeve 不动；写入 `framework/harness/planner.md` 或 generator.md sleeve patterns）
  3. **Earnings calendar 规避在个股策略中的标准实现**（fixture 字段 + construction step 顺序 + 已持仓 vs 新候选 vs 已过财报日三场景；写入 `framework/harness/generator.md` strategy patterns）

## 6. 不做的事（YAGNI）

- ❌ HK-China satellite（留 B026 候选；BL-B011-S2 high 拆分剩余部分）
- ❌ ML 模型（LightGBM / XGBoost / CatBoost / 任何 fit-predict 路径）
- ❌ 真实 broker / paper API 接入
- ❌ Paid 数据源（FactSet / Refinitiv / Bloomberg / EODHD）
- ❌ Smoothed / feedback volatility targeting（留 BL-B013-D1 low）
- ❌ VIX tail risk overlay（留 BL-B013-D2 low）
- ❌ Risk parity 专用 fixture（留 BL-B010-S1 low）
- ❌ 港股 / ADR / 国际指数（HK-China 独立批次）
- ❌ AI 风控签字（strategy doc §17 提及，但本批次不实现 AI 路径）
- ❌ 月度强制 Master Portfolio 调仓（Master 维持 B011 quarterly cadence；strategy 月度信号仅归档不强制）
- ❌ 用户自定义参数 UI（参数固定，spec 内决策矩阵即权威）
- ❌ Walk-forward / out-of-sample 自动化（fixture 是合成数据，walk-forward 留作未来真数据接入后再做）

## 7. 验收门槛汇总

| 门槛 | F# 责任 |
|---|---|
| fixture universe 跨 ≥7 GICS sector + 价格 ≥10 年 + 财报 point-in-time | F001 |
| fixture loader + 流动性过滤 + Repository pattern | F001 |
| 5 因子 pure function + rank-based 标准化 + pytest ≥25 | F002 |
| 综合评分 35/30/15/10/10 + Top 15 等权 + 单股 ≤7% / 行业 ≤30% + 财报规避 | F003 |
| Master `satellite_us_quality` SATELLITE_STUB → IMPLEMENTED（其他 sleeve 不动） | F4 |
| 单 sleeve backtest ≥10 年 + 全指标输出 + 基准对比 | F004 |
| Master Portfolio 4-sleeve 回测 deterministic + 既有 backtest 测试不破 | F004 |
| 回测报告 Markdown 双语 + 双语 disclaimer | F004 |
| workbench UI 5 路由双语展示 + messages key parity | F005 |
| vitest ≥156 + Playwright ≥29 双 locale + lint/tsc/build/npm audit 全绿 | F005 + F006 |
| 中文按钮禁词 vitest grep 0 命中 + safety regression 全绿 | F005 + F006 |
| pytest ≥320 + ruff + mypy 清 | F006 |
| 同源 regression / no-broker-sdk-imports / no-hardcoded-backend-host / Repository pattern | F006 |
| L2 真 VM zh + en 双 locale 完整走通 5 路由 | F006 |
| Production HEAD ≡ main HEAD | F006 |
| `/api/debug/recent-errors` count=0 after full L2 flow | F006 |
| Signoff 报告 framework/templates/signoff-report.md 全段 | F006 |
| framework v0.9.27 候选 3 条写入 `framework/proposed-learnings.md` | F006 |

## 8. 参考文档

- `docs/strategy/03-us-quality-momentum.md` — 策略说明书（首版参数权威来源）
- `docs/specs/B024-i18n-zh-cn-spec.md` — i18n 基建（双语模式）
- `docs/specs/B023-workbench-phase2-manual-execution-spec.md` — manual execution 边界
- `docs/prd/mvp-completion-declaration-2026-05-20.md` — MVP 完工范围
- `trade/portfolio/master.py` — Master Portfolio sleeve 配置（接入点）
- `trade/strategies/global_etf_momentum.py` — 现有 strategy 实现模式（参考）
- `trade/strategies/risk_parity.py` — 现有 strategy 实现模式（参考）
- `framework/harness/generator.md` §10-15（safety regression / cloud deploy / FastAPI 观测 / i18n middleware chain）
- `framework/harness/planner.md`（角色行为规范 + B024 v0.9.26 沉淀两节）
- `framework/templates/signoff-report.md`（含 §Production/HEAD 等价性）
- `framework/CHANGELOG.md` v0.9.26

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Fixture 合成数据导致 backtest 指标无法对应实盘 | Spec §4.1 明示 synthetic；F004 断言只验 deterministic 范围，不验真实表现；Markdown 报告头部双语 disclaimer 强制 |
| 5 因子 + 行业约束 + 财报规避叠加导致 construction 算法 corner case 多 | F003 ≥20 测试覆盖；construction step 顺序固定（评分 → Top N → 财报规避 → 等权 → 单股缩减 → 行业缩减）；不引入优化器 |
| Master Portfolio 回测既有断言可能因新 sleeve implemented 失败 | F004 任务明确包含「同步更新 `test_master_portfolio_config.py` satellite_us_quality 断言」；其他 sleeve 完全不动 |
| workbench UI 双语 messages key 漂移 | F005 沿用 B024 vitest `messages-key-parity.spec.ts`；F006 L1 必跑 |
| L2 真 VM 接入 strategy signal endpoint 后引入 file system runtime 路径破坏 Repository pattern | F005 明示「Repository pattern + 不读 runtime file system」；F006 L2 检查 same-origin + recent-errors |
| ML 边界被无意破坏（如某 ranker 工具用了 sklearn fit） | F002 spec 明示 sklearn 仅允许 ranking 工具函数，禁止 model fit/predict；F006 grep `sklearn.*fit\\|predict` 列入 safety regression |

## 10. 与既有批次的边界

- 不动 B011 Master Portfolio 4 sleeve 配置（除 satellite_us_quality 一处）
- 不动 B011 既有测试除 satellite_us_quality 单条断言
- 不动 B013 regime adaptive sleeve / B016 HRP / B019 vol-target retune / B020-B023 workbench infrastructure
- 不动 B024 i18n middleware chain / messages bundle 既有 key（仅追加新 namespace）
- 不动 NextAuth / Cloud SQL / OAuth / systemd 部署
- 不动 `/api/execution/*` manual execution endpoint
- 不动 Order ticket Markdown 既有双语 disclaimer（仅 reports/ Markdown 沿用 B024 模式）

## 11. 后续批次（不在 B025 范围）

- **B026 候选：** HK-China satellite ETF（BL-B011-S2 剩余部分；首期 US-listed ADR/ETF proxy；预估 2-3 周）
- **B027 候选（low）：** Smoothed vol-targeting / VIX tail overlay / risk parity 专用 fixture / B023 prod 冒烟（BL-B010-S1 / BL-B013-D1 / BL-B013-D2 / BL-B023-S1+S2 批量）

---

> 本 spec 完成后，progress.json status=building（含 generator features），current_sprint=F001，Generator 接 fixture + universe loader。
