---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B069 ✅ done（2026-06-19，NO-SWITCH 维持 equal）** = B068 follow-up。planner『验证→确认改善才切』诚实设计奏效:generator 跑 committed B068 harness 于全真宽数据(393名/250期 walk-forward)→**inverse_vol 不支持切**(OOS Sharpe quality 1.88→1.78/pure 1.72→1.65 两模式更差,CAGR 更差,换手/成本更高,唯 quality 回撤少挖~3pp)→印证 equal 1/N 难被权重优化打败。F002 不改产品代码(precompute 续 equal 字节级零回归)+守门单测焊死 equal;Codex F003 NO-SWITCH PASS。决策依据 docs/dev/B069-inverse-vol-default-decision.md+报告 docs/dev/B068-wide-comparison-report.md 入 git。signoff docs/test-reports/B069-cn-attack-no-switch-signoff-2026-06-19.md。
- **B068 ✅ done**（2026-06-19 用户自验置 done，无 Codex signoff）= A股 宽宇宙重验。报告 `docs/dev/B068-wide-comparison-report.md`（committed harness，全真宽数据 393名/250期，2019-04→2026-06）。
- **B068 研究结论（真数字 OOS）**：**Q1 质量加值=是(仅风险调整)**(quality OOS Sharpe 高+0.15/+0.13,CAGR 略低)；**Q2 波动倒数=不值得换**(inverse_vol OOS Sharpe/CAGR 更差→印证 equal 1/N 基线)；**Q3 表面不脆弱**(OOS CAGR 62~77%,B066 −9~−11% 未复现)。**★诚实警示:OOS 高=幸存者偏差+2024Q4 顺风 双重高估,不足证稳健**;红旗 IS≠OOS winner。weighting_scheme F002 已落代码(默认 equal 零回归)。
- **B068 F001 实测（§23=GO）**：sina `stock_zh_a_spot` 可达=宽 superset 端点（eastmoney push hosts 全挂）；宽宇宙真建 **513 superset→250 成员/期×29 季度,0 fetch error,393 distinct,LEAKAGE=0**。commit d5a60c1 已部署。**sina gated 于 allow_sina_fallback(默认 False)→生产 daily refresh 字节级不变,B067 读 seed-43 宇宙不动**。runbook: docs/dev/B068-wide-universe-runbook.md；产物本地 data/research/b068/(gitignored)。
- **上一批 B067 ✅ done**（2026-06-18，Codex 签收）= A股 进攻 P2（两 cn_attack advisory 模式进 _MODES，timer 03:30/03:40 UTC，cash 补 1.0，OOS 负/未验证红卡，advisory-only 全守门）。真 VM=`34.180.93.185`。B066 ✅ done。
- **★诚实约束（spec §0 焊死）**：advisory surface 须持续显示 OOS 负/未验证披露（B068 OOS 强劲但受幸存者偏差高估，不撤披露）。B067 默认维持 equal。

## 遗留 / soft-watch
- **~~SSH fail2ban~~ / ~~真 snapshot~~ 全部关闭(2026-06-18 planner 实测)**：真 VM=`34.180.93.185`(评估用错 IP=误诊)。planner 手动提前触发两 cn_attack precompute service→**both saved=25 行, as_of=2026-06-18, data_source=real, 无错误**(weight-sum=1.0 被 save_batch 守门反证=cash 补 1.0 真生效)。B067 operational 全闭。**用户现可用**:`astock.guangai.ai` /recommendations 切 cn_attack 两模式看真推荐(每日 timer 03:30/03:40 UTC 自动更新)。
- **B068 follow-up**：①据结论(equal 维持)无需调 B067 默认；②宽宇宙幸存者偏差需付费历史成分股 feed 才能消除（OOS 高估根因）；③S1 全量 cross-source 仍延用 B065 抽样（VM 可达可补）。
- **P3**：港股扩待 P2 后；backlog B055 记路线。

## 永久硬边界
- B045 market data refresh (r) 只读 + §12.10.2 AST 守门 + data self-contained。
- research-safe / no-broker（只接 akshare/baostock）/ no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。

## Framework 状态（最新 4 版）
- **v0.9.48**（B066）：generator.md §28 回测引擎停牌 ffill+NaN 安全读价禁 `or 0.0`+缺价回归测试 / §29 多变体报告退化空仓必须红旗。
- **v0.9.47**（B065）：generator.md §19.1 ruff 本地须目录上下文 `python -m ruff check .`。
- **v0.9.46**（B064）：generator.md §27 前端「本机绿≠CI 绿」二坑。
- **v0.9.45**（B061+B062+B063）：★evaluator FULL PASS 系统性退化三实例→§25.1+§29+§23+§24 等。

## 已知 gap
- 本机 python3=3.9.6，用 .venv/bin/python；ruff 本地须 `python -m ruff check .` 目录上下文。
- GitHub Secret 全配齐。prod=B067 系（A股进攻 P2 advisory surface 上线）。
