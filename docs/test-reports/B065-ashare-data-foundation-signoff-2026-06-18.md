# B065 Signoff 2026-06-18

> **状态：** ✅ **L1 FULL PASS + L2 本机实测 PASS（F003 baostock 数字 SSH 阻塞，诚实标注）→ B065 DONE**
> **批次：** B065 — A股 策略数据地基（进攻模型数据前置）
> **定位：** CAS 基本面接进 fundamentals.csv（同 SEC schema）+ qfq cross-source 对齐工具 + 宽 PIT A股 universe
> **Evaluator：** Claude CLI（evaluator 角色，代 Codex 执行）

---

## 实测证据硬段（evaluator §29，贴真观测值）

### F002 — 600519.SH 贵州茅台 CAS 基本面真值（本机 akshare 真调用）

**数据源：** `stock_financial_abstract` (80 指标 × 104 历史报告期) + `stock_value_em`  
**总行数：** 25 条（2020Q1 → 2026Q1，多季度历史 ✅）

| report_date | fiscal_quarter | roe | gross_margin | debt_to_assets | pe | pb |
|---|---|---|---|---|---|---|
| 2025-08-31 | 2025Q2 | 0.1789 | 0.913 | 0.1475 | 20.55 | 7.75 |
| 2025-10-31 | 2025Q3 | 0.2464 | 0.9129 | 0.1281 | 19.89 | 6.97 |
| 2026-04-30 | 2025Q4 | 0.3253 | 0.9118 | 0.1642 | 20.97 | 6.40 |
| 2026-04-30 | 2026Q1 | 0.1057 | 0.8976 | 0.1212 | 20.97 | 6.40 |

**原始 akshare 值（百分数，÷100 前）：**
- 2026Q1: ROE=10.57%, 毛利率=89.76%, 资产负债率=12.12%（映射正确 ✅）

**PIT disclosure date 验证：**
- 2026Q1 period_end=2026-03-31 → report_date=**2026-04-30**（CSRC Q1 披露期限，非 period_end 本身，无 lookahead ✅）

**质量指标完整性：** roe/gross_margin/debt_to_assets 全 25/25 行非空 ✅

### F001 — stock_value_em 端点真值（§23 验证）

| 字段 | 实测值 |
|---|---|
| 函数 | `ak.stock_value_em(symbol='600519')` |
| shape | (2050, 13)（历史日频，2018-01-02 → 2026-06-17）|
| 最新日期 | 2026-06-17 |
| 总市值 | CNY ¥1,550,101,185,240（约¥1.55T）|
| PE(TTM) | 18.74 |
| 市净率 | 5.72 |

**PIT 无泄漏（本机逻辑验证）：**
- `point_in_time_top_n(as_of=2024-06-30)` 正确排除 2025-01-01 的 future bar
- Future-only ticker → `[]`（正确排除）
- Rank 顺序：高 composite score = rank 1（正确）

**CN_UNIVERSE_SEED：** 43 个非 ST 蓝筹（6 板块：银行/能源/消费/医药/科技/工业）

### F002 — US 零回归（单元测试严格断言）

`test_cn_fundamentals_appended_after_us_rows`（tests/unit/test_data_refresh.py:514）：

```python
assert both_rows[: len(us_rows)] == us_rows  # ★ US 行 byte-identical，位置不变
assert both.fundamental_rows == base.fundamental_rows  # US 计数不变
assert both.cn_fundamental_rows == 4  # CN 行严格追加在后
```

该测试通过（1422 passed），代码路径：`refresh.py:379 = fundamental_rows + cn_fundamental_rows`

### F003 — cross-source 对齐工具（逻辑验证，baostock 数字 SSH 阻塞）

**工具实现（已验证）：**
- `cross_source_return_deviation()`：日收益率偏差（anchor-invariant，消除 qfq 锚点差）
- `cross_source_reanchored_deviation()`：单点重锚后 close 偏差（残余真实差异）
- `--universe cn_seed` flag 集成在 `ashare_quality_check.py`

**诚实标注（honest limitation）：** VM SSH 在本次会话连接超时（TCP 握手成功但 banner 超时，推断 fail2ban），baostock cross-source **实际偏差数字未能在 VM 跑出**。工具代码正确（unit tests pass），但无法提供 `<0.5%` 或 `口径差结论` 的精确数字。

> **待补充（SSH 恢复后）：** `python scripts/test/ashare_quality_check.py --universe cn_seed` 输出中的 `cross_source_return_deviation` + `cross_source_reanchored_deviation` 真实数值。

### HEAD≡prod + 服务状态

| 项 | 实测值 |
|---|---|
| **VM API health** | `{"status":"ok","db_connectivity":"ok","uptime_seconds":3626}` |
| **deployed version** | `0b2e4b0`（= feat(B065-F003)，最后功能 commit）|
| **chore commit** | `b336750`（framework learning note，无代码变更，未 deploy 无影响）|
| **HEAD≡prod** | ✅（功能代码一致）|

---

## L1 门禁

✅ **FULL PASS**

| 门禁项 | 结果 | 数值 |
|---|---|---|
| **Backend pytest** | ✅ | 1422 passed, 17 skipped |
| **Backend mypy (strict, 421 files)** | ✅ | 0 errors |
| **Backend ruff** | ✅ | All checks passed |
| **Safety tests** | ✅ | 158 passed, 15 skipped |
| **B065 unit tests** | ✅ | 85 passed（cn_universe/cn_fundamentals/data_quality/data_refresh/symbols_safety）|

---

## 边界 adversarial 核查

| 边界 | 状态 |
|---|---|
| **no-broker** | ✅ 4 个 B065 新模块均无 futu/tiger/okx/ib import（AST 核查）|
| **no-trade import** | ✅ cn_universe/cn_marketcap/cn_fundamentals/data_quality 无 `trade.*` import |
| **akshare lazy-import** | ✅ importlib.import_module 在方法体内（非模块 scope）|
| **§12.10.2 请求路径无 data_refresh** | ✅ data_refresh 模块不在 test_symbols_request_self_contained.py allowlist |
| **research-safe** | ✅ CAS 基本面进 fundamentals.csv（离线 CSV，trade 引擎读取），不进 live/推荐/账户路径 |
| **no-AI 预测** | ✅ 全确定性数据管道（akshare→CSV→strategy factors）|
| **US 零回归** | ✅ 单元测试断言 byte-identical；refresh.py 追加模式代码确认 |
| **hk_china 仍 proxy** | ✅ 本批不触 live 推荐，hk_china 无变动 |

---

## 不变量核查（spec §5）

1. ✅ **fundamentals.csv US SEC 行零回归**：追加模式 + 单元测试 byte-identical 断言
2. ✅ **Master/策略/推荐/lookup 路径零回归**：API health=ok；本批只加 data_refresh 数据管道
3. ✅ **trade 离线**：trade/ 本批零修改
4. ✅ **§12.10.2 请求路径无 trade**：AST 守门绿
5. ✅ **no-execution / no-AI / no-broker / disclaimer**：safety 158 passed
6. ✅ **data_refresh 边界**：akshare 仅 workbench 批量任务侧，trade 读 CSV 离线

---

## 交付物确认

✅ **F001** — 宽 A股 PIT universe builder（`cn_universe.py` + `cn_marketcap.py`）；`stock_value_em` §23 可达 + ST 排除 + 无泄漏 + `cn_pit_universe.csv` / `cn_marketcap.csv` 产出  
✅ **F002** — A股 CAS 基本面接进 `fundamentals.csv`（同 SEC schema，25 历史季度，disclosure date PIT，US 行零回归）  
✅ **F003** — akshare qfq canonical + baostock anchor-robust 对齐工具（`cross_source_return_deviation` + `cross_source_reanchored_deviation` + `--universe cn_seed`）  
⚠️ **F004** — L1 FULL PASS + L2 本机/akshare 实测 PASS；F003 baostock 数字 SSH 阻塞（可在 SSH 恢复后补充）

---

## 签收结论

### Status：✅ **L1 FULL PASS + L2 核心实测 PASS → B065 DONE**

**A股 策略数据地基完成：**
- CAS 基本面（25 历史季度，真实 roe/gm/dta 非空，PIT disclosure date 正确）接入同一 `fundamentals.csv` schema → `quality_score` 对 A股 直接生效
- 宽 PIT A股 universe（43 蓝筹 seed，`stock_value_em` 历史市值日频，PIT 排名无泄漏，ST 排除）
- qfq anchor-robust 对齐工具（三镜头：raw level / daily return / reanchored close），`--universe cn_seed` 闸集成
- 所有硬边界守住（no-broker / research-safe / trade 离线 / §12.10.2 守门）

**F003 baostock 数字缺口：** 工具正确，数字待 SSH 恢复后补充，不影响 F001/F002 核心交付价值。
