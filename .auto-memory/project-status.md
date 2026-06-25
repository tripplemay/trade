---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B077 ✅ done（2026-06-25，CLI代Codex F003 INCONCLUSIVE_COVERAGE_LIMITED）** = A股 聪明钱数据可行性摸底。**整体 NOT GO 本批**：北向 ELIMINATED（live 冻结 2024-08-16/678+d，经典跟北向已死）；主力资金流 HOLD-NOT-GO（0.5y 太浅 can_support_backtest=False）；龙虎榜机构席位 INCONCLUSIVE_COVERAGE_LIMITED（rank-IC 0.018-0.023 < 0.03 + 驼峰非单调 + 80.8% 小盘未覆盖）。**决定性下一步**=补小盘价格覆盖重跑 first-look（80.8% 机构 LHB 事件小盘未覆盖 B070，不能据 19.2% 断言全无信号）。**★北向独立抽查 2026-06-25 今日确认仍冻结**。signoff docs/test-reports/B077-cn-attack-smart-money-signoff-2026-06-25.md。
- **⚠️ B077 本会话另修预存 date-bomb（与 B077 无关）**：cn/hk/yfinance get_quote 用真实 datetime.now()+固定 fixture 日期→2026-06-23 起 Backend CI 红。用户确认后 clock-injectable fix(commit 6f54e35),Backend CI 已绿,deploy 链已跑。
- **cn_attack 方向(冻结观察)**：B068-B076 共 4 次诚实 NO-GO/NO-SWITCH(质量/波动率倒数/幸存者/size-tilt)→简单版(蓝筹+等权+动量质量)edge 微弱不稳健;宽宇宙(B075)+模拟盘(B074)作研究展示基础设施留存,生产未再改。B077 聪明钱方向是全新方向（信息流族 vs 因子族）。
- **B076 ✅ done（2026-06-24）** = cn_attack size-tilt 选股，独立裁定 NO-GO(去偏全样本 Sharpe 0.56→max0.42)。signoff docs/test-reports/B076-cn-attack-size-tilt-signoff-2026-06-24.md。★survivor=GO/去偏=NO-GO 幸存者偏差镜像，spec §0 铁证。
- **B075 ✅ done（2026-06-22）** = A股 生产股票池扩大到全市场流动 top ~1501。workbench-cn-universe.timer 每周日 06:00 自动重建。
- **⚠️ ops: 网关 402 out-of-credit（2026-06-22）**：生产 AI 功能（推荐解释/新闻翻译/advisor）不可用，需充值 aigc-gateway。

## 遗留 / soft-watch
- **聪明钱方向决定性下一步**：补小盘价格覆盖（B070 宇宙外 47654 事件个股），含小盘去偏样本重跑 first-look LHB 机构席位 IC。GO→下批搭策略+全回测；仍 NO-GO→诚实劝退。
- **cn_attack 宽池 top-25 与种子 43 重叠**：大盘蓝筹偏差，预期行为，B075 诚实标注。
- **B070 follow-on**：2 因子去偏 baostock；港股 P3（backlog B055）。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- golden 只进测试 fixture seam（fixture_dir / 测试 DB seed），不碰生产 data_root/unified 真数据路径。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资（B075 未改策略）。

## Framework 状态（最新 4 版）
- **v0.9.52**（B076）：generator.md §35 baostock turn 补退市名市值 + survivor/去偏双 cut / planner.md §策略-改动 verdict 设计(全样本+OOS 双门禁)。
- **v0.9.51**（B075）：environment.md VM /tmp PYTHONPATH / generator.md §33 可行性探针复用真 loader / §34 宽集 partial-failure exit-code 容忍。
- **v0.9.50**（B074）：generator.md §32 paper 搁浅现金诊断 / planner.md §根因诊断。
- **v0.9.49**（B071）：generator.md §30 复权口径一致 / §31 验收即代码常态化 / evaluator.md §30 verifying 跳 L1。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade）。
