# B067 — A股 进攻策略 P2（实盘 advisory surface + 手动执行闭环）Spec

**批次定位：** A股 进攻模型 3 步路线图第②步的 **P2**（接 B066 P1 引擎之后）。把 cn_attack 引擎的每日信号接成**实盘 advisory surface**：**两份推荐流**（质量+动量 / 纯动量，各独立账户）+ 每日输出 **{推荐目标持仓, 是否调仓, 获利了结清单}** + **完整手动执行闭环**（ticket→fills→reconcile→journal，复用 B023/B057，按 strategy_id 隔离）。

**来源：** 2026-06-18 用户拍板（B066 P1 done 后选 P2）：两份推荐 + 完整执行闭环。

---

## 0. ★不可妥协的诚实约束（贯穿，硬性）

B066 P1 诚实结论：**OOS（样本外）动量逆转、CAGR −9~−11%；质量 A/B 本地未分胜负（需宽宇宙才答）**。本 P2 surface **绝不能让用户误以为它是验证过的赚钱策略**：

1. **研究态徽章（funding_state=research，ModeSelector 自动）+ 专门的「OOS 负收益 / 未验证」诚实披露**摆在每日推荐旁（不止通用研究徽章，须 cn_attack 专属文案：动量逆转期会亏 / 未经样本外验证 / 按它交易风险自负）。
2. **advisory-only / 不自动下单 / no 收益预测**（系统硬边界 + no-execution 守门）——只输出"系统建议"，用户手动决定执行。
3. IS/OOS 回测记录（B066）可在 surface 触达（让用户看到它的真实历史，含负 OOS），不藏。

> 设计立场：用户有权用这个工具，planner 的职责是诚实框架 + 守门，不是拒绝。surface 满足"每天看推荐"需求 + 不掩盖未验证。

---

## 1. 愿景（与 Master 的分工）

cn_attack 进攻模式与 Master/regime 并行（B057 多模式平台）。**两份推荐流**（同引擎，因子变体不同）：

| strategy_id（建议）| 变体 | 退出 |
|---|---|---|
| `cn_attack_quality_momentum` | 质量过滤→动量 | momentum_decay 基线（跌出 top-N 退=自然获利了结）|
| `cn_attack_pure_momentum` | 纯动量（无质量过滤）| 同上 |

> 退出变体（trailing_stop/hard_profit_target）是 B066 回测研究维度；**P2 live 默认 momentum_decay**（基线、低换手、自然轮动获利了结）；其它退出留后续按需（surface 可后扩切换）。质量 A/B 在宽宇宙 advisory 上自然分化（解 P1 本地未分胜负）。

---

## 2. 复用清单（核过源码——Explore 摸底；框架已 strategy_id 参数化）

| 复用资产 | 位置 | 用法 |
|---|---|---|
| B057 模式 registry | `strategy_modes/registry.py`（`_MODES` L83，`StrategyMode` L44，regime 行 L94 模板，funding_state=research）| **加 2 行**（cn_attack 两变体）+ 新增 `CADENCE_DAILY` 常量 |
| target producer dispatch | `strategy_modes/refresh_worker.py`（`_DISPATCH` L107，`_run_regime_producer` L88 模板，IS 允许 lazy import trade）| **加 2 producer**（共用 1 个参数化 precompute，按 factor_variant 区分）|
| 通用 target 读层 | `strategy_modes/targets.py`（`get_target` L71 对任意 strategy_id 零改动；`compute_target_key` L56）| 零改动 |
| recommendation service | `services/recommendations.py`（`get_current_recommendations(strategy_id)` L258、`_build_target_positions(strategy_id)` L168，B044 target+B046 current_weight+diff）| 零改动（已参数化）|
| snapshot repo | `db/repositories/recommendation_snapshot.py`（`save_batch(strategy_id)` L40 delete-by-(sid,date) 幂等；`latest_snapshot(strategy_id)` L102）| 复用;★见 §3 cash-buffer 守门 |
| position-diff | `services/execution.py`（`get_position_diff(strategy_id)` L153，"卖到零"清单 L259=获利了结渲染源）| 零改动 |
| 独立账户 | `account_snapshot`（strategy_id 列，migration 0021 已存在）+ `get_latest_account/update_account(strategy_id)` | **零 schema 改**：`PUT /execution/account?strategy_id=<id>` seed 两账户 |
| 执行闭环 | `routes/execution.py`（tickets/fills/reconcile/journal **全 strategy_id 参数化**）+ `services/tickets.py`（`generate_ticket(strategy_id)`）+ `reconcile.py` | **零改动**（ticket.strategy_id 继承）|
| 每日 timer 模板 | `workbench-recommendations.timer`（daily 03:00）+ regime precompute service；deploy.sh L442 glob 自动 install+enable | **加 2 对 timer/service**（deploy.sh 不动）|
| 前端 ModeSelector | `components/strategy/ModeSelector.tsx`（research 徽章 L74 自动）+ recommendation/position-diff 页（`?strategy_id=` 已接）| 多数零改动;加 cn_attack 专属 OOS 诚实文案 + no-execution 扫描列表 |
| cn_attack 引擎(B066) | `trade/strategies/cn_attack_momentum_quality/signal.py`（`generate_cn_attack_signal` L102）+ `trade/backtest/.../engine.py`（`run_cn_attack_backtest` L309，`CnAttackDailyRecord` 含 target_tickers/rebalanced/forced_exits L90）| **每日 target 走 daily-driver 取 final-day record**（含 no-trade band + 获利了结），非裸 signal |
| paper（可选前向验证）| `paper/targets.py PAPER_STRATEGIES` L45（从 `_MODES` 派生，进 registry 即自动 paper-enabled）| 模式进 registry 后 `activate_paper_account(strategy_id)` 零接线 |

---

## 3. 必须新写/改的点 + 三个硬陷阱（Explore 结论）

1. **★save_batch 权重和=1.0 守门 vs cash_buffer（头号陷阱）**：`save_batch` L68 `abs(weight_sum−1.0)>1e-3` 即 raise；cn_attack `CnPortfolioWeights` 有 `cash_buffer`（weights 不和为 1.0）→ **producer 必须把 cash buffer 显式补成一行**（如注入现金/SGOV 等价符号，或类比 regime `_finalize_weights` 把残差路由），否则拒写。
2. **cn_attack 升格出 STANDALONE_RESEARCH**：现 `services/strategies.py:346 STANDALONE_RESEARCH_STRATEGY_IDS={cn_attack_momentum_quality}`（P1 刻意排除 mode/home/advisor/paper）→ P2 进 `registry._MODES`；两变体两 strategy_id（backtest registry 可拆 2 条或保单 backtest+双 advisory id）。注意 registry（模式）与 strategies.py sleeve registry 是两套，进 `_MODES` 不影响 `sleeve_strategies()`（cn_attack 是独立模式非 master sleeve）。
3. **获利了结语义落地**：diff reason 现来自 snapshot rationale，无专门 profit-take 标记 → producer 把 daily-record 的 `forced_exits`（+「跌出 top-N」自然退）写进 snapshot rationale/master_meta，position-diff 的 reason 列才能体现"获利了结/退出"。
4. **CADENCE_DAILY**：registry 无 daily 常量，新增；每日 precompute 跑（daily-driver 取 final-day target）。
5. **export_ticket 参数化**（若要导出 cn_attack ticket）：`services/recommendations.py:407 export_ticket` 内部硬调 master-only，须传 strategy_id。
6. **gate 语义**：`_build_gate_checks` kill_switch=平台级 master_drawdown（非 per-mode）；spec 明确 cn_attack 的 gate 复用平台 kill-switch（研究态可接受）。
7. **safety**：新 producer 的 scope-test 块（`test_market_scheduler_scope.py` 同构，evaluator §24）；no-execution 扫描列表加新 surface（若新增页/组件）；registry/targets 禁 import trade（precompute/producer lazy import 允许）。

---

## 4. Feature 拆解（4 features：3 generator + 1 codex）

### F001 — cn_attack 两变体 advisory 模式接入（registry + producer + 每日 precompute + cash-buffer 补 1.0 + 获利了结 meta）（executor: generator）

1. `registry.py`：加 `CADENCE_DAILY` + 2 个 strategy_id 常量 + 2 行 `_MODES`（funding_state=research，cadence=daily，display_name 双语，target_producer 指向新 precompute）。
2. `refresh_worker._DISPATCH` 加 2 producer（共用 1 个参数化 `cn_attack_precompute(session, strategy_id, factor_variant)`，lazy import trade）。
3. precompute：跑 cn_attack daily-driver（`run_cn_attack_backtest` 到 as_of，取 **final-day record** 的 target/rebalanced/forced_exits），**★cash_buffer 显式补成 1.0 一行**，`save_batch(strategy_id, as_of, rows, master_meta)`；**forced_exits + 跌出 top-N 写进 rationale/master_meta**（获利了结落地）。
4. cn_attack 升格出 `STANDALONE_RESEARCH_STRATEGY_IDS`（进 mode 体系；backtest registry 拆/保 planner 定）。
5. **★OOS 诚实 meta**：snapshot master_meta 带 cn_attack OOS-负/未验证 caveat（供 surface 渲染）。

**Acceptance（§29 实测）：** 跑 precompute → `recommendation_snapshot` 写出两 strategy_id 的 target（**权重和=1.0，cash 行在内**，过 save_batch 守门）；`get_target(strategy_id)`/`/api/recommendations/current?strategy_id=` 各返对应变体推荐；forced_exits 体现在 rationale。Gates：backend pytest/ruff 目录上下文/mypy CI-exact 0；registry/targets 无 trade import（AST 守门）。

### F002 — 每日 timer/service + CLI 接线（daily cadence）+ deploy + scope safety（executor: generator）

1. CLI entrypoint（`strategy_modes/cn_attack_cli.py` 或子命令）跑两变体 precompute。
2. 2 对 `workbench-cn-attack-*.timer`（daily `OnCalendar`）+ `.service`（ExecStart 跑 CLI，WORKBENCH_DATA_ROOT，hardening，**不含 broker/order/fills/reconcile 字样**）；deploy.sh glob 自动 install+enable（不动 deploy.sh）。
3. **入口级 env 守门**（§12.11.1，precompute 写生产 DB）。
4. scope safety-test 块（`test_market_scheduler_scope.py` 同构）+ `test_deploy_timer_wiring.py`（sibling .service / glob / 无硬编码 enable，已满足）。

**Acceptance：** 两 timer/service 文件就位；本地 safety test 过（scope/wiring）；CLI 可跑 precompute；env 守门测试过。Gates 同 F001。L2 由 F004 验 systemd enabled+active（§24）。

### F003 — 前端 advisory surface + ★cn_attack OOS 诚实框架 + 获利了结渲染 + no-execution 守门（executor: generator）

1. ModeSelector 自动列出两新模式（research 徽章自动）;recommendation 页 + position-diff 页按 `?strategy_id=` 工作（多数零改动）。
2. **★cn_attack 专属诚实披露**（超出通用研究徽章）：选中 cn_attack 模式时，醒目展示「未经样本外验证 / OOS 动量逆转期会亏 / 按它交易风险自负」+ 可触达 B066 IS/OOS 回测记录。双语。
3. **获利了结清单**清晰渲染（position-diff reason 列体现 forced_exits/跌出 top-N）。
4. no-execution 扫描列表加新 surface（若新增页/组件）；disclaimer 仍渲染；api.ts 重生+drift（若 schema 变）;i18n parity。

**Acceptance：** 两模式在 ModeSelector 出现带研究徽章；选 cn_attack 模式见专属 OOS 诚实披露；每日 target+diff+获利了结 渲染；no-execution/disclaimer 守门过；vitest/tsc/eslint/i18n parity/api.ts drift 绿。

### F004 — Codex L2 真机验收 + signoff（executor: codex）

**真数据/真机批次——signoff 必含实测证据硬段（§29）：**
- L1 全门禁（backend+trade mypy+ruff 目录上下文+frontend+safety）。
- **L2 真机实测（VM，贴真返回）：**
  - 两 timer 触发 → precompute 真跑 → `recommendation_snapshot` 两 strategy_id target 真值（**权重和=1.0 含 cash 行**）；systemd timer enabled+active（§24）。
  - ModeSelector 见两 cn_attack 模式 + 研究徽章 + **专属 OOS 诚实披露**（真渲染截图）。
  - `/recommendations?strategy_id=` 各变体真推荐;`position-diff` 真 target/current/diff + **获利了结**体现。
  - **执行闭环 per strategy_id 隔离真验**：seed 独立账户 → 生成 ticket（strategy_id 隔离）→ fills → reconcile → journal 跑通一次（advisory，**无自动下单**）；Master/regime 账户/推荐**零回归**。
  - 边界 adversarial：advisory-only/no-broker/no 收益预测/no 自动执行/研究态不碰真金自动化；HEAD≡prod；recent-errors=0。
- signoff `docs/test-reports/B067-...-signoff-*.md`，实测证据硬段逐条贴真观测 + 演练自清（执行闭环冒烟后 void ticket/恢复账户）。

---

## 5. 状态流转 + 风险

- 混合批次：`planning → building(F001→F002→F003) → verifying(F004) → done`。
- **风险与缓解：**
  - **用户在未验证策略上交易**（OOS 负）→ ★诚实框架（F003 专属披露 + IS/OOS 可见）+ advisory-only + 手动执行；planner 已明示。
  - cash_buffer vs save_batch 1.0 守门 → F001 显式补 cash 行（头号陷阱）。
  - 两变体 mode 体系污染 Master/regime → cn_attack 独立模式（非 sleeve），mode registry 与 sleeve registry 两套，零回归核。
  - 每日 timer 运维 → deploy.sh glob 自动接线 + scope safety + §24 L2 验。

## 6. 不变量清单（Codex 回归核）

1. Master/regime 模式/推荐/账户/执行/home NAV 零回归（cn_attack 独立 strategy_id，框架已隔离）。
2. **research-only / advisory-only / no 自动下单 / no-broker / no 收益预测**；研究态诚实标注（含 cn_attack 专属 OOS 披露）。
3. cn_attack 不进 master sleeve（`sleeve_strategies()` 不含）；不碰 live Master 真金。
4. §12.10.2 请求路径无 trade（registry/targets 禁 import；precompute lazy）;§12.11.1 env 守门。
5. trade 离线（akshare 在 data_refresh 侧）；US/A股 lookup 零回归。
