---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B070 building（F001+F002 ✅ done，F003 next，2026-06-19）** = A股 进攻策略去幸存者偏差重验。**§23 三关口=GO**（免费 baostock 能去偏，证伪 spec NO-GO 先验+`cn_universe.py` 付费 feed 说；多 agent verify=CONFIRM_GO）。**F002 去偏宇宙真建成功**：dated `query_{hs300,zz500,sz50}_stocks(date=)` 回溯 2007 → **29 季度×800 PIT 成分**（HS300∪ZZ500∪SZ50），union 1310/non-current 536，退市抽样 **12.5%**（小天鹅A/*ST泛海/ST阳光城…），non-current 占比 2019=**46.5%**→2026=5.6%。`trade.load_cn_universe` **零改读取**（小天鹅A 000418∈2019-03 宇宙=True=策略真见退市输家）。建 PIT + current-control 两宇宙。代码 `scripts/research/b070_survivorship_free.py`(纯逻辑+loader,19 单测)+build/fetch 脚本；runbook `docs/dev/B070-survivorship-free-universe-runbook.md`。1005 单测全绿，gated 研究 root 零生产回归。
- **【口径裁定（用户 2026-06-19）】**：F003 比 **PIT 去偏宇宙 vs current 对照宇宙**（同口径同成员数 800，唯一差=是否含退市/轮出名）→ 差值=纯幸存者偏差。**不**走 mcap top-N（退市名无免费 mcap 会重造偏差）。
- **【F003 续接】**：去偏宇宙 walk-forward 重跑 cn_attack（默认 equal,B069）→ 去偏 OOS vs 对照 OOS 量化幸存者偏差 + 判定『去偏后是否仍成立』。需全量价格(~1310 名 3-4h)→VM/长跑。复用 `run_cn_attack_wide_comparison` harness + b070 fetch 脚本。**§5**：F003 据 `tradestatus`/volume 剔停牌（退市名停牌~30%）、退市价记出场；CEILING=仅指数band去偏非完全。
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
