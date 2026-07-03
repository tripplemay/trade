# B080 — 策略生命周期监控 + 试验登记簿 + 冻结式再验证流水线（评审 P0，L0+L1）Spec

**批次定位：** 策略研究体系化基建（混合批次 4 generator + 1 codex）。不改任何策略逻辑/参数——「再验证」非「再训练」，流水线不允许改参数。这是评审报告对"要不要自动进化机制"的正式回答落地：**建监控+再验证+门禁，不建自动进化训练闭环**。

**来源：** 2026-07-03 用户立项（backlog `B0XX-strategy-lifecycle-monitoring`，评审路线图 P0）← `docs/research/ashare-strategy-deep-review-2026-07-03.md` §2.3（L0+L1 层）。Explore 预研 2026-07-03 已核源码。

**Planner 默认决策（用户 /goal 持续推进授权下采用，如有异议可随时推翻重排）：**
1. **不拆两批**：L0+L1 合并一批 5 features（评审报告建议 4-5，DB 层两件合并为 F001）。
2. **CPCV-lite 代替全 CPCV**：K=4 交错 IS/OOS split（季度错开）+ 1 个月 purge gap，复用引擎任意窗口能力；signoff 与卡片中**诚实标注非全组合 CPCV**；全 CPCV 若未来需要另立批次。
3. **paper 首日口径修前向不改历史**：建仓成交价改用 activation 当日可得价格（修前向逻辑）；历史首日假象（B074 建仓 06-18 价 vs 06-22 标记，虚增 +2.6~3.1pp）不重算历史 NAV 行，在 API/面板 meta 加标注说明。

---

## 0. 设计要点（Explore 2026-07-03 已核源码，焊死）

- **paper NAV 原料齐**：`paper_nav_history`（逐日 nav+positions JSON+benchmark_close）+ `paper_rebalance`（逐次成本）+ `services/paper.py _build_nav_curve`。跟踪误差直接组合现成件。
- **★滚动 IC 信号保真度陷阱**：`recommendation_snapshot` cn_attack 为逐日行、但存的是**过不动区后的持仓目标**（等权 target_weight），原始动量 score 未落库；Master 仅季度粒度（逐日重跑覆盖同一季度末行）。→ **Master 不做滚动 IC**（只做跟踪误差）；cn_attack 先做「持仓级 IC」（**必须**在指标 meta 与面板标注"持仓保真非纯信号 IC"），并从本批起让 cn_attack precompute 把原始 score 落库进 `master_meta.signal_scores`（前向积累；≥12 个月后才有完整滚动窗——诚实边界，面板显示积累进度）。
- **trial registry 必须新表**：`backtest_run` 是工作队列+结果存储（无 parameter_hash/universe/区间/verdict 一等字段），语义不符 DSR「尝试次数 N」。新表 + **B066-B078 历史试验一次性回填**（从 signoffs 整理，N 起点诚实，每条 source_ref 指向 signoff 文件）。
- **红卡双处硬编码**：`strategy_modes/cn_attack_precompute.py:80-95`（CN_ATTACK_RESEARCH_CAVEAT dict）+ `strategy_modes/registry.py:126-153`（description 内写死 −9~−11%）。→ 新表 `oos_verification_card`，precompute 运行时读 DB、**缺行 fallback 现硬编码值（byte-identical 零回归，守门单测）**；registry description 去具体数字改为「以验证卡片为准」。
- **去偏重验证可复跑但无自动化**：`scripts/research/b070_survivorship_comparison.py` 是参数化 CLI（读 `data/research/b070` 冻结快照，`WORKBENCH_DATA_ROOT` 覆盖不碰生产）；「追加新数据」fetch（baostock 长任务 ~30-40min）未接 timer；产出仅 md/json 未入 DB。→ 两段式 pipeline（见 F003）。
- **timer 基建零缺口**：`workbench/deploy/systemd/` 一对 .timer+.service，deploy.sh 通配自动装。周频 `OnCalendar=Mon *-*-* 05:00:00`（避开 03:00-04:00 现有 job 带）、季频 `*-01,04,07,10-01 06:00:00`。oneshot service 必须显式 `TimeoutStartSec`（v0.9.54 §38 watchdog 纪律）。
- **IC 算法模板现成**：`scripts/research/b077_signal_first_look.py` 的 `forward_returns`/`rank_ic`/`grouped_spread`（纯函数已单测）→ 迁入 `workbench_api/monitoring/` 与 `price_history.closes_by_symbol_since` 组合。
- **市值横截面接线**：拥挤度/暴露用 `cn_size.csv` 帧（照 `trade/strategies/cn_attack_momentum_quality/size.py` PIT 口径）喂 paper 持仓 → 市值分位/小盘占比/集中度 HHI；**行业维度本批不做**（fundamentals_cache 隔离红线不破）。
- **B079 遗产直接可用**：monitoring 面板显示标的时走 `<SymbolLink name=...>`（B079 F003），API 层 enrich 用 `resolve_symbol_names` batch（B079 F002 模式）。

## 1. 复用清单

| 资产 | 位置 | 用法 |
|---|---|---|
| NAV/持仓/成本历史 | paper_nav_history / paper_rebalance / services/paper.py | 跟踪误差+暴露原料 |
| 逐日推荐历史 | recommendation_snapshot（cn_attack 逐日） | 持仓级滚动 IC |
| IC 纯函数 | scripts/research/b077_signal_first_look.py | 迁入 monitoring 包 |
| 价格序列 | price_history repo `closes_by_symbol_since` | 远期收益 |
| PIT 市值 | data/research/b076/cn_size.csv + size.py 口径 | 暴露/拥挤度 |
| 去偏重跑 CLI | scripts/research/b070_survivorship_comparison.py | 冻结再验证内核 |
| 队列/状态范式 | target_refresh_job / backtest_run repo + lib/backtest-poll.ts | pipeline 状态与轮询 |
| timer 模板 | deploy/systemd/workbench-recommendations.{timer,service} | 周频/季频 job（+TimeoutStartSec） |
| 面板模板 | app/(protected)/paper/page.tsx + snapshots/page.tsx + nav-items.ts | /monitoring 页 |
| 名称显示 | B079 SymbolLink name-prop + resolve_symbol_names | 面板标的显示 |

## 2. Feature 拆解（5：4 generator + 1 codex）

### F001 (g) — DB 层：trial_registry 表 + 历史回填 + oos_verification_card 红卡 DB 化

1. **trial_registry 表**：id/created_at/batch/strategy_id/parameter_hash/params(JSON)/universe/window_start/window_end/oos_split/metrics(JSON)/verdict(GO|NO_GO|INCONCLUSIVE|NA)/source_ref/notes + repo + 只读 API（列表/按 strategy 计数=DSR 的 N）。B050 回测 worker 完成一次 run 时自动登记一条（verdict=NA，params 带 parameter_hash——引擎已有 `parameter_hash()`）。
2. **历史回填**：幂等 seed 脚本，从 B066/B068/B069/B070/B075/B076/B077 signoffs 整理 ≥15 条历史试验（每条 source_ref 指向报告文件路径，数字照抄原文）。
3. **oos_verification_card 表**：strategy_id PK/validated/oos_result/oos_cagr_range/headline_zh/headline_en/detail_zh/detail_en/backtest_ref/updated_at/source + repo + seed 迁移写入现红卡值。
4. **precompute 读源改造**：`_build_target_result` 改为读 DB 卡片，**无行 → fallback 现 CN_ATTACK_RESEARCH_CAVEAT dict（byte-identical，回归测试焊死）**；registry.py description 去具体数字。

**Acceptance：** 两表+迁移+repo+API；回填 ≥15 条（抽 3 条对照 signoff 原文精确一致）；回测完成自动登记；无卡片行时快照 meta 与现状 byte-identical（守门单测）；有行时以 DB 为准。Gates：backend pytest ≥ baseline / ruff 目录上下文 / mypy CI-exact 0 / alembic head。

### F002 (g) — 监控指标计算 job + API（L0 核心）

1. 新包 `workbench_api/monitoring/`：
   - **持仓级滚动 rank-IC**（cn_attack 两模式）：t 日 recommendation_snapshot target_weight 排名 vs N∈{5,10,20} 日远期收益（price_history），12 个月滚动窗 + 滚动 t-stat；快照历史不足 12 个月 → 按现有窗口出数并标 `partial: true`（诚实降级，不报错）。
   - **原始 score 落库**：cn_attack precompute 顺带把当日全宇宙动量/复合 score top-N 写入 `master_meta.signal_scores`（前向积累；零回归——纯加 meta 键）。
   - **paper vs 基准跟踪差**：复用 nav curve，per-strategy 基准（见 F004 的基准修复；F002 内先按 strategy→benchmark 映射常量实现）。
   - **暴露/拥挤度**：paper 持仓 × cn_size PIT 帧 → 市值分位中位数/小盘占比（低于宇宙中位市值的持仓比例）/HHI 集中度。
   - **换手/不动区触发率**：paper_rebalance 频率 + 每次成本。
2. 结果表 `monitoring_metric`（strategy_id/as_of/metric/value/meta JSON，唯一键 strategy_id+as_of+metric）+ 只读 API `GET /monitoring/metrics`。
3. 周频 timer `workbench-monitoring.{timer,service}`（Mon 05:00 UTC，`TimeoutStartSec` 显式）+ CLI `python -m workbench_api.monitoring.cli`。

**Acceptance：** 两 cn_attack 模式全指标真数据产出（VM 或本地真 DB 快照）；IC 标注"持仓保真"+partial 降级；阈值仅提示（IC 0.05-0.10 参考带、t<2 噪音——meta 标注经验法则）；advisory-only（无任何执行动作）。Gates 同 F001。

### F003 (g) — 冻结式再验证 pipeline（L1 核心）

1. **两段式**：
   - **数据追加 job**（季频，周末窗口）：baostock 拉 B070 宇宙增量价格追加研究快照副本（`data/research/b070` 不动，写 `data/research/reverify/<date>/` 新副本）；长任务显式超时 watchdog（v0.9.54 §38）+ 逐只 fetch 超时（§39 清单含 bulk）。
   - **重验证 job**：参数**完全冻结**（代码层不接受任何参数输入，只读冻结 config 常量）重跑 b070 对照回测 + **CPCV-lite**（K=4 交错 IS/OOS split，季度错开 + 1 个月 purge gap，报告各 split 的 OOS CAGR/Sharpe 分布）→ 三处落地：① `oos_verification_card` 更新（**只能更保守或数据如实，代码路径上不存在 validated=False→True 的赋值**——摘红卡永远走人工批次）；② trial_registry 登记一条（verdict 按双门禁规则：全样本+OOS 不劣于上期 → 维持，劣化 → 标注）；③ md 报告落 `docs/test-reports/auto/reverify-<strategy>-<date>.md`。
2. 状态表（照 target_refresh_job 范式）+ 手动触发 API（POST + GET 轮询，照 backtest-poll 范式）+ 季频 timer。

**Acceptance：** 手动触发端到端真数据跑通（数据追加 → 重验证 → 卡片/registry/报告三落地）；参数冻结守门单测（尝试注入参数 → 拒绝）；无 validated 翻真路径（AST/grep 守门断言）；CPCV-lite 标注"非全 CPCV"。Gates 同 F001 + trade/ 侧 mypy trade（若触 trade/）。

### F004 (g) — 前端 /monitoring 面板 + paper 三口径修复

1. **/monitoring 页**（nav 增项 + zh/en i18n key）：每策略健康卡（滚动 IC 曲线含 partial 标注/跟踪差/暴露拥挤度/红卡状态）+ trial registry 表（DataTable）+ 再验证历史与手动触发按钮（触发的是研究 pipeline，非交易——按钮文案注明）。仿 paper 六段 Card 布局；标的显示走 `<SymbolLink name>`。
2. **paper 三口径修复**：① `services/paper.py:56 BENCHMARK_SYMBOL="SPY"` → per-strategy 基准映射（cn_attack 两模式→CSI300（读 cn_csi300.csv 或 price 表）、master/regime→SPY 不变）；② cn_attack paper 账户 base_currency 改 CNY（迁移 + 前端 currency 格式化验证）；③ 建仓成交价改用 activation 当日可得价格（前向逻辑）；历史首日假象不重算，在 paper view API meta + 面板加标注。

**Acceptance：** 面板真数据渲染（截图）；CN 策略基准曲线为 CSI300 且注明；历史口径标注可见；vitest/tsc/eslint + Playwright e2e（含 no-execution safety 守门——monitoring 页无交易 affordance 断言）。Master paper 视图零回归（SPY 基准/USD 不变）。

### F005 (codex) — 独立验收 + signoff

- L1 全门禁（CI 绿可跳全量复跑，safety + 新单测子集本地抽查）。
- **L2 真机**：VM 上 timer 装载（`systemctl list-timers workbench-monitoring*` 等）；监控指标真数据（两模式 IC/暴露数字合理性抽查——对照手工计算一个点）；再验证 pipeline 手动触发跑通（或如实标注长任务窗口未跑）；红卡 DB 化零回归（无行 fallback byte-identical 实测）；trial registry 回填抽查 3 条对照 signoff 原文；paper 口径修复实测（CN 基准曲线/CNY/首日标注）；/monitoring 面板截图；no-execution 守门。
- 边界：research-only/no-broker；HEAD≡prod；signoff 逐条证据。

## 3. 状态流转 + 不变量

- 混合批次：`planning → building(F001→F002→F003→F004) → verifying(F005) → done`。
- **不变量**：① 不改任何策略逻辑/参数（监控纯观测；pipeline 参数冻结，代码层无参数注入路径）；② **pipeline 不得自动摘红卡**（无 validated→True 路径，守门断言）；③ 红卡 DB 化零回归（无行=现状 byte-identical）；④ advisory-only/no-execution 守门不破（monitoring 页无交易 affordance）；⑤ research-only/no-broker/名称与指标均 read-only 请求路径；⑥ §12.10.2（新 request-path 模块注册守门——B079 教训）/ ruff 目录上下文 / mypy CI-exact / alembic head / oneshot timer 显式 TimeoutStartSec（v0.9.54）。
- **诚实边界**：① 滚动 IC 前 12 个月为 partial（快照历史 2026-06-18 起）；② 持仓级 IC ≠ 纯信号 IC（score 落库起前向积累）；③ CPCV-lite ≠ 全组合 CPCV；④ 历史 paper 首日假象保留原样仅标注；⑤ 再验证数字只会更保守——这是特性不是回归。
- **后续**：L2（人工审批参数再估计）/L3（Qlib 因子研究）门禁见评审报告 §2.3，本批不做；行业暴露维度、全 CPCV、Master 逐日信号历史为可选 follow-up。
