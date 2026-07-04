# New-strategy reuse map — end-to-end scaffolding

> 复用地图：新增一个策略批次（backlog 的 `dividend-lowvol-defense` / `pead-first-look` /
> `A股 ETF 趋势` / `B055 单市场选股` 等）时，**照抄哪些层、改哪些点**。以 `cn_attack_momentum_quality`
> 为范例（B081 刚全程走过）。目的：立项时 Research&Reuse 一步到位，避免每个新策略从零搭。
> **非 spec、非 active 批次**——planner 开批后据此起草正式规格。

## 分层（每层一个"照抄+改"点）

| 层 | 范例文件 | 复用 / 改 |
|---|---|---|
| **数据 universe** | `trade/data/cn_attack_universe.py`（`load_cn_universe_history`） | 照抄 loader 骨架；改数据源（新策略用 akshare ETF/成分/股息率）。`load_prices`（`us_quality_universe.py`）+ `WORKBENCH_DATA_ROOT` + PIT universe CSV 模式通用 |
| **参数** | `trade/strategies/<s>/parameters.py` | `@dataclass` + `factor_variant`/`weighting_scheme` 枚举 + `parameter_hash()`（trial id 用）。改因子/权重口径 |
| **信号** | `trade/strategies/<s>/signal.py` + `construction.py` + `size.py` | 因子计算 → 排序 → 权重构造。**新策略核心工作量在此**（红利低波=股息率+低波打分；PEAD=业绩预告事件） |
| **回测引擎** | `trade/backtest/<s>/engine.py`（`run_*_backtest` + `Config`） | ★**强烈复用**：T+1 open 执行、no-trade band、成本模型、WF 窗口。**必带 B081 引擎修真开关**（`lot_rounding`/`suspension_halt`/`delist_liquidation`/`price_limit_gating`，默认 True）——见 §分数股假象教训 |
| **成本模型** | `trade/backtest/<s>/costs.py`（`CnCostModel`） | 照抄；改印花税/佣金/滑点（A股卖出印花税 5bp、涨跌停…）。ETF 无印花税 |
| **指标** | `trade/backtest/us_quality_momentum/metrics.py`（`annualized_return`/`sharpe_ratio`/`max_drawdown`） | 直接 import，通用 |
| **对照/报告** | `trade/reporting/<s>.py`（`build_*_comparison`） | 照抄多变体对照构造器。★新增 config switch 时**每个 per-variant cfg 都要透传** `base.<switch>`（B081 F001 CI 红教训） |
| **live target** | `trade/backtest/<s>/live.py` | 当日建议目标（advisory）。照抄 |
| **precompute** | `workbench_api/strategy_modes/<s>_precompute.py` | 生产 advisory 生产器 + `<S>_RESEARCH_CAVEAT`（红卡 fallback dict，8 键）。照抄 |
| **strategy 注册** | `workbench_api/strategy_modes/registry.py` | 加 strategy_id 常量 + 注册 |
| **OOS 红卡** | `oos_verification_card`（model/repo/migration `0028` seed + `reverify_landings.py` 更新） | 照抄。`validated` **恒 False 硬编码**；seed 走 **data-migration**（非 bootstrap-only，B080 F005 铁律） |
| **trial registry** | `trial_backfill*.py` + data-migration（`0033`/`0034`） | 每个回测配置登记 trial（DSR N）。**data-migration 落地**（B080 F005） |

## 验收口径（planner 写 acceptance 时照搬）

- 去偏 **PIT** 宇宙（survivorship-free）+ **WF 70/30** + **CPCV-lite** + **DSR**（trial N）。
- **B066 式红/黄/绿卡**：红卡默认 `validated=False`；只向更保守方向更新。
- 防守型策略（红利低波）核验重点 = **回撤控制**（2024-02 型踩踏 DD）而非绝对收益。
- **引擎修真 A/B**（B081 模板 `scripts/research/b081_engine_fidelity_ab.py`）：跑手数取整/停牌退市/涨跌停各开关，
  确认 edge 非引擎理想化假象。

## 两条 B081 血泪教训（新策略必读）

1. **分数股假象（最重）**：A股回测不建 100 股/手取整 = 分数股假象，**显著虚高收益**。B081 实测 cn_attack
   OOS +28.4% → 修真后 **-14.7%**。成分增强路径尤其要开 `lot_rounding`。ETF 纯持有可豁免。
2. **默认口径变更门禁**：改 backtest 默认 config 值的 `trade/` edit，push 前必须跑 **full root pytest**
   （子集绿≠全绿；comparison/reporting/overfitting detector 都消费默认口径）。

## 部署种子数据铁律（B080 F005）

凡"部署后必须存在的种子数据"（trial / 红卡 / curated names），**必须走 alembic data-migration**
（随部署自动落地），**不能只放 `workbench-bootstrap` CLI**——否则生产静默缺数据、无告警、不自愈。
