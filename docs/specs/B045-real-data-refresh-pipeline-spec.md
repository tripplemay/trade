# B045 — 真实数据刷新 pipeline（live-refresh → data_source=real）

> **状态：** planning（2026-06-07 起草）。
> **批次类型：** 新功能 / 数据工程（**真实数据刷新 pipeline**；B044 真实评分基础的 Batch 2 拆分后的数据线）。
> **来源/动因：** B044 signoff §Soft-watch S2/S3——precompute 在 VM `data_source=fixture`（risk_parity 需 120+ 日频、us_quality 需 fundamentals，均不在 wheel → stub）。用户批 Option C：真 live-refresh pipeline（非静态快照）。
> **拆分说明：** 用户选 C 后体量升级为数据工程批次，故本批=数据 pipeline；**regime reconcile + account current_weight（Threads 2/3，小）拆出到 B046**。

---

## 1. 目标

建立**真实数据刷新 pipeline**，让 B044 precompute 在 VM 上对**全部 sleeve 跑真实数据评分**（`data_source=real`），消除 S2/S3 的 fixture stub。

- **prices**：B027 Tiingo loader 抓真实日频（满足 risk_parity 120+ 日频 + global_etf_momentum）。
- **fundamentals**：B029 SEC EDGAR loader `fetch_quarterly_fundamentals` 抓真实季度财报（满足 us_quality 5 因子）。
- 刷新 job（timer，边界 r）→ 写 unified 数据到 VM 可读 store → trade loaders 读真实数据 → precompute 全 sleeve real。

---

## 2. 决策（2026-06-07 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 真数据路径 | ★ **C：live-refresh pipeline** | 非静态快照；定期刷新与市场同步 |
| 拆分 | **B045=pipeline；B046=regime+current_weight**（planner 决） | C 升级体量，小 wire-up 拆出避免 scope creep |
| 数据 store | **VM 文件 `/var/lib/workbench/data/snapshots/unified/`**（planner 决） | trade loaders 读 CSV 路径；文件 store 最贴合既有 loader 期望；镜像 market-context/news 已 provision 的 snapshot 目录 |
| 数据源 | **prices=Tiingo(B027) / fundamentals=SEC EDGAR(B029)**（planner 决） | 两真实源已存在，复用 |
| 刷新 cadence | **每日 timer（边界 r）**（planner 决） | 季度调仓只需定期；每日 cheap（复用 Tiingo budget guard + EDGAR rate limit）|

---

## 3. 永久硬边界（继承 + 本批修订）

- **边界 (r)**：刷新 job 是只读市场数据拉取（prices/fundamentals）→ 收编入 (r)；NOT 交易执行。scope 守门扩刷新 job。
- **§12.10 / §12.10.1 / §12.10.2**：刷新 job + precompute import trade/（job 非请求路径，B044 §12.10.2 AST 守门已立请求路径禁 trade）；刷新 job 写 **VM data dir（非 repo-root）**，自包含。
- **§12.10 数据自包含**：trade loaders 现读 `_REPO_ROOT/data/snapshots/unified/*.csv`（VM 上 repo-root 不存在）→ 本批加 **data-root env 覆盖**让 loaders 读 VM store（F002）。
- 定位 §1.1：真实数据=历史/季度财报真值，评分仍是配置权重非收益预测。
- secret：复用 TIINGO_API_KEY + SEC_EDGAR_CONTACT_EMAIL（VM env 已配），不引新 secret。

---

## 4. 技术架构

### 4.1 刷新 job + timer（F001）

- `workbench_api/data_refresh/`（或复用既有 prices/news 模块风格）：刷新 CLI 抓真实 prices（Tiingo，深历史满足 120+ 日频）+ fundamentals（SEC EDGAR `fetch_quarterly_fundamentals`）→ 写 unified CSV（schema 同 trade loaders 期望：prices_daily.csv + fundamentals.csv）到 `/var/lib/workbench/data/snapshots/unified/`。
- universe = master portfolio 各 sleeve 所需 symbol（risk_parity 5 ETF + us_quality universe + global_etf_momentum ETF）。
- `deploy/systemd/workbench-data-refresh.{service,timer}`（每日 oneshot；B037-OPS1 循环+通配符零成本自动接线）。
- 复用 B027 request_spacing/budget guard + B029 rate limit。

### 4.2 loader data-root 覆盖（F002）

- trade loaders（`trade/data/loader.py` / `us_quality_universe.py`）读 unified CSV 的路径加 **env 覆盖**（如 `WORKBENCH_DATA_ROOT`）：env 设则读该 root 下 `snapshots/unified/`，否则保持现有 repo-root 行为（本地/CI 不变）。
- precompute（B044）+ 刷新 job 设该 env 指向 VM store → loaders 读真实数据。
- 既有 fixture fallback 保留（数据缺→fixture + data_source 标记）。

### 4.3 precompute data_source 真实标记（F003）

- B044 precompute 现 `data_source=fixture` 硬标记 → 改为**按实际数据源粒度标记**：prices/fundamentals 各 sleeve 实际读到 real 还是 fixture/fallback；全 real → `data_source=real`；部分 → 标记 mixed + 明细（v0.9.21 诚实，不蒙混）。
- 数据齐时 risk_parity/us_quality 不再 `sleeve_unavailable`（S3 消失）。

### 4.4 测试

- pytest：刷新 job（fake Tiingo/EDGAR → 写 unified CSV 正确 schema）；loader data-root env 覆盖（env 设→读 VM store / 未设→repo-root 不变）；precompute data_source 粒度标记（全 real/mixed/fixture）；scope 守门含刷新 job。
- 既有 B044 precompute/recommendation_snapshot 契约不破。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 真实数据刷新 CLI（Tiingo prices + SEC EDGAR fundamentals → VM unified CSV store）+ workbench-data-refresh.{service,timer} + scope 守门 + pytest |
| F002 | generator | trade loaders data-root env 覆盖（读 VM store / repo-root 兼容）+ precompute 设 env + fixture fallback 保留 + pytest |
| F003 | generator | precompute data_source 粒度真实标记（real/mixed/fixture）+ 全 sleeve real 路径（S3 sleeve_unavailable 消除）+ pytest |
| F004 | codex | L1 + L2 真 VM 验收（刷新 timer 自动接线 + 真机刷新写 unified 数据 + precompute data_source=real 全 sleeve + /current 真实权重非 fixture + 数据明细记录）+ signoff |

---

## 6. 不做的事（YAGNI / 留 B046+）

- 不做 regime reconcile（B046）/ account current_weight（B046）。
- 不改 master portfolio 评分逻辑 / 5 因子 / planning weights（仅喂真数据）。
- 不做评分调参 UI / AI 解释（B043）。
- 不输出预期收益数字（定位 §1.1）。
- 不让请求路径 import trade/（§12.10.2 守门维持）。
- 不改前端（数据源换透明）。

---

## 7. 验收门槛汇总

- **F001**：刷新 CLI（Tiingo+EDGAR 真实抓取 → VM unified CSV 正确 schema）+ workbench-data-refresh.{service,timer} + scope 守门含刷新 job；backend pytest ≥ baseline+≥8 / ruff 0 / mypy 0 / 复用既有 secret。
- **F002**：loader data-root env 覆盖（env 设→VM store / 未设→repo-root 本地 CI 不变）+ precompute 设 env + fixture fallback 保留；pytest 覆盖两路径；既有 trade loader 本地行为不破。
- **F003**：precompute data_source 粒度标记（全 real / mixed / fixture 明细）+ 数据齐时全 sleeve real（risk_parity/us_quality 不再 stub）；pytest；不破 B044 recommendation_snapshot 契约。
- **F004**：L1 全门禁 + secret grep 0；L2（真 VM）：(1) health 200 + HEAD≡main + recent-errors=0；(2) **workbench-data-refresh.timer 经 B037-OPS1 自动 enabled+active 无 warn**；(3) **手动 trigger 刷新 service → VM unified CSV 有真实 prices+fundamentals**（记录抓了哪些 symbol/行数）；(4) **手动 trigger precompute → recommendation_snapshot `data_source=real`（或 mixed 明细）+ risk_parity/us_quality 真实评分非 stub**（对比 B044 的 fixture，记录权重变化）；(5) **GET /api/recommendations/current authenticated 200 真实权重**（全 sleeve 真实，非仅 momentum）+ anon 401；(6) B026 absent。Signoff 用模板（§24 timer 接线 + §Production/HEAD + §Post-signoff Deploy + **data_source real/mixed 显式声明 + 与 B044 fixture 对比**）。Framework 候选：data-root env 跨 repo-root/VM 适配 若出新通用规律记 §Framework Learnings。

---

## 8. 参考文档

- 真实源：`workbench_api/data/tiingo_loader.py`（B027 prices）/ `workbench_api/data/sec_edgar_loader.py`（B029 `fetch_quarterly_fundamentals`）/ `scripts/backfill_fundamentals.py` + `scripts/universe_us_quality.py`（backfill 逻辑参考）
- loader 路径：`trade/data/loader.py` + `trade/data/us_quality_universe.py`（unified CSV 解析 + 优先级）
- B044 precompute：`workbench_api/recommendations/precompute.py`（data_source 标记点）
- 边界 r / §12.10.2 / B037-OPS1 timer：project-status §永久硬边界 + `framework/harness/generator.md`
- snapshot 目录 provision 先例：market-context/news（`/var/lib/workbench/data/snapshots/`）

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| SEC EDGAR fundamentals 覆盖/时延不足（部分 symbol 无财报）| precompute data_source 粒度标记 mixed + L2 记明细；缺的 symbol fixture fallback 诚实标记（v0.9.21）|
| Tiingo 深历史抓取成本/rate limit | 复用 B027 budget guard + request_spacing；universe 限 master 所需 symbol |
| trade loader data-root env 覆盖破坏本地/CI（repo-root）行为 | env 未设→保持现有 repo-root；pytest 双路径；本地 FORCE_FIXTURE 等开关不动 |
| VM data dir 权限/磁盘（B044 S1 disk 82%）| 写 `/var/lib/workbench/data/snapshots/`（deploy 用户可写）；unified CSV 体量监控（接 S1 disk soft-watch）|
| 刷新 job import trade/ 触 §12.10 | job 非请求路径；写 VM dir 非 repo-root；scope 守门扩刷新 job |

---

## 10. 与既有批次的边界 + 后续

- **不改**：master 评分/5 因子/planning weights（仅喂数据）/ B044 precompute→snapshot→read 架构 / 前端 / B041 UI。
- **B046（Batch 3）**：regime sleeve reconcile（注册表对齐 master 实际 4-sleeve 组成；regime 留研究态）+ account current_weight（AccountSnapshot + PriceProvider marks / NAV，复用 home.py）。
- **B043 依赖**：B044(评分闭环)+B045(真数据)+B046(current_weight) 齐 → AI「为什么这样建议」有真东西可解释。
- disk soft-watch（B044 S1）：unified CSV 落 VM 增磁盘占用，持续监控。
