---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B066 ✅ done**（2026-06-18，0 fix-round）；**上一批：B065 ✅ done**（2026-06-18）。
- **B066 = A股 进攻型动量+质量选股 P1（research-only）**：F001 引擎+cn universe loader+2 因子变体 / F002 每日驱动+不动区+3 退出变体+方向化成本（印花税仅卖）/ F003 B050 接线+回测页+6 变体对比报告+沪深300 基准 / F004 Codex 验收 ✅。
- **研究判定（诚实）**：引擎正确，全窗口 CAGR **10.2% > 沪深300 8.94%**（小胜），但 **OOS（2025H2 起）CAGR −9~−11% = 动量逆转**（A股 切防御风格→动量崩溃，诚实披露无 cherry-pick）。**P2 实盘 advisory 建议等 ≥6 个月正向 OOS 再推进**。signoff `docs/test-reports/B066-...-signoff-2026-06-18.md`。
- **关键决策**：cn_attack = STANDALONE_RESEARCH（不入 Master/PAPER/INACTIVE，回测页可跑研究态）；纯进攻无 regime gate（吸取 hk_china_real 全防御教训）。

## 遗留 / soft-watch
- **质量 A/B 未分胜负**：种子宇宙 43 股全通质量门槛→「质量+动量」≡「纯动量」，"质量是否加值" **需生产宽宇宙才分化**（未答）。
- **S1 全量 cross-source 待补**：B066 延用 B065 抽样结论（未改价格逻辑=合理）；全 universe baostock 复确认待 VM 真跑（S2 SSH 本会话已恢复）。
- **S3 已处理**：akshare eastmoney `stock_zh_a_hist` 端点 VM 不可达 → B066 F001 已 fold sina `stock_zh_a_daily` fallback（B062 同款）。
- **P2/P3**：P2（实盘 advisory surface=每日推荐/调仓/获利了结）待 OOS 正向证据；P3 港股扩。backlog B055 记 A股 进攻 P2/P3 路线。

## 永久硬边界
- B045 market data refresh (r) 只读 + §12.10.2 AST 守门 + data self-contained。
- research-safe / no-broker（只接 akshare/baostock 不接券商 SDK）/ no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy（live 推荐未碰）。

## Framework 状态（最新 4 版；更早见 framework/CHANGELOG.md）
- **v0.9.48**（B066）：generator.md §28 回测引擎停牌 ffill+NaN 安全读价禁 `or 0.0`+缺价回归测试 / §29 多变体报告退化空仓必须红旗（no_activity+同族 toggle 失效）。
- **v0.9.47**（B065）：generator.md §19.1 ruff 本地须目录上下文 `python -m ruff check .`。
- **v0.9.46**（B064）：generator.md §27 前端「本机绿≠CI 绿」二坑（货币显示确定性符号前缀 + 测试 waitFor 等目标元素）。
- **v0.9.45**（B061+B062+B063）：★evaluator FULL PASS 系统性退化三实例→§25.1+§29 实测证据硬段+planner done §1.5 强制复核（流程修复）+§23 新端点须实跑+§24 决策级 harness 复审 等。

## 已知 gap
- 本机 python3=3.9.6，用 .venv/bin/python；ruff 本地须 `python -m ruff check .` 目录上下文。
- GitHub Secret 全配齐。prod=B064 系（A股+港股 lookup 上线）。
