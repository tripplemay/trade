---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B067 🔍 verifying**（2026-06-18，Codex 接 F004）= A股 进攻 P2（实盘 advisory surface + 手动执行闭环）。**F001+F002+F003 ✅ done（推 main，CI 绿），F004=Codex L2 真机验收待做**。上一批 B066 ✅ done。
- **B067 进度**：F001/F002 ✅（模式接入+precompute+cash 补 1.0+OOS meta；timer/CLI/scope safety，deploy glob 零改）；**F003 ✅**（后端暴露 typed `research_caveat`+获利了结读 `master_meta.profit_take` 标注 diff reason；前端 `CnAttackOosDisclosure` 红卡按 research_caveat self-gate+双语+引用 B066；no-execution 注册+api.ts 重生；门禁全绿:后端 1294 unit / 前端 343 vitest）。**F004=Codex L2 真机**（两 timer 真跑+权重和=1.0 含 cash 行+OOS 披露真渲染+执行闭环隔离+零回归+§29）。spec `docs/specs/B067-...-spec.md`。
- **★诚实约束（spec §0 焊死）**：用户 B066 P1 done 后拍板上 P2（有权用）。B066 诚实结论=**OOS −9~−11% 动量逆转 + 质量 A/B 本地未分胜负（需宽宇宙）**。surface 须 cn_attack 专属 OOS 负/未验证披露 + advisory-only/不自动下单/非收益预测。
- **关键决策**：cn_attack 两 advisory 模式（cn_attack_quality_momentum/pure_momentum）进 **mode registry _MODES**（非 master sleeve，守不变量#3）；B066 backtest id `cn_attack_momentum_quality` 仍在 STANDALONE_RESEARCH 不动。纯进攻无 regime gate。

## 遗留 / soft-watch
- **质量 A/B 未分胜负**：种子宇宙 43 股全通质量门槛→「质量+动量」≡「纯动量」，"质量是否加值" **需生产宽宇宙才分化**（未答）。
- **S1 全量 cross-source 待补**：B066 延用 B065 抽样结论（未改价格逻辑=合理）；全 universe baostock 复确认待 VM 真跑（S2 SSH 本会话已恢复）。
- **S3 已处理**：akshare eastmoney `stock_zh_a_hist` 端点 VM 不可达 → B066 F001 已 fold sina `stock_zh_a_daily` fallback（B062 同款）。
- **P2/P3**：P2 = 本批 B067（用户拍板上，不等 OOS 正向；靠诚实框架守门，宽宇宙 advisory 自然分化解质量 A/B）。P3 港股扩待 P2 后；backlog B055 记路线。

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
