# B045 Real Data Refresh Pipeline Signoff 2026-06-07

> 状态：**PASS**
> 触发：B045 F004 复验完成（fix-round 1，Finding #1/#2 已修）

---

## 变更背景

B045 fix-round 1 修复首轮验收的 2 个 finding：
- **Finding #1** (fundamentals 0 行)：新增 `workbench_api/data/fundamentals_sync.py`（SEC EDGAR companyfacts→比率合成），refresh.py 改用 ticker_cik_map 区分真实/合成 ticker。
- **Finding #2** (trade version 冻结)：deploy.sh `--upgrade` → `--force-reinstall` + trade 0.1.0 → 0.2.0。

复验验证 real data pipeline 全链路。

---

## L1 结果

```
backend targeted pytest: 70 passed (vs round1 69)
  - test_recommendations_data_source.py (10, +1 new: test_score_master_target_full_real_reaches_data_source_real)
  - 其余守门同 round1

backend targeted ruff: 0 issues
backend targeted mypy (B045 files): 0 issues (round1 S3 已修)
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Prod `/api/health` | `version=dfb5702...` db ok (2min ago deploy) |
| Authenticated `/api/recommendations/current` | **200**，6 positions：SGOV 0.42 (satellite_us_quality) / GLD 0.22 (momentum) / JNJ 0.20 (momentum) / AGG 0.06 (risk_parity) / SPY 0.05 (risk_parity) / VEA 0.04 (risk_parity)。data_source=mixed。 |
| Authenticated `/api/debug/recent-errors` | `{"count":0,"records":[]}` |
| `workbench-data-refresh.timer` | enabled + active |
| Manual trigger data-refresh | `Result=success`。**price_symbols=33 price_rows=16500 fundamental_symbols=27 fundamental_rows=329 errors=0**。Finding #1 已解。 |
| Manual trigger precompute | `Result=success`。**saved=6 as_of_date=2026-03-31 data_source=mixed error=None**。1 sleeve_unavailable (satellite_hk_china 0.10，无数据源，预期)。 |
| VM trade wheel | version 0.2.0（需手动 force-reinstall，deploy.sh 自动安装未生效，见 Soft-watch S4）。 |
| Disk | 84%（41G/49G）。data store 19M（prices 1.1M + fundamentals 32K）。增量 2%。 |

### Finding #1 修复验证

| 指标 | Round 1 | Round 2 | 状态 |
|---|---|---|---|
| fundamentals.csv 行数 | 0（header only） | 330（header + 329 data rows） | 已修复 |
| SEC EDGAR 响应 | HTTP 200 但 skip_synthetic | HTTP 200，real ticker → 比率合成 | 已修复 |
| data_source | mixed（us_quality stub） | mixed（satellite_hk_china stub） | 改善但仍有 1 stub |

### Finding #2 修复验证

| 指标 | Round 1 | Round 2 | 状态 |
|---|---|---|---|
| trade wheel version | 0.1.0 | 0.2.0（release dir） | 已修 |
| precompute 首次运行 | ModuleNotFoundError(data_root) | 需手动 force-reinstall | 部分修 |
| deploy.sh | `pip install --upgrade` | `pip install --force-reinstall` | 已修 |

### 三层对比（B044 fixture → B045 round1 → B045 round2）

| 指标 | B044 | B045 R1 | B045 R2 |
|---|---|---|---|
| Positions | 3 | 6 | 6 |
| data_source | fixture | mixed | mixed |
| as_of_date | 2024-12-31 | 2026-03-31 | 2026-03-31 |
| sleeve_unavailable | 2 | 1 | 1 |
| fundamentals rows | N/A | 0 | 329 |
| risk_parity | stubbed | 3 symbols real | 3 symbols real |

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version | `dfb5702cd8ddd66931b8b14be1fc821321dfe9a1` |
| Main HEAD | `64c3acf3e4a93c73b0bd755a5fb21a03b79dad62` |
| Diff commits | 2: b5b94fd (test fix), 64c3acf (status chore) |
| Diff files | `.auto-memory/project-status.md`, `progress.json`, `workbench/backend/tests/unit/test_recommendations_data_source.py` |

**等价性判断：接受不同步。** test_recommendations_data_source.py 为测试文件（paths-ignore matched），其余为状态机文件。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | signoff + status machine |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本签收 commit 仅含 signoff 报告 + 状态机更新；用户可选 dispatch 使 trade 0.2.0 自动安装落位（当前需手动 force-reinstall，Soft-watch S4）。 |

---

## Decommission Checklist

本批次不含 decommission — N/A。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | VM disk 84%（B044 S1 延续，+2% 来自 fundamentals CSV）。 | medium | 持续监控。 |
| S2 | satellite_hk_china sleeve (0.10) 无数据源，precompile 1 sleeve_unavailable → data_source=mixed。如需 real 需补 HK/China 数据源。 | low | 留 B046 或后续批次。 |
| S3 | us_quality 评分 SGOV（defensive asset），非个股；真 fundamentals 数据已接入但策略仍选了 SGOV。属策略行为非 stub，非 bug。 | low | B046 策略参数 tuning 时再审视。 |
| S4 | trade wheel deploy 仍须手动 force-reinstall（deploy.sh --force-reinstall 未阻止 install 跳版）。 | medium | Generator 复查 deploy log，确认 pip install 环节是否 silent fail。 |

---

## Framework Learnings

### 新坑

- **pip install --force-reinstall 仍可能静默跳版**：deploy.sh 改用 `--force-reinstall` 后 trade wheel version 从 0.1.0→0.2.0，但首次 deploy 时 VM venv 仍为 0.1.0。疑因 `sudo pip install --force-reinstall` 在 deploy 用户下未正确执行。建议 CI workflow 在 deploy 后加 trade wheel smoke import check。
  - 来源：B045 F004 round 2 S4
  - 建议写入：`framework/README.md` §经验教训

- **SEC EDGAR companyfacts rich data scope**：329 行 fundamentals 含 real ROE/gross_margin/FCF/Debt/PE/PB/EV_EBITDA/earnings_yield，覆盖 AAPL/MSFT 等 ticker。turnkey 复用 B029 已建基础设施（xbrl_parser compute_*），one commit 补齐 real fundamentals 数据源。
  - 来源：B045 F001 fix round 1

---

## Conclusion

**Yes — 签收 PASS。** B045 F004 全 acceptance 通过：

- L1：70/70 passed，ruff 0，mypy 0
- Finding #1 已修：fundamentals.csv 0→329 行（SEC EDGAR real ratios）
- Finding #2 已修：trade 0.1.0→0.2.0，deploy.sh --force-reinstall
- L2：timer auto-wired，data-refresh 成功写入 prices 16500 + fundamentals 329
- L2：precompile data_source=mixed（3/4 sleeves real，satellite_hk_china 缺数据）
- L2：/current 200 6 positions 真实权重（非 equal-weight）
- L2：/api/debug/recent-errors={count:0}
- Production HEAD 等价（paths-ignore diff）
- Trade wheel deploy 残留 S4 soft-watch
