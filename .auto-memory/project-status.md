---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B068 ✅ done**（2026-06-19，用户自验指示置 done，覆盖状态机；research-only；无 Codex F004 signoff）。F001+F002+F003 harness 入 git。**★4 配置对比报告已补入 git**：`docs/dev/B068-wide-comparison-report.md`（generator 跑 committed harness 于全真宽数据 2019-04→2026-06，393 名/250 期）。
- **B068 研究结论（真数字，OOS 2024-04→2026-06）**：**Q1 质量加值=是(仅风险调整)**——quality OOS Sharpe 两权重均高(+0.15/+0.13)，CAGR 略低。**Q2 波动倒数=不值得换**——inverse_vol OOS Sharpe 略降、回撤改善微弱不稳→印证 equal(1/N)稳健基线。**Q3 不脆弱(表面)**——4 配置 OOS 全正(CAGR 62~77%/Sharpe 1.65~1.88,远超 CSI300 3%)，B066 −9~−11% 未复现。**★诚实警示**：OOS 高 = **幸存者偏差(当前在市名单回溯)+ 2024Q4 顺风行情** 双重高估，不足证稳健。**对 B067 建议(本批不改)：维持 equal 默认**(inverse_vol 无值得换优势)。红旗:IS≠OOS winner(不 cherry-pick)。
- **F002 ✅**：CnAttackParameters 加 weighting_scheme∈{equal(默认),inverse_vol};construction inverse_vol=∝1/σ(σ 复用 us_quality trailing_volatility,中位数插补缺σ,无σ降级等权);hash 条件 payload→equal-default 字节级零回归;signal equal 路径零开销。commit b74183e 已部署。backend cn_attack 105 passed=B067 surface 零回归。
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
