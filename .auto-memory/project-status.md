---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B110 纯 E/P first-look ✅ done（2026-07-21）**：F001-F004 验收通过；F004 Codex 裁定 `INCONCLUSIVE_COVERAGE_LIMITED`。
- 签收：`docs/test-reports/B110-pure-ep-first-look-signoff-2026-07-21.md`；独立证据：`docs/test-reports/B110-F004-evidence-2026-07-21.json`。
- 主口径几何超额 0.9606%/年、7/12 正超额年份、Q5 非最优；D1 构成差绝对值 1.7225pp，D6 stub 跨越 1.0% 边界。
- 独立复核：60 个证券-形成日、240/240 rt=2 对拍 MATCH、144 月拆腿复算；最差联合覆盖 71.69%、R1=0、period_not_fetched=0。
- B110 F002 已修复 Tushare 空响应/整页边界截断；863 缓存恰 5,000 行文件为 0，逐年 TTM 损失无尖峰。
- 统计等价式是 Decimal 下的代数恒等式，不能称为独立交叉验证；真校验为 R1 + R2，R2 断裂 fail-closed。
- 本批次不改产品代码、策略 readiness 或 `DATA_NO_GO`；研究结论不是可交易策略或收益承诺。

## 接续 / 待决策
- B110 后续 handoff gate 暂不因本批次自动推进；先由用户决定是否接受 coverage/stub 不确定性并补测。
- 下一 first-look 前明确 NO-GO 与 D1/D6 INCONCLUSIVE 的优先级，以及 D1 构成差使用 signed 还是 absolute。
- Tushare token 建议轮换（用户曾明文提供，未执行）；residual-engine（B100）与 B106-S3 在 backlog。
- B109 遗留：`panel_cli.py` 空响应防护、`universe.py` 畸形行披露、PIT 数据层仍 `DATA_NO_GO`。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins、法定截止日冒充公告日、流通市值代总市值、当前股本回填历史、只拉 L。
- 冻结再验证 pipeline 永不 validated；golden 只进测试 fixture seam；smart-money first-look 全部 research-only。
- B108 方法纪律：独立 holdout、被规则挡住不等于验证过、每轮修复后必须重新审查跨模块交互。

## Framework / 环境
- Framework 最新状态：P5-F2、v0.9.55；B110 S1/S2/S3 见 signoff，待 Planner/用户确认后沉淀。
- 本机测试使用 `.venv/bin/python`；生产活面 `https://trade.guangai.ai`，真 VM `34.180.93.185`（本批次未做 L2）。
