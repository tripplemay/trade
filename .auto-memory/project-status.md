---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B048-real-risk-safety-layer：`building`**（2026-06-07 启动；F011 根因批次；里程碑 C 交易安全/风控/合规层真实化，order 2；**大批次 5 features**）。让安全层从占位变真：kill_switch gate(去硬编码 pass)+risk_panel master/per-sleeve DD mark-to-market 随时间(去成本价/去镜像)+wash_sale(去永空)。**决策（★用户批）：一次做全含历史价格表**（per-sleeve 回撤随时间需历史价格重建 NAV 历史；price_snapshot 只存最新+前一日）。planner 决：新 `price_history` 表(深每日，job 从 B045 unified CSV materialize)+kill_switch 阈值统一 0.15+mark-to-market 复用 B046+历史不足 degrade。5 features：**(F001 g ✅ done)** price_history 深历史表+repo(close_on_or_before 容缺/since)+backfill job(B045 unified CSV→表，幂等/malformed 跳/缺 CSV 空)+scope 守门(第 7 scheduler 包)，testsuite 881/ruff/mypy 0；(F002 g)sleeve tag 写路径补齐；(F003 g)risk_panel mark-to-market 回撤+kill_switch gate 真实+阈值 0.15；(F004 g)wash_sale；(F005 c)L2+signoff。**风险**：大批次+改 execution 写路径/risk/gate 触 B023 敏感→回归绿+L2 端到端。spec `docs/specs/B048-real-risk-safety-layer-spec.md`。
- **B048-OPS1-alembic-deploy-reliability：✅ `done`**（2026-06-08，0 fix-round；B048 Finding #1/S2 resolved）。**根因确证**：env 未导出 WORKBENCH_DB_URL→alembic 跑 scratch DB + post-alembic schema-check 被 `if [[ -n VAR ]]` 静默跳过（B022 F014 同族）。修(deploy.sh 3 处)：env-url 空硬失败(堵 scratch)+ **deploy 后断言 alembic current==heads 硬失败**(durable 防线，根因无关)+ required 表加 0007-0011。L2 fresh deploy(run 27119352795) alembic==head(0011)无需手动，表全/API 正常，prod≡main HEAD e0c035c。signoff `docs/test-reports/B048-OPS1-alembic-deploy-reliability-signoff-2026-06-08.md`。
- **B048-real-risk-safety-layer：✅ `done`**（2026-06-07，0 fix-round；F011 安全层真实化）。price_history 深历史表(16500 行)+risk_panel master/per-sleeve DD 真实 mark-to-market(去成本价/去镜像)+kill_switch gate 真实(阈值 0.15 单一来源 nav_history)+wash_sale 真实检测；B023 不破。沉淀 v0.9.37(同一风控常数多处副本→单一来源+feature-grounding)。**Finding #1(alembic 未自动升级)→B048-OPS1；Soft-watch S1(cost_degraded price_history 不覆盖近期 snapshot 日期 low)**。signoff `docs/test-reports/B048-real-risk-safety-layer-signoff-2026-06-07.md`。
- **🎯 里程碑 C 路径（『所有页面接真实引擎』硬标准）**：B046(✅)→B048(✅)→**B048-OPS1**(building,order3)→BL-B023-S1(闭环冒烟)→HK-China→B042/BL-B023-S2(Risk UI)→B047(Backtest+Reports 真实引擎)→**B049**(全页面真实化审计 gate)；B043 AI 解释并行。详见 `docs/product/progress-review-2026-06.md` 覆盖矩阵 + backlog order。
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
- **v0.9.38**（B022/B045-OPS1/B048-OPS1 三例）：generator.md §12.11 **deploy 步骤必须 post-step assert 验证 intended end-state**（命令返回 0/守门通过 ≠ 成功；守门条件不静默跳过关键步骤）；统一 v0.9.36 smoke check。
- **v0.9.37**（B048）：README 同一风控常数多处副本→单一来源+feature-grounding。
- **v0.9.36**（B045）：README venv 多包安装 deploy 静默装不上 + smoke import check。v0.9.35（B044）：§12.10.2 物理缺席→AST 守门。

## 已知 gap
- 本机 python3=3.9.6，用 .venv/bin/python。
- GitHub Secret 全配齐。
