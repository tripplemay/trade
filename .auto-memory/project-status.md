---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B045-real-data-refresh-pipeline：`fixing`**（2026-06-07，fix-round 1）。**F001+F002+F003 done，F004 首轮验收 PASS（含2 finding 需修复）。** 数据刷新 pipeline 跑了 16500 行 Tiingo prices 写入 VM unified CSV，precompute data_source=mixed（risk_parity 从 stub→真实评分 6 positions vs B044 3），/current 返回非 equal-weight 真实权重。**Finding #1（critical）：SEC EDGAR fundamentals 0行，skip_synthetic 误过滤→us_quality stub→data_source=mixed 非 real。Finding #2（high）：trade version 0.1.0 未递增→pip --upgrade 跳重装→deploy 后 precompute ModuleNotFoundError(data_root)，手动 force-reinstall 恢复。** signoff `docs/test-reports/B045-real-data-refresh-pipeline-signoff-2026-06-07.md`。
- **B044-real-scoring-precompute：✅ `done`**。`/api/recommendations/current` equal-weight→Master 真实评分，§12.10 AST 守门，vm disk 82% S1。**B046=regime reconcile+account current_weight 待做。**

## 已完成签收
- B001-B044 全部签收。MVP substantively 完成。

## 生产状态
- **B045 deployed（90e52808）：** trade 含 data_root 但 version 冻结未自动重装→precompute 需 force-reinstall 恢复。data-refresh timer enabled+active（B037-OPS1）。prices CSV 16500 行（1.1M），fundamentals CSV 仅 header（0行）。precompute 后 saved=6 mixed。VM disk 82% data 19M。
- **VM 运维笔记：** timer auto-wiring 就位；deploy 后需核对 trade version 递增或改 force-reinstall。

## 永久硬边界
- 系统层/UI 层/数据层：参见 B044 done 状态。B045 扩 boundary (r) 允许 data-refresh 每日读市场数据。

## Framework 状态
- v0.9.35（B044 done）：§12.10.2 enforcement 物理缺席→AST 守门 + README 长停机教训。

## 已知 gap
- 本机 python3=3.9.6，用 .venv/bin/python。
- GitHub Secret 全配齐。
