---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B070 ✅ done（2026-06-19，Codex SURVIVES_DEBIASING PASS）** = A股 进攻去幸存者偏差重验。**★核心结论：去偏后策略仍成立但只是"边际为正"、不可配资。** PIT 去偏(全量 1310 名/52 退市,pure_momentum+equal,WF 70/30)**OOS CAGR 28.4%/Sharpe 0.93(仍正,非纯幻觉)** vs 对照 55.0%/1.45 → 幸存者偏差高估 +26.6pp(下界)。🎯免费 baostock 带日期成分+退市价格够去偏(证伪付费 feed 说)。**★诚实警示(多 agent 复审钉死)**:正 OOS 主因 2024Q4『924』反弹落 OOS 窗口=窗口落位假象(OOS Sharpe 0.93>IS 0.39),边际为正非可配资证据;仅 pure_momentum;仅指数 band;仍研究态。报告 docs/test-reports/B070-survivorship-comparison.md+signoff。**【A股 进攻 B066→B070 五批调查收官:真实但微弱未稳健 edge,能研究不可押真金;全程守诚实。】**
- **F001 §23=GO**（免费 baostock dated 成分能去偏，证伪付费 feed 说；多 agent verify=CONFIRM_GO）。**F002 去偏宇宙真建**：29 季度×800 PIT(回溯 2007)，union 1310/退市 52(小天鹅A/*ST泛海/ST阳光城…)，`trade.load_cn_universe` 零改读取。建 PIT + current-control 两宇宙隔离单变量。代码 `scripts/research/b070_*`(judge+builder+comparison 31 单测)。
- **【F003 多 agent verify=CONFIRM_WITH_DISCLOSURES，纠正 generator 误判】**：①exits=0=momentum_decay 结构性非 bug;②退市估值伪命题:引擎 _wide() **ffill 冻结最后成交价(非计 0)**，ffill-vs-计0 实测**完全一致**→零影响，**+26.6pp 为下界**;③52 退市名 43 *ST 真崩(正确拖累 PIT)全在 PIT/0 在对照。**诚实**:正 OOS 主来自 2024Q4『924』反弹落 OOS 窗口(OOS Sharpe>IS 窗口落位假象);仅 pure_momentum(退市名无免费 quality 基本面=follow-on);仅指数band去偏;仍研究态不可配资。
- **【F004 Codex 验收 carry】**：VM 复跑确认数字 + 复验退市估值 null result + 对照构造有效性 + 修正披露已入 .md（详见 progress.json session_notes.generator）。
- **B069/B068 ✅ done**：B068 宽宇宙重验(质量=仅风险调整;OOS CAGR 62-77% 但幸存者偏差+2024Q4 顺风双重高估,**B070 已攻幸存者偏差这一半=砍 OOS 约一半**);B069 NO-SWITCH 维持 equal(inverse_vol 不支持切)。**B067 ✅** A股 进攻 P2 advisory 上线,真 VM=`34.180.93.185`,prod=B067 系。
- **★诚实约束（spec §0 焊死）**：advisory 持续显示 OOS 负/未验证披露；B070 去偏只消幸存者偏差,**不**触及 2024Q4 顺风 → 披露续挂；默认维持 equal。

## 遗留 / soft-watch
- **B070 follow-on(非本批)**：2 因子(quality)去偏需 baostock 基本面管线(query_profit/balance_data,退市名 fcf_yield 缺)；港股 P3(backlog B055)。S1 cross-source 延用 B065 抽样。

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
