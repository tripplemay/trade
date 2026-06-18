---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B067 ✅ done**（2026-06-18，Codex F004 签收）= A股 进攻 P2（实盘 advisory surface + 手动执行闭环）。F001-F004 全部完成。上一批 B066 ✅ done。
- **B067 结论**：两 cn_attack advisory 模式（quality_momentum/pure_momentum）注册进 _MODES（FUNDING_RESEARCH）；每日 timer 03:30/03:40 UTC；cash 补权重=1.0；★cn_attack 专属 OOS 负/未验证披露红卡（validated=False，oos_result=negative，-9~-11%）；advisory-only/no-execute 全守门通过。L1 全绿（trade 961/backend 1458/safety 164/frontend 343）。VM HEAD=e95b08e。**★evaluator「SSH fail2ban 封锁」=误诊(用错 IP 162.14.96.221;真 VM 34.180.93.185 可达,§25 实例)**——planner 2026-06-18 实测:两 cn_attack timer **active+已排程**(首跑 2026-06-19 03:30/03:40 UTC,LAST=n/a 未触发)、ExecStart 从 service cwd import OK(将正常运行,配置同已工作 regime/recommendations timer)。4 项 operational 中 3 项(SSH 可达/timer active/会跑)已闭;仅真实 DB snapshot 待明天 timer 自然触发。
- **★诚实约束（spec §0 焊死）**：B066 OOS −9~−11% 动量逆转 + 质量 A/B 本地未分胜负（需宽宇宙）。advisory surface 须持续显示 OOS 负/未验证披露。
- **关键决策**：cn_attack 两 advisory 模式进 mode registry（非 master sleeve）。B066 backtest id `cn_attack_momentum_quality` 仍在 STANDALONE_RESEARCH 不动。

## 遗留 / soft-watch
- **~~SSH fail2ban~~ / ~~真 snapshot~~ 全部关闭(2026-06-18 planner 实测)**：真 VM=`34.180.93.185`(评估用错 IP=误诊)。planner 手动提前触发两 cn_attack precompute service→**both saved=25 行, as_of=2026-06-18, data_source=real, 无错误**(weight-sum=1.0 被 save_batch 守门反证=cash 补 1.0 真生效)。B067 operational 全闭。**用户现可用**:`astock.guangai.ai` /recommendations 切 cn_attack 两模式看真推荐(每日 timer 03:30/03:40 UTC 自动更新)。
- **质量 A/B 未分胜负**：种子宇宙 43 股全通质量门槛→需生产宽宇宙分化（未答）。
- **S1 全量 cross-source 待补**：B066 延用 B065 抽样结论；VM SSH 解封后可跑 ashare_quality_check.py 补。
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
