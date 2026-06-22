---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B074 building（生产 hotfix，铁律 9）** = cn_attack A股 模拟盘建仓修复。**★根因(planner VM 实测)**:两 cn_attack paper 账户激活有目标但 build_complete=0/全现金——price_snapshot(paper 价格源)0 个 A股(25 目标 0 可估价);A股 价在统一 CSV(data_refresh 写)但从没进 price_snapshot;prices/cli Tiingo(US-only)+price_universe 全美股不含 A股=双重缺口。§17.1+B058 regime 同款。**修=方案 A**:A股 收盘从统一 CSV 同步进 price_snapshot(非 Tiingo)→paper 能估价建仓。3 features 2g+1c:F001 A股 价同步/F002 acceptance 守门(paper 目标可估价永不复发,复用测试基建)+建仓/F003 Codex L2 真机(两模拟盘 build_complete=1+持仓+cash≈0)。spec docs/specs/B074-...-spec.md。研究态 paper(无真金),不改 cn_attack 策略本身。
- **B073 ✅ done（2026-06-22，Codex F003 PASS）** = 测试自动化 Phase 2.1（VCR 录放 + AI Safety Eval 网关韧性）。F003:mutation N/O/P/Q 全红(安全门有牙齿)+§0 安全门未削弱核实+断网 56/56 绿。F001 VCR(vcrpy 3 httpx loader+akshare/yfinance frame,CI 离线确定性)/F002 网关韧性(VCR'd 确定性 red-team 硬门+live eval 区分 infra-unreachable vs advisor-unsafe)。**🎯韧性被真实故障当场验证**:CI 实测网关 402→INFRA_SKIP(绿,不拖红 deploy gate)。signoff docs/test-reports/B073-...-signoff-2026-06-22.md。**【测试基建 B071-B073 三批地基已厚:golden 真数据+验收即代码+全栈 e2e 闭环+可注入时钟+VCR 离线+eval 网关韧性。】**
- **⚠️ ops:网关 402 Payment Required = 余额耗尽(2026-06-22 CI 实测)**:**生产 AI 功能(推荐解释/新闻翻译/advisor)当前不可用,需用户充值 aigc-gateway**;充值后 live eval+生产 AI 自动恢复。B073 F002 已让此 402 在 live red-team eval 中 INFRA_SKIP(非红,advisor 逻辑未变)而非拖红 deploy gate。
- **B072 ✅ done（2026-06-21）** = Phase 2 核心(golden 全栈 CI seed_golden_e2e.py 推 4 表 + e2e 交易闭环 b072-closed-loop.spec.ts=BL-B023-S1 自动化 + 可注入时钟 8 timer --as-of 共享 cli_clock.py)。无 prod-affecting。signoff docs/test-reports/B072-...-signoff-2026-06-21.md。

## 遗留 / soft-watch
- **F002 合规**：避 no-execution 禁词（EN execute/place order/send to broker；ZH 执行/下单/实盘等）；新 spec 须加入 playwright.config.ts authed testMatch；fills CSV generic 格式小额买单+allow_unmatched，reconcile 1M cash 不超卖。
- **F003 clock-seams**：paper/mtm+advisor+prices+canonical 干净 seam（加 flag 即可）；precompute 簇（recommendations/regime/cn_attack）需 plumb as_of 入价格 cutoff（precompute.py:248/262 硬 now）。
- **B070 follow-on（非本批）**：2 因子去偏 baostock；港股 P3（backlog B055）。A股 进攻 P3 / hk_china 重测在池。

## 永久硬边界
- B045 market data refresh (r) 只读 + §12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- golden 只进测试 fixture seam（fixture_dir / 测试 DB seed），不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 4 版）
- **v0.9.49**（B071）：generator.md §30 复权口径一致 / §31 验收即代码常态化 / evaluator.md §30 verifying 跳 L1。
- **v0.9.48**（B066）：§28 停牌 ffill+NaN 安全读价 / §29 多变体退化空仓必须红旗。
- **v0.9.47**（B065）：§19.1 ruff 本地须目录上下文 `python -m ruff check .`。
- **v0.9.46**（B064）：§27 前端「本机绿≠CI 绿」二坑。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade）。golden 必须落 `data/fixtures/**` 才 commit。
