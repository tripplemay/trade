---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B070 building（F001 ✅ done，2026-06-19）** = A股 进攻策略去幸存者偏差重验（feasibility-first）。**§23 三关口 = GO**：免费源 **baostock 能去幸存者偏差**（违反 spec「很可能 NO-GO」悲观先验）。实测：dated `query_{hs300,zz500,sz50}_stocks(date=)` 本机可达（baostock 自有 host，非 akshare push host），成分回溯 **2007**，真 PIT（HS300 跨 19yr 换 226/300）且**含已退市名**（1914 ever/800 current；武钢/葛洲坝/退市长油…确证退市）；退市名 k 线 `query_history_k_data_plus` 可拉（右删失到 outDate，乐视 17.89→1.69，4/4）；规模 ~14s/名→3-4h/800名 gated 研究态。akshare `index_stock_cons*` 无 date（current-only）→ baostock 是唯一免费使能源。**证伪 `cn_universe.py:33`『需付费 feed』**。多 agent verify=**CONFIRM_GO**（独立复现新名/新日期）。产物：probe `scripts/research/b070_feasibility_probe.py` + 报告 `docs/dev/B070-feasibility-report.md`（含 §5 carry-into-F002 硬约束）+ 单测 `tests/unit/test_b070_feasibility_judge.py`（7 pass）。gates 全绿。
- **【F002 续接 — 须照报告 §5 硬约束，否则从另一扇门重造偏差】**：①STOP-BIAS 停牌非尾部（乐视 29.6%/康得 26.5% 零成交）→ 信号+成交都剔停牌、退市价记出场；②CEILING baostock 只有 hs300/zz500/sz50（无 zz1000/zz800）→ 只在指数band去偏、**非完全去偏**；③MCAP-RANK GAP 退市名无免费历史 mcap → **别走 mcap top-N**（会重造偏差），最安全=「B068 宇宙+补退市名」隔离单变量 或 只按 amount 排序并标注；④成分端点瞬时空返回 err0 → loader 须断言 n 在band+退避重试；⑤持一 session+按 updateDate 缓存；⑥更新 cn_universe.py:33 docstring。复用 `cn_provider.py`（已含 baostock fallback + `adjustflag=2` qfq 锁测 `test_cn_provider.py:177`）。
- **B069 ✅ done**（NO-SWITCH 维持 equal）：committed B068 harness 跑全真宽数据（393名/250期）→ inverse_vol 不支持切（OOS 两模式更差）→ 印证 equal 1/N 难被权重优化打败。守门单测焊死 equal，precompute 续 equal 零回归。
- **B068 ✅ done** = A股 宽宇宙重验（report `docs/dev/B068-wide-comparison-report.md`，393名/250期）。**研究结论**：质量加值=是（仅风险调整）；波动倒数不值得换；OOS CAGR 62-77% 但**幸存者偏差+2024Q4 顺风双重高估**（B070 正在攻幸存者偏差这一半）。
- **B067 ✅ done**（A股 进攻 P2 advisory 上线）。真 VM=`34.180.93.185`。prod=B067 系。
- **★诚实约束（spec §0 焊死）**：advisory surface 持续显示 OOS 负/未验证披露；B070 去偏只消除幸存者偏差，**不**触及 2024Q4 顺风 → 披露续挂。默认维持 equal。

## 遗留 / soft-watch
- **B070 F002/F003 待做**（GO 已解锁）；F004 Codex 在 VM 复跑三关口+去偏宇宙真建+去偏 vs 偏差 OOS。
- S1 全量 cross-source 仍延用 B065 抽样（VM 可达可补）；港股 P3 待 P2 后（backlog B055 记路线）。

## 永久硬边界
- B045 market data refresh (r) 只读 + §12.10.2 AST 守门 + data self-contained。
- research-safe / no-broker（只接 akshare/baostock）/ no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。

## Framework 状态（最新 4 版）
- **v0.9.48**（B066）：generator.md §28 停牌 ffill+NaN 安全读价禁 `or 0.0` / §29 多变体退化空仓必须红旗。
- **v0.9.47**（B065）：generator.md §19.1 ruff 本地须目录上下文 `python -m ruff check .`。
- **v0.9.46**（B064）：generator.md §27 前端「本机绿≠CI 绿」二坑。
- **v0.9.45**（B061+B062+B063）：★evaluator FULL PASS 系统性退化三实例→§25.1+§29+§23+§24。

## 已知 gap
- 本机 python3=3.9.6，用 .venv/bin/python；ruff 本地须 `python -m ruff check .`。**baostock 已装入根 .venv**（B070 F001，pyproject 早声明 backend dep `baostock>=0.8.8`）。GitHub Secret 全配齐。
