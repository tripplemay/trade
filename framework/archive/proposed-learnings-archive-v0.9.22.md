# Proposed Learnings Archive — v0.9.22

> 归档日期：2026-05-15
> 来源批次：B019-b010-b013-cadence-vol-target-retune F005 signoff §Framework Learnings + Soft-watch S1
> 闭环情况：1 条 learning Accept（用户 5/15 done wrap-up 决议）+ 落 docs/engineering/backtest-report-schema.md，CHANGELOG v0.9.22 已记录。

---

## [2026-05-15] Claude CLI — 来源：B019 F005 signoff（v0.9.22 #1）

**类型：** 新规律（snapshot consumption discipline — T+1 execution boundary）

**内容：** Sweep / comparison / reporting CLI 消费 snapshot 时，**必须为最后一个实际使用的 signal date 保留至少 1 个交易日的 trading-day headroom**。T+1 execution 模型要求每个 signal date 之后存在下一个 trading day；没有这层 headroom，snapshot 尾部的 signal 在 lookup T+1 execution date 时找不到匹配，触发 `no trading date exists after signal_date` 类边界错误，即使 signal date 本身的数据点存在。

**沉淀位置（已写入）：**
- `docs/engineering/backtest-report-schema.md` §"Snapshot Tail Headroom for T+1 Execution" —— 含 reference incident + 3 条 required practice + retrofit 政策
- `docs/engineering/backtest-report-schema.md` §"Non-Goals" 段同时刷新：删除 "No formal frontend dashboard" 绝对禁令（PRD §7 修订后已不成立），改为指向 PRD §7 作为 dashboard 边界权威源

**实物时间线（B019 F004 → F005 2026-05-15）：**

1. **F004 实施期间** Generator 跑 `scripts/generate_b015_activation_policy_report.py` 默认全量 snapshot 路径，CLI 报 `no trading date exists after signal_date`
2. **绕过方案** Codex 给 CLI 传显式窗口，end_date 截到 snapshot tail - 1 交易日；rerun 通过
3. **F005 signoff** 记录为 Soft-watch S1（low risk），建议 framework 层固化
4. **5/15 done wrap-up** Planner 提议沉淀到 backtest-report-schema.md，用户 5/15 确认 → 沉淀 v0.9.22 #1

**未来 retrofit 候选（不阻塞 v0.9.22 沉淀）：**
- `scripts/generate_b015_activation_policy_report.py` 默认窗口逻辑改为自动 trim 最后一个 signal date
- 其它 sweep / comparison CLI 顺手按此模式回填
