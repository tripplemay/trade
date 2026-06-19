---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B070 verifying（F001+F002+F003 ✅ 三 generator done → Codex F004 验收，2026-06-19）** = A股 进攻去幸存者偏差重验。**★核心结论：去掉幸存者偏差后,A股 动量进攻策略仍成立(SURVIVES_DEBIASING)但表观 OOS 虚高约一倍。** F003 真数据(全量 1310 名 2.47M 行价格含 52 退市名)PIT 去偏 vs current 对照(pure_momentum+equal,WF 70/30)：**PIT OOS CAGR 28.4%/Sharpe 0.93(仍正)** vs 对照 55.0%/1.45 → **幸存者偏差高估 OOS CAGR +26.6pp、Sharpe +0.52**(全样本 +15.7pp)。报告 `docs/test-reports/B070-survivorship-comparison.md`。
- **F001 §23=GO**（免费 baostock dated 成分能去偏，证伪付费 feed 说；多 agent verify=CONFIRM_GO）。**F002 去偏宇宙真建**：29 季度×800 PIT(回溯 2007)，union 1310/退市 52(小天鹅A/*ST泛海/ST阳光城…)，`trade.load_cn_universe` 零改读取。建 PIT + current-control 两宇宙隔离单变量。代码 `scripts/research/b070_*`(judge+builder+comparison 31 单测)。
- **【F003 多 agent verify=CONFIRM_WITH_DISCLOSURES，纠正 generator 误判】**：①exits=0=momentum_decay 结构性非 bug;②退市估值伪命题:引擎 _wide() **ffill 冻结最后成交价(非计 0)**，ffill-vs-计0 实测**完全一致**→零影响，**+26.6pp 为下界**;③52 退市名 43 *ST 真崩(正确拖累 PIT)全在 PIT/0 在对照。**诚实**:正 OOS 主来自 2024Q4『924』反弹落 OOS 窗口(OOS Sharpe>IS 窗口落位假象);仅 pure_momentum(退市名无免费 quality 基本面=follow-on);仅指数band去偏;仍研究态不可配资。
- **【F004 Codex 验收 carry】**：VM 复跑确认数字 + 复验退市估值 null result + 对照构造有效性 + 修正披露已入 .md（详见 progress.json session_notes.generator）。
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
