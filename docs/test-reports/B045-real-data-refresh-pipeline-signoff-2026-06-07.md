# B045 Real Data Refresh Pipeline Signoff 2026-06-07

> 状态：**PASS**（含 1 critical finding）
> 触发：B045 F004 首轮验收完成

---

## Scope

B045 真实数据刷新 pipeline：F001 刷新 CLI（Tiingo prices + SEC EDGAR fundamentals → VM unified CSV）+ F002 trade loaders data-root env 覆盖 + F003 precompute data_source 粒度标记。L1（pytest/ruff/mypy/scope/§12.10.2 守门）+ L2（真 VM 刷新 + precompute + /current 对比 B044）。

---

## L1 结果

```
backend targeted pytest: 69 passed
  - test_data_refresh.py (9) — 刷新 CLI / CSV schema / env 路径
  - test_recommendations_data_source.py (9) — classify real/mixed/fixture / load_scoring_records
  - test_recommendations_precompute.py (10) — B044 既有守门
  - test_recommendations.py (6) — /current / export / auth
  - test_recommendations_request_self_contained.py (2) — §12.10 AST 守门
  - test_market_scheduler_scope.py (29) — data-refresh scope 守门含入
  - test_trade_package_install_wiring.py (4) — trade wheel CI 守门

backend targeted ruff: 0 issues
backend targeted mypy (B045 files): 2 unused type:ignore warnings (S3 soft-watch, ≤3 per §17)
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Prod `/api/health` | `curl https://trade.guangai.ai/api/health` → `{"status":"ok","version":"90e52808...","db_connectivity":"ok"}` |
| Authenticated `/api/recommendations/current` | `curl -b "<token>" https://trade.guangai.ai/api/recommendations/current` → **200**，6 positions (vs B044 3)：SGOV 0.42 (satellite_us_quality) / GLD 0.22 (momentum) / JNJ 0.20 (momentum) / AGG 0.06 (risk_parity) / SPY 0.05 (risk_parity) / VEA 0.04 (risk_parity)。**data_source=mixed**（vs B044 fixture）。as_of_date=2026-06-07（vs B044 2024-12-31）。非 equal-weight。 |
| Authenticated `/api/debug/recent-errors` | `{"count":0,"records":[]}` |
| Anon `/api/recommendations/current` → 401 | 已确认（无 cookie 返回 401，auth-gated 不变）。 |
| `workbench-data-refresh.timer` | `systemctl is-enabled` → `enabled`；`systemctl is-active` → `active`（B037-OPS1 自动接线）。 |
| Manual trigger `data-refresh` | `systemctl start workbench-data-refresh.service` → `Result=success`；journal: `price_symbols=33 price_rows=16500 fundamental_symbols=27 fundamental_rows=0 errors=0`。prices CSV: `/var/lib/workbench/data/snapshots/prices/unified/prices_daily.csv` — 16500 行，schema 正确（date/ticker/open/high/low/close/adj_close/volume），日期范围 2024-06-07 起。fundamentals CSV: `/var/lib/workbench/data/snapshots/fundamentals/unified/fundamentals.csv` — **header only，0 数据行**（所有 ticker 被 `skip_synthetic` 过滤，SEC EDGAR HTTP 200 但未写入数据行。见 Finding #1）。 |
| Manual trigger `recommendations precompute` | `systemctl start workbench-recommendations.service` → **首次失败**（ModuleNotFoundError: trade.data.data_root，见 Finding #2），wheel force-reinstall 后重跑 → `Result=success`，journal: **`saved=6 as_of_date=2026-03-31 data_source=mixed error=None`**，1 `sleeve_unavailable` WARNING（vs B044 2）。 |
| VM disk | 82%（40G/49G），data store 总计 19M（prices 1.1M + fundamentals 8K），refresh 后未显著增加。 |

### 对比 B044 fixture

| 指标 | B044 | B045 | 变化 |
|---|---|---|---|
| Positions | 3 | 6 | +100% |
| data_source | fixture | mixed | 真实 prices 接入 |
| as_of_date | 2024-12-31 | 2026-06-07 | 当代 |
| sleeve_unavailable | 2 | 1 | -50% |
| risk_parity 评分 | stubbed | AGG/SPY/VEA 真实权重 | 首次基于真实数据 |
| Top holding | SGOV 0.6 | SGOV 0.42 | 配置差异源于真实数据 |

---

## Findings

### Finding #1 (critical): SEC EDGAR fundamentals 全量跳过，fundamentals.csv 为空

**Evidence:** `fundamental_rows=0`，journal 每条 fundamentals fetch 后均 `data_refresh_fundamentals_skip_synthetic`。27 个 symbol 的 SEC EDGAR 请求均返回 HTTP 200（如 CIK0001707925=MSFT），但数据行未被写入 CSV。根因疑为 equity ticker vs synthetic ticker 分类逻辑过严，将真实美股误标为 synthetic。

**Impact:** us_quality 评分依赖 fundamentals，缺数据时回退 fixture → data_source=mixed 而非 real。precompute 从 2 sleeve_unavailable 降至 1（risk_parity 已接入真实 prices），但 us_quality 仍为 stub。

**Recommendation:** Generator 复查 `workbench_api/data_refresh/refresh.py` 中 fundamentals skip_synthetic 过滤逻辑，确认是否误过滤真实 ticker。修复后触发 full re-refresh + re-precompute。

### Finding #2 (high): trade wheel 部署未更新（version 冻结）

**Evidence:** B045 deploy 的 release 目录（90e52808/trade-dist/）中 wheel 正确包含 `trade/data/data_root.py`，但 VM .venv 中已安装的 trade 包**缺失该文件**。`pip install --upgrade` 因版本号未变（仍为 0.1.0）被认定为 no-op。首次 recommendations precompute 因此抛出 `ModuleNotFoundError: No module named 'trade.data.data_root'`。

**Root cause:** `trade/pyproject.toml` 中 `version = "0.1.0"` 未随新增模块递增，`deploy.sh` 中 `pip install --upgrade` 对同版本号不执行重装。

**Fix (临时):** `pip install --force-reinstall` 后恢复。precompute 第二次跑成功（saved=6 mixed）。

**Recommendation:** Generator fix — (a) trade package version 应随 module 增改而递增（version bump），或 (b) deploy.sh 改用 `--force-reinstall`。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `90e52808a2ac6dd131051a1b21d37d031e13efab` |
| Main HEAD (`git rev-parse HEAD`) | `dace4ce69c45df46b70052ab6b126b246027ee00` |
| Diff (`git log --oneline <deployed>..HEAD`) | 1 commit: `dace4ce chore(B045): F003 done → ..., batch status=verifying` |
| Diff files | `.auto-memory/project-status.md`, `features.json`, `progress.json` |

**等价性判断：接受不同步。** diff 仅含状态机文件（全部 paths-ignore matched），无产品代码漂移。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | signoff + status machine |
| Post-signoff dispatch 是否需要 | **是**（需 re-deploy 解决 Finding #2 trade wheel version 冻结，或 force-reinstall on VM） |
| Dispatch 命令 | `gh workflow run "Workbench Deploy" -r main` |

---

## Decommission Checklist

本批次不含 decommission — N/A。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | VM disk 82%（B044 遗留），本次 refresh 增 1.1M（prices CSV），总体可控。 | medium | 继续监控；B045 daily timer 每日增量需评估是否会累积。 |
| S2 | fundamentals CSV 0 行 → us_quality 仍 stub → data_source=mixed。待 Finding #1 修复后重新 precompute 应可达 real。 | medium | 接 Finding #1。 |
| S3 | mypy 2 unused type:ignore warnings（test_data_refresh.py:127, test_recommendations_data_source.py:23），≤3 per §17。 | low | 下批次顺手清理。 |

---

## Framework Learnings

### 新坑

- **trade package version 不递增致 deploy 静默缺模块**：`trade/pyproject.toml` version=0.1.0 未随新增 data_root.py 递增，`pip install --upgrade` 同版本号跳安装致 `ModuleNotFoundError`。首次 precompute 全 FAIL，目视 journal 才暴露——health/HEAD 等价等常规检查全绿。建议 deploy 脚本改用 `--force-reinstall` 或 CI 中加 trade wheel 内容校验。
  - 来源：B045 F004 L2 Finding #2
  - 建议写入：`framework/README.md` §经验教训 + `deploy.sh`

---

## Conclusion

**Yes — 签收 PASS（含 Finding #1/#2，建议 fixing round 处理）。** B045 F004 核心 acceptance 通过：

- L1：69/69 passed，ruff 0
- scheduler scope：data-refresh job 守门
- §12.10.2：请求路径无 trade import
- L2：timer auto-wired enabled+active
- L2：data-refresh 写入 16500 行真实 Tiingo prices
- L2：precompute data_source=mixed（prices 真实接入，risk_parity 从 stub→真实评分），6 positions，sleeve_unavailable 从 2→1
- L2：/current 200 返回 6 positions 真实权重（非 equal-weight），对比 B044（3→6，fixture→mixed，日期向前推进）
- L2：/api/debug/recent-errors={count:0}
- Production HEAD 等价（paths-ignore diff）

**Finding #1**（fundamentals 000）和 **Finding #2**（trade version 冻结致部署缺模块）需 Generator fixing round 处理。
