---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B047-backtest-reports-real-engine：🔨 `building`**（2026-06-08 planning done；里程碑 C order 7『所有页面接真实引擎』；**大批次 5 features 4g+1c**）。Backtest（合成 stub _compute_synthetic_backtest）+Reports（读 docs/test-reports/ 108 份开发签收=错误类别）→接真实 master_portfolio 回测引擎（两页同源：generate_master_portfolio_reports 同时产出结果+投资报告）。**用户拍板（AskUserQuestion）**：①Backtest=**Option A on-demand async**（保留交互式 Run+任意参数，建 async worker，请求路径只读 DB／worker import trade 守 §12.10.2）；②Reports=**过滤出用户 Reports**（只显 kind=investment 真实报告，开发 signoff 过滤）。planner 决：worker=长驻 systemd service 轮询 backtest_run 队列(claim 原子)；Reports 源=canonical 定时回测。F001(表/repo/§12.10.2 守门)→F002(worker/service/scope)→F003(API async/前端轮询)→F004(Reports canonical/过滤)→F005(Codex L2)。**风险=async worker 新 infra(fix-round 高)，过大可拆 Backtest/Reports 两批。** spec `docs/specs/B047-backtest-reports-real-engine-spec.md`。
- **B042-risk-panel-robinhood：✅ `done`**（2026-06-08，0 fix-round；前端-only UI 微调 + BL-B023-S2 resolved）。Risk Panel Robinhood 化：colorForRiskState 统一 B040 emerald/amber/red 调色板(RiskBanner 去 ad-hoc)+per-sleeve 严重度配色+风控术语双语 tooltip+valuation_basis cost_degraded 诚实标注+字体一致。**BL-B023-S2 red 演练 PASS**：PUT 风险快照→DD 0.70≥0.15→red banner+kill_switch fail+defensive ticket+radio，红态截图落。signoff `docs/test-reports/B042-risk-panel-robinhood-signoff-2026-06-08.md`。
- **🎯🎯 BL-B011-S2-hk-china-satellite：✅ `done`**（2026-06-08，1 fix-round）。**Master Portfolio 4/4 真实达成（里程碑 C「Master 真实度」）**：hk_china 策略激活(去 SATELLITE_STUB)，precompute **data_source=real（4/4 sleeve，0 stub，20 positions vs B045 6）**。hk_china 本季 quarter-end 区域风险触发→全 4 ETF 未过 trend→100% SGOV defensive（确定性过滤生效，弱市收缩=valid）。**fix-round 1 根因=§12.10 家族**：us_quality+hk_china loader 读 repo-root `data/fixtures/`，trade wheel(`packages=["trade"]`)只含 trade/data/fixtures 不含 repo-root→VM wheel 装双 satellite stub（editable 本地掩盖，fresh deploy 暴露）；修=pyproject force-include data/fixtures 入 wheel(0.2.1)+守门 test_trade_wheel_bundles_fixtures.py。signoff `docs/test-reports/BL-B011-S2-hk-china-satellite-signoff-2026-06-08.md`。**下一批 B042 Risk UI(order 6，在真风控数据上)。**
- **🎯🎯 BL-B023-S1-trading-closed-loop-smoke：✅ `done`**（2026-06-08，含 1 fix-forward；Codex-only）。**里程碑 C §6『用户交易闭环端到端可用』= 完整确证（9/9 全 PASS）**：交易闭环在真实数据上端到端正面跑通——真实 6-pos target(B044/B045)+真实 mark-to-market current_weight(AAPL 市价 17.4% vs 成本 10.2%/NAV $35,246)+真实 kill_switch(B048 DD vs 0.15)+wash_sale(B048)→ticket(双语)→fills(3@市价)→**reconcile 200**(/reconcile/{ticket_id} snap-381cf)→journal(3 条)。首轮 Finding #1 reconcile 404=冒烟调错 URL(漏 ticket_id；路由存在 routes/execution.py:198)非缺陷，复验正确 URL 200 闭合 9/9（planner 校正 signoff RE-VERIFY addendum）。signoff `docs/test-reports/BL-B023-S1-trading-closed-loop-smoke-2026-06-08.md`。**下一批 HK-China(order 5，Master 4/4 真实)。**
- **B048-OPS1-alembic-deploy-reliability：✅ `done`**（2026-06-08，0 fix-round；B048 Finding #1/S2 resolved）。**根因确证**：env 未导出 WORKBENCH_DB_URL→alembic 跑 scratch DB + post-alembic schema-check 被 `if [[ -n VAR ]]` 静默跳过（B022 F014 同族）。修(deploy.sh 3 处)：env-url 空硬失败(堵 scratch)+ **deploy 后断言 alembic current==heads 硬失败**(durable 防线，根因无关)+ required 表加 0007-0011。L2 fresh deploy(run 27119352795) alembic==head(0011)无需手动，表全/API 正常，prod≡main HEAD e0c035c。signoff `docs/test-reports/B048-OPS1-alembic-deploy-reliability-signoff-2026-06-08.md`。
- **B048-real-risk-safety-layer：✅ `done`**（2026-06-07，0 fix-round；F011 安全层真实化）。price_history 深历史表(16500 行)+risk_panel master/per-sleeve DD 真实 mark-to-market(去成本价/去镜像)+kill_switch gate 真实(阈值 0.15 单一来源 nav_history)+wash_sale 真实检测；B023 不破。沉淀 v0.9.37(同一风控常数多处副本→单一来源+feature-grounding)。**Finding #1(alembic 未自动升级)→B048-OPS1；Soft-watch S1(cost_degraded price_history 不覆盖近期 snapshot 日期 low)**。signoff `docs/test-reports/B048-real-risk-safety-layer-signoff-2026-06-07.md`。
- **🎯 里程碑 C 路径（『所有页面接真实引擎』硬标准）**：B046(✅)→B048(✅)→B048-OPS1(✅)→BL-B023-S1(✅ §6 交易闭环)→HK-China(✅ Master 4/4)→B042/BL-B023-S2 Risk UI(✅6)→**B047 Backtest+Reports 真实引擎(7,building)**→**B049 全页面真实化审计 gate(8)**；B043 AI 解释并行。**里程碑 C §6 交易闭环 + Master 4/4 真实 + Risk UI 均已达成；余 回测/Reports 真实化(B047 进行中)+全页面审计(B049)+AI 解释(B043)。**详见 `docs/product/progress-review-2026-06.md` 覆盖矩阵 + backlog order。
- **B046-tradeable-diff-current-weight：✅ `done`**（2026-06-07，0 fix-round；交易闭环关键拼图）。**mark-to-market 可交易 diff 生效**：L2 PUT 浮盈持仓→position-diff AAPL 权重 成本 13%→**市价 23.47%**（涨幅 +$157 正确捕捉），total_equity 市价 NAV；rec current_weight 真实(SGOV 0.3835 非 0.0)；strategies 注册表对齐 master 4-sleeve(regime→research)；B023 工作流不破。signoff `docs/test-reports/B046-tradeable-diff-current-weight-signoff-2026-06-07.md`。**Soft-watch S1**：home nav=0.0(空账户未设标准 snapshot)low，留 BL-B023-S1 冒烟补。
- **B045-OPS1-trade-wheel-deploy-reliability：✅ `done`**（2026-06-07，0 fix-round，S4 resolved）。trade wheel `--force-reinstall --no-deps` + deploy 后 smoke import check（v0.9.36 铁律）；fresh deploy trade 0.2.0 自动匹配无需手动。signoff `docs/test-reports/B045-OPS1-trade-wheel-deploy-reliability-signoff-2026-06-07.md`。
- **B045-real-data-refresh-pipeline：✅ `done`**（2026-06-07，1 fix-round）。data-refresh pipeline 闭环：Tiingo prices 16500 行 + SEC EDGAR fundamentals 329 行 → VM unified CSV → trade loaders WORKBENCH_DATA_ROOT 覆盖 → precompute **data_source=mixed（3/4 sleeve real，satellite_hk_china by-design stub 无策略实现=现实天花板）**。/current 6 positions 真实权重。沉淀 v0.9.36。signoff `docs/test-reports/B045-real-data-refresh-pipeline-signoff-2026-06-07.md`。
- **B044-real-scoring-precompute：✅ `done`**。`/api/recommendations/current` equal-weight→Master 真实评分。**B046 待做：regime reconcile+account current_weight。**

## 已完成签收
- B001-B045 全部签收。

## 生产状态
- **B045 done：** prod `dfb5702` (trade 0.2.0 + fundamentals_sync)，timer auto-wired，data 19M (prices 1.1M+fundamentals 32K)，disk 84%。daily timer 每日 02:30 刷新。precompile data_source=mixed (1 sleeve_unavailable=hk_china 预期)。/current 6 pos / recent-errors=0。
- VM 运维：timer auto-wiring 就位；trade wheel deploy 需手动 force-reinstall(S4)。

## 永久硬边界
- B045 market data refresh (r) 只读 + §12.10.2 AST 守门 + data self-contained。

## Framework 状态
- **v0.9.39**（B034/BL-B011-S2 二例）：generator.md §12.10.3 **wheel `packages=[...]` 只打源码树，运行时非包数据须 force-include**（或 materialise 进包目录）+ 守门 + L2 fresh deploy 验不 stub。
- **v0.9.38**（B022/B045-OPS1/B048-OPS1 三例）：generator.md §12.11 **deploy 步骤必须 post-step assert 验证 intended end-state**（命令返回 0/守门通过 ≠ 成功）；统一 v0.9.36 smoke check。
- **v0.9.37**（B048）：README 同一风控常数多处副本→单一来源+feature-grounding。
- **v0.9.36**（B045）：README venv 多包安装 deploy 静默装不上 + smoke import check。v0.9.35（B044）：§12.10.2 物理缺席→AST 守门。

## 已知 gap
- 本机 python3=3.9.6，用 .venv/bin/python。
- GitHub Secret 全配齐。
