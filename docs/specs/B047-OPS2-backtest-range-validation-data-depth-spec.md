# B047-OPS2 — 回测页生产 hotfix（有效默认范围 + 数据窗口暴露/钳制 + 友好错误 + 深化回填）

> **状态：** planning（2026-06-09 起草）。
> **批次类型：** 生产 hotfix（用户实际运行回测撞错）。**优先于 B049/B043**（里程碑 C 收尾决定暂搁）。
> **来源：** 用户 2026-06-09 报生产故障——回测页 Run 报 `BacktestWorkerError: insufficient price history for any signal date in range: no valid volatility estimates for risk assets`。Planner 根因分析（铁律 9 流程）。
> **配套：** B047 signoff（async 回测）+ B048 S1（数据深度 soft-watch）。

---

## 1. 根因（Planner 已确证）

| # | 因子 | 证据 |
|---|---|---|
| 1 | **回测页默认范围硬编码且已陈旧** | `backtest/page.tsx:93-94` 写死 `startDate=2024-01-01 / endDate=2024-06-30`。今天 2026-06，B045 数据是**滚动 2 年窗口**（每天重写 CSV=today−730 天≈2024-06 至今）→ 默认范围几乎整段早于数据起点 → **任何用户用默认范围点 Run 必然失败（开箱即坏）** |
| 2 | **risk_parity 需 120 交易日波动率 lookback** | `risk_parity.py:34 volatility_lookback=120`；`:155 len(returns)<lookback→RiskParityDataError`；全 risk 资产失败→`:206 no valid volatility estimates`。momentum 另需 ~9 月窗口（更长，binding） |
| 3 | **可用回测带 = 数据起点 + ~9-10 月** | worker `run_backtest_job` 丢最早信号日重试到剩 1 仍失败→`insufficient price history for any signal date in range`。2 年窗口下实际仅最近 ~1.3 年信号日可用 |
| 4 | **无校验/钳制 + 原始错误漏 UI** | 页面放任选任意日期不显数据覆盖；F003 graceful 仅把英文异常文本显出，用户看不懂 |

---

## 2. 决策（2026-06-09 用户拍板：前三层 + 深化回填，全四层）

| 层 | 修什么 |
|---|---|
| **L1 动态有效默认** | 去硬编码 2024 H1，默认范围从数据窗口动态算（落在可用带内），保证默认 Run 成功 |
| **L2 数据窗口暴露+钳制** | API 暴露数据覆盖区间（data_start/data_end + min_usable_start）；前端 date picker 钳制 + 显「数据覆盖 X–Y」 |
| **L3 友好错误** | worker 结构化 error-kind（insufficient_history 等）→ 前端 i18n 双语友好提示，不漏原始异常 |
| **L4 深化数据回填** | `DEFAULT_LOOKBACK_DAYS` 730→1825（~5 年）+ VM 一次性深回填，扩大可用带（顺带治 B048 S1 退化曲线） |

---

## 3. 永久硬边界（继承）

- §12.10.2 请求路径禁 import trade（数据窗口走 job→持久化→请求只读；worker/canonical/data-refresh allowlist）；定位 §1.1 回测=历史非预测；no-execution；边界 (r) 数据只读；i18n 双语。

---

## 4. 技术方案

### 4.1 L4 深化回填（F001）

- `data_refresh/cli.py` `DEFAULT_LOOKBACK_DAYS` 730→**1825**（~5 年；注释更新：覆盖 momentum 9 月 + risk_parity 120 日 vol + 给用户多年可用带）。daily timer 下次运行重写 CSV 为 5 年窗口。
- disk 影响小（730 天≈16500 行/1.1MB → 5 年≈2.5x ≈ 2.7MB；disk 84% 可容）。
- F003/Codex 触发一次 data-refresh（`systemctl start workbench-data-refresh.service` 或等 02:30 timer）落 5 年数据。

### 4.2 L2 数据窗口暴露（F001）

- **data-refresh job 写实际覆盖窗口**：写完 prices CSV 后，记录实际 `data_start`（CSV 最早日）/`data_end`（最晚日）+ **`first_usable_signal_date`**（覆盖最长 lookback 后第一个可跑信号日）到持久化（DB 小表 `backtest_data_window` 或等价）。**first_usable_signal_date 由 job 侧算**（data-refresh 可 import trade，或用文档化保守常数 data_start + ~10 月覆盖 momentum 9 月+buffer）——planner 留给 generator 定精确机制（job 侧精确 vs 常数保守）。
- **请求路径 API**：`GET /api/backtests/data-range`（或并入既有 strategies/meta 端点）返回 `{data_start, data_end, min_usable_start}`，**只读持久化不 import trade**（§12.10.2）。无数据时 graceful（返回 null/空，前端提示「暂无回测数据」）。

### 4.3 L1 动态默认 + L2 钳制（F002，前端）

- 去 `useState("2024-01-01")/("2024-06-30")` 硬编码；启动 fetch data-range → **默认 `end=data_end`，`start=max(min_usable_start, data_end−1 年)`**（保证落可用带）。data-range 未就绪前禁用 Run 或显 loading。
- date picker `min={min_usable_start} max={data_end}`（HTML `min`/`max` 属性 + 提交前校验）；显「数据覆盖 {data_start}–{data_end}」说明文字（双语）。

### 4.4 L3 友好错误（F002 前端 + F001 worker error-kind）

- worker/服务把 `insufficient price history` / `no valid volatility estimates` / `no quarter-end signal dates` 等映射为**结构化 error-kind**（如 `insufficient_history` / `no_signal_dates`），存 backtest_run.error（或新 error_kind 字段）。
- 前端按 error-kind i18n 双语映射（如「所选范围历史数据不足以估算波动率，请选择 {min_usable_start} 之后的范围」/ "The selected range lacks enough price history…"），不显原始英文异常。

### 4.5 测试（各 F）

- backend：data-refresh 写覆盖窗口（min/max/first_usable）+ data-range API（有数据/空）+ worker error-kind 映射（三类错误→kind）+ §12.10.2 守门（请求路径无 trade）+ cli DEFAULT_LOOKBACK_DAYS=1825。
- 前端：动态默认范围（mock data-range→默认落可用带）+ picker 钳制 + error-kind→双语文案 + 空数据态；vitest + Playwright（默认范围可 Run / 无效范围友好提示 / 双 locale）。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 后端——L4 深化回填(cli 730→1825) + L2 data-refresh 写覆盖窗口(data_start/end/first_usable) + GET /api/backtests/data-range(请求路径只读) + L3 worker 结构化 error-kind + §12.10.2 守门 + 测试 |
| F002 | generator | 前端——L1 动态有效默认范围(去硬编码 2024 H1) + L2 date picker 钳制+「数据覆盖 X–Y」 + L3 error-kind→i18n 双语友好提示 + 空数据态 + vitest/Playwright |
| F003 | codex | L1+L2 真 VM——深回填落 5 年数据 + data-range API 返窗口 + **默认范围 Run 成功且非退化结果** + 无效范围友好提示(非原始异常) + picker 钳制 + B023 不破 + signoff |

---

## 6. 不做的事（YAGNI）

- 不改 risk_parity/momentum lookback 算法或 master 评分。
- 不做参数扫描/优化器。
- 不改 §12.10.2 / async worker 架构 / canonical 报告逻辑。
- 不无限深回填（5 年够用户多年可用带；非全历史）。

---

## 7. 验收门槛汇总

- **F001**：cli DEFAULT_LOOKBACK_DAYS=1825；data-refresh 写 data_start/data_end/first_usable_signal_date 持久化；GET /api/backtests/data-range 返窗口（请求路径无 trade，§12.10.2 守门绿）；worker 三类错误→结构化 error-kind；backend pytest ≥ baseline+≥6 / ruff 0 / mypy 0 / alembic head（若加表）。
- **F002**：去硬编码默认；动态默认范围落可用带（mock data-range 测）；picker 钳制 min/max + 「数据覆盖」双语；error-kind→双语友好提示（不漏原始异常）；空数据态；frontend vitest ≥ baseline+ / lint / typecheck / Playwright（默认可 Run + 无效友好 + 双 locale）。
- **F003**：L2 真 VM——(1) data-refresh 深回填后数据≥~5 年（或 Tiingo 可达最长）；(2) GET /api/backtests/data-range 返合理窗口；(3) **默认范围点 Run→真实非退化结果**（equity 点数 >> 2，sharpe/maxdd 非 0）；(4) 无效范围（如早于 min_usable_start）→**中文友好提示非原始 BacktestWorkerError 串**；(5) picker 钳制生效；(6) B023 不破 + recent-errors=0 + HEAD≡main。Signoff（§Production/HEAD + §Post-signoff Deploy + **开箱即坏修复证据=默认范围 Run 成功 + 友好错误对比**）。

---

## 8. 参考文档

- 根因：`backtest/page.tsx:93-94`（硬编码默认）+ `data_refresh/cli.py:24 DEFAULT_LOOKBACK_DAYS=730` + `risk_parity.py:34/155/206`（120 lookback）+ `backtests/worker.py:182-193`（drop-earliest 重试→报错）
- §12.10.2 守门 `tests/safety/test_backtests_request_self_contained.py`；data-refresh `refresh.py`/`cli.py`；B048 S1 数据深度 soft-watch

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Tiingo 不一定有全 5 年（某些 symbol/proxy）| best-effort 每 symbol（refresh 已 try/except）；data_start 取实际最早；first_usable 据实算 |
| first_usable 计算需 trade 知识（请求路径禁 import）| job 侧算（data-refresh allowlist）或文档化保守常数（data_start+~10 月）；planner 留 generator 定 |
| 深回填 disk（84%）| 5 年 CSV ~2.7MB 可容；F003 验 disk |
| 一次性深回填未触发 | F003 手动 trigger data-refresh 或确认 timer 跑过 |

---

## 10. 与既有批次边界 + 后续

- **不改**：master 评分 / async 架构 / canonical 逻辑 / risk_parity 算法。
- **修复**：回测页开箱即坏 + 数据深度（顺带治 B048 S1 退化曲线）。
- **后续**：B047-OPS2 done 后回到里程碑 C 收尾（B049 全页面审计 / B043 AI 解释，用户先讨论的决定继续）。
