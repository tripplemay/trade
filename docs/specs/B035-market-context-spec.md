# B035 — Market Context（Phase 2 / Stream 2.C）

> **批次类型：** 混合批次（3 generator + 1 codex）
> **状态流转：** planning → building → verifying → (fixing ⟷ reverifying) → done
> **依赖：** B027/B029 snapshot foundation（✅）+ 独立于 B031-B034
> **决策对齐：** 2026-06-04 用户已批（见 §2）

---

## 1. 目标

为 Home 页提供**市场宏观 context**：FRED 宏观指标（10y 利率 / VIX / CPI）+ Alpha Vantage 免费指数（SPY / QQQ / DXY），每日更新，Home 页 market context 卡片呈现。复用 B027/B029 real-data snapshot foundation。

**本批次首次为项目引入调度器（scheduler/cron）** —— 但**严格 scope 为只读市场数据拉取**（见 §3 边界细分）。

**不做**（见 §6）：AI advisor（B036）/ news 关联（B034 已做）/ 把 market context 喂给 quant 策略 / 付费数据源 / 盘中实时（仅每日）。

## 2. 决策矩阵（2026-06-04 用户已批，★=用户拍板）

| # | 决策 | 取值 | 依据 |
|---|---|---|---|
| 1 ★ | 数据源 | **FRED + Alpha Vantage 两者** | 用户拍板；implementation-path §4 B035 行 |
| 2 ★ | 新 secret | `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY`，**用户申请 key** | 走 v0.9.30 §12.9 三处接线；用户负责 GitHub Secret + VM env |
| 3 ★ | 更新机制 | **引入 scheduler/cron（每日自动）** | 用户拍板；§3 严格 scope 为只读数据拉取 |
| 4 ★ | 存储 | **复用 B027/B029 snapshot foundation**（raw 落 `data/snapshots/` + metadata 表）| 用户拍板；与 prices/fundamentals 一致 |
| 5 | series | FRED：10y `DGS10` / VIX `VIXCLS` / CPI `CPIAUCSL`；Alpha Vantage：`SPY` / `QQQ` / `DXY`（或等效 ETF/指数 endpoint）| data-source §5 |
| 6 | live-validate | FRED + Alpha Vantage 均第三方 API，实施时各 live hit 一次锁 envelope + 字段路径，写守门 test | **B031 候选复用窗口**（若再撞 spec-invented-endpoint 即二例，Planner done 阶段评估沉淀）|
| 7 | CI / Cost | fixture-first 离线（live 仅 manual validate）/ 免费 tier ¥≈0（Alpha Vantage 25 req/day 免费上限注意）| 继承 B027/B029/B032/B033/B034 |

## 3. 永久硬边界（继承 + B035 scheduler 边界细分）

- **系统层（继承）：** no-broker SDK / no-paper-or-live URL / no-credential / **no-auto-execution（仅指自动 broker 下单 / 交易执行）** / 多用户禁 / Cloud SQL 禁 / same-origin `/api/*` / auth-gated / Repository。
- **数据/CI 层（继承）：** fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（§12.8）/ **v0.9.30 §12.9 secret 三处接线**（本批次 2 新 secret 触发）/ **v0.9.32 §12.10 请求路径 deploy-artifact 自包含**（market context 数据 materialise 入 `workbench_api/`，不读 repo-root fixtures）。
- **🆕 B035 scheduler 边界细分（r）：**
  - 项目首个调度器**仅允许做 read-only 市场数据拉取**（FRED / Alpha Vantage observations → snapshot + DB）。
  - **明确 NOT：** 不触发任何交易执行 / broker 下单 / recommendation 生成 / AI 调用 / 写 order ticket（系统层 no-auto-execution 不受影响——调度器只拉数据）。
  - **News 边界 (q) 不变**：News ingest 仍 production-disabled（无 scheduler）；本批次调度器只服务 market context，不碰 news。
  - 实现用 **systemd timer**（OS 级，调用 market-context CLI），不在 app 进程内跑 in-process scheduler，避免引入 APScheduler runtime dep + 保持 app 无状态。
  - 守门：`tests/safety/test_market_scheduler_scope.py` 断言 scheduler/CLI 路径不 import 交易/ticket/recommendation/LLM 模块。
- **AI 边界（v0.9.28）：** 本批次不触 AI logic（纯数值数据 ingest + 展示）。

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/
├── data/
│   ├── fred_loader.py            # F001 FREDMarketLoader (DGS10/VIXCLS/CPIAUCSL)
│   ├── alpha_vantage_loader.py   # F001 AlphaVantageLoader (SPY/QQQ/DXY)
│   └── fixtures/                 # F001 fred-*.json + alphavantage-*.json fixture
├── db/
│   ├── models/market_context.py          # F001 MarketContextObservation 表
│   ├── repositories/market_context.py     # F001 MarketContextRepository
│   └── migrations/versions/0007_b035_market_context.py  # down_revision=0006_b034_news_embedding
├── market/
│   ├── __init__.py
│   └── cli.py                    # F002 CLI：fetch 全 series → snapshot + DB（systemd timer 调用）
├── schemas/market_context.py     # F003 MarketContextResponse
└── routes/market_context.py      # F003 GET /market-context

workbench/deploy/
├── systemd/workbench-market-context.timer + .service   # F002 每日 timer（只读拉取）
└── scripts/deploy.sh             # F002 install timer + F001 2 secret pre-flight

workbench/frontend/src/app/(protected)/  # F003 Home market context 卡片
.github/workflows/bootstrap-env.yml       # F001 inject FRED_API_KEY + ALPHAVANTAGE_API_KEY
.env.example                              # F001 2 secret 注释
data/snapshots/market-context/{source}/{YYYY-MM-DD}/   # raw observations
```

### 4.2 `market_context_observation` 表（F001）

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID PK | 复用 `_UuidString` |
| series_id | TEXT NOT NULL | e.g. `DGS10` / `VIXCLS` / `SPY` |
| source | TEXT NOT NULL | `fred` / `alpha_vantage` |
| obs_date | Date NOT NULL | observation 日期 |
| value | Numeric NOT NULL | |
| snapshot_path | TEXT NOT NULL | raw 落 `data/snapshots/market-context/...`（复用 snapshot foundation）|
| fetched_at | DateTime(tz=True) NOT NULL | |

- Unique `uq_market_context_series_date (series_id, obs_date)` 幂等。
- Index `ix_market_context_series` / `ix_market_context_obs_date`。
- alembic `0007_b035_market_context`，`down_revision='0006_b034_news_embedding'`；downgrade 显式目标 `'0006_b034_news_embedding'`。
- raw observations 走既有 snapshot foundation（`snapshot_meta` + `data/snapshots/market-context/`）。

### 4.3 Adapter（F001）

- `FREDMarketLoader`：`https://api.stlouisfed.org/fred/series/observations?series_id={id}&api_key={FRED_API_KEY}&file_type=json`；解析 `observations[].{date,value}`；落 snapshot + repo.save_if_new。
- `AlphaVantageLoader`：免费 endpoint（`TIME_SERIES_DAILY` / `GLOBAL_QUOTE`，`apikey={ALPHAVANTAGE_API_KEY}`）；**注意 25 req/day 免费上限** → 每日只拉 3 series，cost_guard 复用。
- **live-validate（B031 教训）：** generator 各 live hit 一次真 FRED + 真 Alpha Vantage 验证 JSON envelope + 字段路径，写守门 unit test 锁字段；若 envelope 与假设不符即记 signoff §Framework Learnings（B031 候选二例评估）。

### 4.4 Scheduler（F002，§3 边界细分）

- `workbench_api/market/cli.py`：`fetch` 命令拉全 series → snapshot + DB（与 B033 news CLI 同构）。
- systemd timer `workbench-market-context.timer`（每日一次）+ `.service`（调用 `.venv/bin/python -m workbench_api.market.cli fetch`）。
- `deploy.sh` install timer + enable。
- **守门**：`test_market_scheduler_scope.py` AST 断言 cli/scheduler 路径不 import broker/ticket/execution/recommendation/llm 模块（边界 (r)）。

### 4.5 API + 前端（F003）

- `GET /market-context`（auth-gated, same-origin）→ `MarketContextResponse { series: [{series_id, source, latest_value, latest_date, label}] }`（每 series 最新值）。
- Home 页 market context 卡片：6 series 最新值 + 日期 + 来源标注（纯结构化、无 AI 文本）。

### 4.6 Fixture（CI 离线）

- `data/fixtures/` 内 fred-sample-*.json（3 series）+ alphavantage-sample-*.json（3 series）；CI 不打真 API。

### 4.7 安全 / regression test 矩阵

| 测试 | 守门 |
|---|---|
| `test_market_scheduler_scope.py` | scheduler/CLI 不 import 交易/ticket/recommendation/LLM（边界 (r)）|
| `test_runtime_dependencies_pinned.py`（扩集）| 若引入新 runtime dep 须 pin（§12.8）|
| `test_market_context_request_self_contained`（§12.10）| `/market-context` 请求路径不读 repo-root data/fixtures（数据入 workbench_api/ 或 DB）|
| secret grep | `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY` 值不泄漏；§12.9 四处接线齐 |

## 5. Feature 拆分

### F001 — Market context schema + 双 adapter + 2 secret 三处接线（generator，2-3 天）
schema + snapshot foundation 复用 + FREDMarketLoader + AlphaVantageLoader + alembic 0007 + repository + fixtures + 2 secret §12.9 四处接线 + live-validate + pytest。详见 features.json。

### F002 — Scheduler（每日只读拉取）+ CLI + 边界守门（generator，2 天）
market/cli.py + systemd timer/.service + deploy.sh install + 边界 (r) scope 守门 + pytest。详见 features.json。

### F003 — Home market context 卡片 + API（generator，2 天）
`GET /market-context` + 前端卡片 + vitest/Playwright。详见 features.json。

### F004 — Codex L1 + L2 真 VM 验收 + signoff（codex，1 天）
L1 全门禁 + 边界 (r) 守门 + L2（2 新 secret VM env / systemd timer 装好且 scope 只读 / 真 API live / alembic head=0007 / Home 卡片纯结构化 / HEAD≡main）。详见 features.json。

## 6. 不做的事（YAGNI）

- AI advisor / 把 market context 喂 AI（B036）。
- 把 market context 接入 quant 策略信号（超出 context 展示范围）。
- 盘中实时 / 高频（仅每日）。
- 付费数据源 / 第三方付费指数。
- in-process APScheduler（用 systemd timer 替代，避免新 runtime dep）。
- scheduler 做任何非「只读数据拉取」的事（边界 (r)）。

## 7. 验收门槛汇总

| 门禁 | 阈值 |
|---|---|
| backend pytest | F001 ≥ baseline+≥12 / F002 ≥ +≥8 / F003 ≥ +≥6（B034 收尾 baseline 646）|
| frontend | vitest ≥176（+卡片）/ Playwright ≥39（+卡片 e2e）/ lint 0 / typecheck pass |
| ruff / mypy | exit 0 |
| alembic | upgrade head（0007）+ downgrade 到 0006 可逆 |
| 安全守门 | §4.7 全过；边界 (r) scheduler scope；§12.10 请求路径自包含；2 secret §12.9 四处接线齐 |
| secret | `FRED_API_KEY` + `ALPHAVANTAGE_API_KEY` 四处接线（.env.example / config / deploy.sh / bootstrap-env.yml）|

## 8. 参考文档

- `docs/product/implementation-path-2026-05.md` §4 Phase 2 / Stream 2.C（B035 行）
- `docs/product/data-source-evaluation-2026-05.md` §5（FRED / Alpha Vantage 选型）
- `docs/specs/B027-real-data-snapshot-foundation-spec.md` + B029（snapshot foundation + adapter + secret pattern）
- framework v0.9.30 §12.9（secret 三处接线，本批次 2 新 secret）/ v0.9.32 §12.10（请求路径自包含）/ v0.9.29 §12.8（runtime dep）/ §12.7.1（paths-trigger）
- **B031 第三方 API live-validate 候选**（hold 中，本批次 FRED+Alpha Vantage 为复用窗口）

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Alpha Vantage 25 req/day 免费上限 | 每日只拉 3 series；cost_guard 复用 + fixture-first CI 不打真 API |
| FRED / Alpha Vantage envelope 与假设不符 | F001 live-validate 各一次锁字段 + 守门 test（B031 教训）|
| 引入 scheduler 与既有 no-scheduler 姿态冲突 | §3 边界 (r) 严格 scope 为只读数据拉取 + 守门测试 + systemd timer（非 in-process）+ News (q) 不变 |
| 2 新 secret 漏 bootstrap-env.yml | §12.9 四处接线 spec 硬列 + Planner pre-impl 审计 + Evaluator L2 验证 |
| 用户未及时申请 key | F001 spec 明列用户动作项；CI fixture-first 不阻塞开发，L2 真 VM 验收前用户须配齐 |

## 10. 与既有批次的边界

- **复用不改** B027/B029 snapshot foundation（`snapshot_meta` / `data/snapshots/` / cost_guard）/ 既有 loaders。
- **不动** B033 News（边界 (q) scheduler 禁令对 news 不变）/ B034 news_embedding / B031 LLMGateway / B032 workflow / B026 banner。
- **新增** market context 域 + 项目首个 systemd timer（边界 (r) 只读 scope）。

## 11. 后续批次（不在 B035 范围）

- **B036**（Stream 3.C）：AI advisor MVP —— 整合 quant signal + real data + B034 news + （可选）B035 market context → 生成式建议 + 引用 + `INSUFFICIENT_GROUNDING` + red-team 15 样本 = **🎯 里程碑 B Phase 2 终点**。
