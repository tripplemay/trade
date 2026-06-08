# BL-B011-S2 — HK-China satellite 策略实现 → Master Portfolio 4/4 真实

> **状态：** planning（2026-06-08 起草）。
> **批次类型：** 新功能 / 策略实现（里程碑 C §6 Master 4/4 真实；backlog order 5）。约 80% 复用 B025 us_quality satellite 模板。
> **权威设计：** `docs/strategy/04-hk-china-etf-small-allocation.md`（策略说明书）。
> **来源：** B011 signoff §Soft-watch S2 + 里程碑 C「所有页面接真实引擎」——`satellite_hk_china` 是 master 唯一 by-design stub（SLEEVE_TYPE_SATELLITE_STUB，strategy_id=None，precompute data_source=mixed 的唯一 stub）。

---

## 1. 目标

实现 HK-China satellite 策略，让 **Master Portfolio 从 3/4 真实 → 4/4 真实**（激活 `satellite_hk_china` sleeve，去 SATELLITE_STUB），precompute `data_source` 可达 full `real`。这是里程碑 C「Master 真实度」的最后一块。

---

## 2. 决策（2026-06-07/08 用户已批 + planner 按设计说明书定，★=用户批）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 是否实现 | ★ **实现 HK-China**（2026-06-07 用户批） | 降级条件（真数据 B045 + AI 框架 B036）已解除 |
| Phase 1 universe | **仅 US-listed ETF：MCHI/FXI/KWEB/ASHR**（planner 决，设计 §4.3） | USD 计价，无汇率/港股日历复杂度；HK-listed（2800.HK 等）留 Phase 2 |
| 信号 | **3 因子：momentum + trend + 区域风险过滤**（planner 决，设计 §） | momentum=0.4·r3m+0.3·r6m+0.3·r12m；trend=price>200D MA & r6m>0；price-only 无 fundamentals |
| 选股 | **top 1-2 ETF（过 trend），余额 → defensive(SGOV)**（设计 §） | 非 B025 的 equal-weight top-15；per-ETF≤10% / KWEB 子限 5-10% |
| 区域风险过滤 | **用 universe 内 ETF 价格（KWEB/MCHI/FXI 200D MA + 6M return），不用 HSI**（planner 决） | HSI 不在 data-refresh universe；manual policy override 是用户判断不编码（研究-only） |
| 数据 | **prices-only**（planner 决，设计 §6） | 无 fundamentals；MCHI/FXI/KWEB/ASHR 入 B045 data-refresh ETF_UNIVERSE |
| cadence | **季度（对齐 master）** | 设计 §10 |

---

## 3. 永久硬边界（继承）

- research-only / no-broker / no-paper / 不做港股个股/窝轮/牛熊证（设计 §1 ETF-only）。
- §12.10.2：请求路径禁 import trade（hk_china 策略在 trade/，precompute job 调，请求路径只读 DB）。
- 定位 §1.1 不出收益预测；区域风险过滤是确定性价格触发，非 AI 预测。
- B023 / 既有 sleeve 契约不破。

---

## 4. 技术架构（约 80% 复用 B025 模板）

### 4.1 数据：HK-China universe 入 B045 + loader（F001）

- `data_refresh/refresh.py` `ETF_UNIVERSE` += MCHI/FXI/KWEB/ASHR（B045 pipeline 拉其 prices 入 unified CSV；ETF 不取 fundamentals）。
- 新 `trade/data/hk_china_universe.py`：`load_universe(as_of)`（ETF 列表 + 最小元数据）+ `load_prices(as_of)`（镜像 us_quality_universe loader：读 unified CSV/fixture，筛 HK-China ETF）；无 earnings/fundamentals loader（price-only）。
- 测试 fixture（合成 HK-China ETF prices）。

### 4.2 策略：hk_china_momentum 模块（F002）

- 新 `trade/strategies/hk_china_momentum/`：`parameters.py`（frozen dataclass + parameter_hash，复用 B025 模式：top_n=1-2/max_position_weight=0.10/kweb_sublimit/rebalance=quarterly）+ `factors.py`（momentum 0.4/0.3/0.3 + trend 200D MA & r6m>0 + 区域风险触发，price-only，复用 B025 factor 结构）+ `signal.py`（`generate_signal(parameters, as_of_date)→SignalResult`，签名同 B025）+ `construction.py`（top 1-2 过 trend + per-ETF/KWEB caps + 区域风险触发→defensive；简化版无 earnings/sector）。
- 单测 B025 风格（已知 prices→已知 weights；trend 过滤/区域风险→defensive/caps）。

### 4.3 master 激活（stub → implemented）（F003）

- `trade/portfolio/master.py`：`satellite_hk_china` sleeve `SLEEVE_TYPE_SATELLITE_STUB→IMPLEMENTED` + `strategy_id=None→"hk_china_momentum"`（validation 自动切换分支）。
- `trade/backtest/master_portfolio.py`：`KNOWN_IMPLEMENTED_STRATEGY_IDS` += `hk_china_momentum`；`MasterChildStrategyParameters` += `hk_china_momentum` 字段；`_resolve_child_weights` 加 dispatch case（镜像 us_quality：调 generate_signal→weights_dict，数据缺→defensive fallback）。
- master backtest 集成测试（4/4 sleeve 真实评分，hk_china 有数据→real）。

### 4.4 precompute / data_source（自动 + F003 验）

- precompute `score_master_target` 循环 master sleeves，激活后**自动**调 hk_china dispatch（无额外 wiring）。
- `data_source` 达 `real`：需 prices_source=real **且全 4 sleeve 有数据评分**；HK ETF 数据缺→hk_china stubbed→data_source=mixed（degrade graceful，不破其他 sleeve）。

### 4.5 测试

- pytest：hk_china loader（universe/prices）；strategy（momentum/trend/区域风险/caps/top 1-2/defensive）；master 激活（4/4 dispatch + validation）+ 集成（master backtest hk_china 真实评分）；precompute data_source 4/4→real（fake 全 sleeve 数据）。
- 既有 3 sleeve + B023 + §12.10.2 守门不破。

---

## 5. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 数据：MCHI/FXI/KWEB/ASHR 入 B045 data_refresh ETF_UNIVERSE + `trade/data/hk_china_universe.py` loader（price-only）+ fixture |
| F002 | generator | 策略：`trade/strategies/hk_china_momentum/`（parameters/factors momentum+trend+区域风险/signal/construction top 1-2+caps+defensive）+ 单测 |
| F003 | generator | master 激活（stub→implemented + dispatch case + KNOWN_IMPLEMENTED + params）+ 集成测试（4/4 backtest）+ precompute data_source 验 |
| F004 | codex | L1 + L2 真 VM 验收（data-refresh 拉 HK ETF prices + precompute data_source=real 4/4 + /current 含 hk_china 真实权重 + master backtest 4/4 + B023 不破）+ signoff |

---

## 6. 不做的事（YAGNI）

- 不做 HK-listed 港股 ETF（2800.HK 等，Phase 2）/ 不做港股个股/衍生品。
- 不接 fundamentals（price-only）/ 不用 HSI 指数（universe 外）。
- 不编码 manual policy override（用户判断；区域风险过滤仅确定性价格触发）。
- 不改 master 其他 sleeve / planning_weight（hk_china 仍 0.10）/ 评分逻辑。
- 不真实下单 / 请求路径 import trade。

---

## 7. 验收门槛汇总

- **F001**：MCHI/FXI/KWEB/ASHR 入 ETF_UNIVERSE（data-refresh 拉 prices）+ hk_china_universe loader（load_universe/load_prices price-only，镜像 us_quality）+ fixture；backend pytest ≥ baseline+ / ruff 0 / mypy 0。
- **F002**：hk_china_momentum 模块（generate_signal 签名同 B025；momentum 0.4/0.3/0.3 + trend + 区域风险 + top 1-2 + caps + defensive fallback）+ 单测（已知场景）；ruff/mypy 0。
- **F003**：master.py 激活（SATELLITE_STUB→IMPLEMENTED + strategy_id）+ master_portfolio dispatch/KNOWN/params + 集成测试（master backtest 4/4 真实评分）+ precompute data_source 4/4→real（数据齐）；既有 3 sleeve 不破。
- **F004**：L1 全门禁 + secret grep 0 + B023 回归绿；L2（真 VM）：(1) health 200 + HEAD≡main + recent-errors=0；(2) **data-refresh 拉 MCHI/FXI/KWEB/ASHR prices**（记录行数/日期）；(3) **precompute data_source=real（4/4 sleeve，hk_china 不再 stub）**（对比 B045 的 mixed）；(4) **GET /api/recommendations/current 含 hk_china 真实权重**（或区域风险触发→defensive，记录哪种）；(5) anon 401；(6) B026 absent。Signoff（§Production/HEAD + §Post-signoff Deploy + §24 若 timer + **data_source mixed→real + Master 4/4 清单**）。Framework 候选：satellite 模板复用 / 区域风险确定性过滤 若出新规律记 §Framework Learnings。

---

## 8. 参考文档

- 权威设计：`docs/strategy/04-hk-china-etf-small-allocation.md`
- 复用模板：`trade/strategies/us_quality_momentum/`（B025）+ `trade/data/us_quality_universe.py`
- master 激活点：`trade/portfolio/master.py`（L59-64 stub）+ `trade/backtest/master_portfolio.py`（L42-59 + _resolve_child_weights L457-509）
- 数据：`data_refresh/refresh.py`（ETF_UNIVERSE L46）/ precompute `score_master_target`

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| HK ETF 数据缺/不新鲜致 hk_china stub | data_source graceful degrade=mixed（不破其他 sleeve）；F004 L2 记 real/mixed 哪种诚实(v0.9.21) |
| 数据 freshness（HK 市场收盘时差）| Phase 1 US-listed ETF 走 US 日历，规避港股日历；data-refresh 拉 US close |
| 策略简化偏离设计说明书 | 严格按 §（momentum/trend/区域风险/caps/top 1-2）；单测对齐设计公式 |
| 改 master dispatch 破既有 3 sleeve | dispatch 仅加 case 不动既有；集成测试 4/4 + 既有 3 sleeve 回归 |

---

## 10. 与既有批次的边界 + 后续

- **不改**：master 其他 sleeve / 评分 / B044-B048 / 前端。
- **解锁**：Master 4/4 真实 → 里程碑 C「Master 真实度」达成；precompute data_source 可 real。
- **后续 order**：B042 Risk UI(6) → B047 Backtest+Reports(7) → B049 全页面审计(8)；B043 AI 解释解释 4/4 完整 Master。
- Phase 2（未来）：HK-listed ETF（2800.HK 等）+ USD/HKD 汇率（本批 Phase 1 US-listed 规避）。
