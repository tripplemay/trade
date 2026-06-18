# B068 F001 — 宽 A股 universe 实建 runbook + §23 实测证据

**批次：** B068（A股 进攻策略 宽宇宙重验）F001。
**结论：** §23 = **GO**。宽宇宙在生产 VM 上**真建成功**（513 superset → top-250 PIT × 29 季度，0 fetch error，0 未来泄漏）。解 B066 P1 留白的数据前提（seed-43 全通质量门槛 → 无法分化 Q1；宽宇宙 250/期才有筛选空间）。

---

## 1. §23 端点可达性（VM `34.180.93.185` 实跑，2026-06-18）

`scripts/test/ashare_universe_probe.py --label vm`（`/opt/workbench/.venv/bin/python`）真返回：

| 候选端点 | host | 结果 |
|---|---|---|
| `stock_value_em(600519)` | eastmoney *finance* | ✅ 2051 行（PIT 市值源，B065 已用）|
| **`stock_zh_a_spot`（sina）** | sina | ✅ **5527 行全市场列表** → 宽 superset 列表端点 |
| `stock_zh_a_daily(sh600519, qfq)`（sina） | sina | ✅ 5943 行/票（含 `amount`+`outstanding_share`）→ **F003 价格源** |
| `stock_zh_a_spot_em` / `stock_sh_a_spot_em` / `stock_sz_a_spot_em` | eastmoney *push2* | ❌ ConnectionError |
| `stock_info_a_code_name` | szse.cn | ❌ Connection reset |
| `stock_zh_a_hist`（qfq） | eastmoney *push2his* | ❌ ConnectionError（本次；生产价格走 sina daily fallback，见 `cn_provider.py`）|

**要点：** eastmoney push hosts 在 VM 上全挂（B065 预言坐实）；**sina spot/daily 可达**——这是宽宇宙能建起来的关键。sina spot 无 `总市值`、`代码` 带交易所前缀（`sh600519`/`bj920000`），故按 `成交额` 排序界定候选池、`bj`（北交所）out-of-scope 剔除。

---

## 2. 设计（B067 零回归是硬约束）

- `discover_ashare_superset` 三级：eastmoney(`总市值`) → **sina(`成交额`)** → seed。
- **sina 分支 gated 于 `allow_sina_fallback`（默认 False）**：生产 daily refresh（`workbench-data-refresh.timer` 每日 02:30 UTC，调 `cli fetch` 不带 flag）行为**字节级不变** → VM 上 eastmoney 失败 → 降级 seed-43 → B067 实盘 advisory（03:30/03:40 timer）继续读 seed-43 宇宙。spec 不变量 #1「不改 B067 surface」守住。
  - 实测守门：`discover_ashare_superset(top_n=500)` → `provenance=seed, size=43`；`(…, allow_sina_fallback=True)` → `provenance=sina_spot, size=513`。
- 宽宇宙=**研究产物**，写研究 data root（**非**生产 `/var/lib/workbench/data`），F003 回测经 `run_cn_attack_backtest(universe_history=…)` 注入，永不进生产路径。
- PIT 排名（`point_in_time_top_n`）只用 `≤ as_of` 的市值 bar → 结构性无未来泄漏（单测 + §3 实测双证）。

---

## 3. 如何复跑（VM）

新代码已随 commit `d5a60c1` 部署到 VM（gated，生产安全）。研究构建脚本不随 backend 部署，需 scp：

```bash
# 在 VM 上（部署后 workbench_api 已含 sina 路径）
scp scripts/research/build_cn_wide_universe.py tripplezhou@34.180.93.185:/tmp/
ssh tripplezhou@34.180.93.185
cd /srv/workbench/current/backend   # workbench_api import 上下文
/opt/workbench/.venv/bin/python /tmp/build_cn_wide_universe.py \
  --out-dir ~/b068_out --superset-size 500 --top-n 250 --from-date 2019-01-01 \
  --out-json ~/b068_out/summary.json
```

> 本次首跑用 `/tmp/b068_run`（部署前隔离副本，避免改生产）。`--prices-path` 省略 → 宽名 `成交额` 维度=0、按市值排名（宽名价格 F003 才抓，诚实无泄漏）。

---

## 4. 实测结果（VM 真建，2026-06-18 17:31→18:0x）

`summary.json`（本地副本 `data/research/b068/f001_build_summary.json`）：

| 指标 | 值 |
|---|---|
| superset_provenance | **sina_spot** |
| superset_size | **513**（top 500 成交额 ∪ seed）|
| marketcap_symbols / rows | 513 / 808,034 |
| **fetch_errors** | **0** |
| rebalance_dates | **29**（2019-03-31 → 2026-03-31 季度）|
| **每期成员数** | **250（全 29 期均达 top_n）** |
| universe_rows | 7,250 |
| **distinct tickers（全期）** | **393**（>250 → 名单随期轮换）|

**PIT 无泄漏实测（real-data spot-check）：**
- 143 名在首期之后才进入；76 名「末期有、首期无」（成长进 top-250）。
- 42 名首现于 2023+（近年上市/上规模）。
- **LEAKAGE = 0**：这 42 名在 2019-2022 任一 rebalance **零出现** → 只用 `≤as_of` 数据坐实。

**为何解 Q1：** seed-43 全通质量门槛（无分化）→ 现 250/期、393 distinct 含质量参差的中大盘，质量门槛有筛选空间，质量+动量 vs 纯动量可分化。

**ST/退市/北交所：** 发现阶段按名称剔除 ST/退市、按前缀剔除 `bj`（北交所）。

---

## 5. 产物位置

- VM：`~/b068_out/snapshots/universe/{cn_pit_universe.csv, cn_marketcap.csv}` + `~/b068_out/summary.json`（tripplezhou 家目录，持久）。
- 本地（gitignored 数据）：`data/research/b068/{cn_pit_universe_wide.csv, f001_build_summary.json}`。
- §23 probe 输出：VM `/tmp/ashare_probe_vm.json`。

## 6. F003 衔接

- 宽名价格走 **sina `stock_zh_a_daily`**（§1 实测可达，含 `amount`/`outstanding_share`）；`cn_provider.py` 已有 eastmoney→sina→baostock fallback。
- F003 回测注入本宽 universe（`universe_history`），4 配置（2 因子×2 权重，退出固定 momentum_decay），walk-forward IS/OOS，全披露不 cherry-pick。
