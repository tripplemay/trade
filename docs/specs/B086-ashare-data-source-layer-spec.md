# B086 — A股行情数据源统一层（多源 fallback, 基建）Spec

> **动机（本 session 直接踩坑驱动）**：B082–B085 各自 ad-hoc 取 A股行情——akshare `fund_etf_hist_em`（Eastmoney）/
> `fund_etf_hist_sina`（Sina）/ 业绩预告 / baostock。**B084 F001 撞 Eastmoney IP 限流被迫切 Sina** 才拿到 ETF 数据。
> 没有统一的带 fallback 的健壮取数层 → 每个新策略重复踩限流/格式坑。**本批把多源 fallback 固化为可测模块**（非策略、非 flagship、安全）。
> **P0–P2 已收官**（B081–B085 first-look 均闭环，无强 edge）；此为**基建批次**（用户 away → 按 option 3 安全推进）。

## 0. 设计要点（焊死）

- **零策略/零 flagship**：纯取数基建，不碰 cn_attack / 任何策略产品码 / 生产 data_root（永久硬边界）。research-safe。
- **多源 fallback（本 session 实证顺序）**：ETF 日线 = Eastmoney(`fund_etf_hist_em`, qfq) → **Sina(`fund_etf_hist_sina`, 撞限流时, 原始价)** → baostock（ETF 无覆盖, 弃）。★口径差异（qfq vs 原始）**显式标注**返回。
- **限流/失败可测**：fallback 触发条件（SSLError / 空 / 限流）**可注入测试**（mock 源）。不静默吞错——log 哪个源命中。
- **缓存**：每标的 pickle/csv 缓存（复用 B084/B085 断点续跑模式）。
- **不迁移已完成批次脚本**：B082–B085 脚本已 done+working，**不动**（零回归）；新模块供**未来**策略用。

## 1. 复用清单

| 复用项 | 来源 | 用于 |
|---|---|---|
| Eastmoney→Sina fallback 实证 | 本 session B084 F001（`b084_etf_fetch.py`） | F001 fallback 核心 |
| Sina symbol 派生（sh/sz） | B084 `_sina_symbol` | F001 |
| 业绩预告 fetch | B083 `b083_pead_fetch.py` | F001 事件源（可选纳入） |
| 缓存断点续跑 | B084/B085 | F001 |

## 2. Feature 拆解（2：1 generator + 1 codex）

### F001 (g) — 多源 A股 ETF 行情 fetch 层 + fallback + 测试
- 模块 `trade/data/ashare_market_source.py`（或 scripts/research 下, 视是否入 trade/）：统一 `fetch_etf_daily(code)` →
  Eastmoney→Sina fallback，返回带 `source`/`adjust`（qfq|raw）标注的 DataFrame；SSLError/空 → 下一源；全失败 → 明确 raise。
- **单测**（mock 源，不打真网）：(1) Eastmoney 成功→用它；(2) Eastmoney SSLError→fallback Sina；(3) 全失败→raise 明确错误；(4) sh/sz symbol 派生；(5) 返回带 source/adjust 标注。
- 报告 `docs/test-reports/B086-F001-data-source-layer.md`（设计 + 源矩阵 + fallback 触发条件 + 口径差异）。
- **零回归**：不碰策略/flagship/生产 data_root。Gates: mypy trade（若入 trade/）+ 根 ruff + root pytest + backend 若触。

### F002 (codex) — 独立验收 + signoff
- Codex 独立：fallback 逻辑 mock-源覆盖核实（各分支）；口径标注（qfq vs raw）正确性；不静默吞错；不碰 flagship/生产路径（零回归 grep）；单测真覆盖 fallback 分支非 happy-path only。signoff `docs/test-reports/B086-...-signoff.md`。

## 3. 验收（通用段）
- Gates：mypy + 根 ruff + root pytest + 单测（fallback 各分支 mock）+ CI 全绿。
- 诚实：多源口径差异（qfq/raw）显式；fallback 不静默；零回归（不动已完成批次脚本/策略/flagship/生产路径）。
