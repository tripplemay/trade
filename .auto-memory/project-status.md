---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B083 ✅ done（2026-07-05, round1 一轮闭环）** PEAD/业绩预告 first-look(评审 P1 排序 2, 新信号族) = 全 3 features PASS。独立验收(代 Codex,与实现隔离): **命门(前视/时点)全过** — 独立复算(不import generator)lookahead_violations=0 + 手工3事件核对 entry严格>公告日、**用公告日非报告期末进场**; IC 三条独立路径(直读CSV/searchsorted/numpy-Spearman)4位小数精确吻合(N1+0.021/N5-0.021/N10-0.076/N20-0.057 可执行,8235事件); 惊喜单一先验无扫参; 覆盖率23.0%/1152标的诚实披露(大盘宇宙偏差); **INCONCLUSIVE=与数字一致的合法裁定**(不达GO门槛|IC|>0.03+同号+单调; 审证据质量非方向); migration 0038生产落地(deploy链证明)+门禁全绿+HEAD≡prod(8b01d79)+零回归. trial_registry 登记DSR N. signoff docs/test-reports/B083-pead-first-look-signoff-2026-07-05.md。**backlog follow-up(若续)**: 全A宽宇宙+实际快报惊喜+分析师一致预期SUE 重跑IC。
- **B082 ✅ done（2026-07-05, round1 闭环）**(红利低波防守腿 3g+1c, cn_dividend_lowvol 研究态)。独立验收(代 Codex)：F002 数字独立重实现逐位复现(策略 7.49%/-40.5% vs 持有 10.64%/-66.2%,规则减回撤不增收益)、阈值无扫参、2024-02 真 HS300 -6.1%、探针重fetch、alembic 0037/trial B082=6/OOS card validated=0·mixed、零回归、no-execution。**r1 阻断 ISSUE-1(生产 live 数据未落地)经 c53375f 修复**(dividend_lowvol 前移到 Tiingo run_refresh 之前,run_refresh 零改动 exit-code 不变,2 隔离单测)。生产实证: 5 CSV 落地+快照 data_source=real tier=full spread 2.7589%(与预测逐位吻合)+512890.SH 5 marks。paper 未激活=诚实边界(激活属用户动作,precompute 不自动激活)。signoff docs/test-reports/B082-...-signoff-2026-07-05.md。**遗留(backlog)**: fx/benchmark/universe 仍在 run_refresh 后同 Tiingo-独立性病未治(commit 0b23e46 具体化)。
- **B081 ✅ done（2026-07-04）**(cn_attack 回测引擎修真) = 全 5 PASS(两轮闭环)。6 高估源各带开关，旧口径 bit 级复现 B070。红卡改**资本条件化**(-16.0%@10万/+27.1%@100万纯保真,validated恒False,source=b081_f005_capital_conditioned)。生产 alembic=0036/trial B081=14。signoff docs/test-reports/B081-...-signoff-2026-07-04.md。
- **B080 ✅ done** 策略生命周期监控(trial 27 回填 migration 0033/周timer/paper 三口径)。**B079 done** 标的名。**B078 done** refresh 卡死。**B077 NOT-GO**。B076/B075/B074 done。
- **B084 🔨 building（2026-07-05 开批）** A股 ETF 时序趋势轮动(评审 P2, global_etf_momentum 改造 工作量最小)。first-look 低承诺=趋势胜率/夏普一测;核心不变量=参数先验禁扫参+★2022/2024-02 震荡损耗分窗口报(趋势最大陷阱)+ETF无印花税+时序动量非横截面。数据复用 B082 ETF 管线。3 features(2g F001数据/F002趋势IC + 1c F003)。B083 done 后无并发 planner→本 session 接手开批。
- **接续**：backlog ~10 项(cn_attack 信号升级[预研81335f5备]/A股数据源/聪明钱/hk_china retest/test-automation/B055/vol-target/VIX/bootstrap-seed 等)。B081/B082/B083 follow-up(partial=True/refresh fx+benchmark 前移/PEAD 全A宽宇宙+快报SUE)待 planner 并入。learnings 队列待用户确认。

## 遗留 / soft-watch
- **B081 快照自愈**：cn_attack advisory 快照 daily timer 07-05 03:40 UTC 重算入新纯保真口径(部署不触发 timer)；权威红卡表已更正，建议 07-05 后 spot-check 快照 caveat==卡片表。partial_rebalance=True 策略变体留独立 verdict 批次。
- **B080 F004 坑**：api.ts 加带默认值字段仍 TS-required → 前端 fixture tsc 红；api.ts 与 fixture 须**同 commit**(见 proposed-learnings)。
- **★聪明钱方向**：backlog `B0XX-ashare-smart-money-following`，结论存docs/research/。
- **B070 follow-on**：2因子去偏baostock；港股P3（backlog B055）。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 4 版）
- **v0.9.54**（B078）：generator.md §38 宽集刷超时含 bulk discovery / §39 paper round-trip 成本 / §40 静默冻结守门 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。
- **v0.9.52**（B076）：§35 baostock 补退市名市值 + 双 cut / planner.md 策略改动双门禁 verdict。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
