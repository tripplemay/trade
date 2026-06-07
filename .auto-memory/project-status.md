---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B045-real-data-refresh-pipeline：`reverifying`**（2026-06-07，fix-round 1 已修，交 Codex 复验）。**F001+F002+F003 done；F004 首轮 PASS（含2 finding），Generator 已修两 finding。** **Finding #1（critical，fundamentals 0 行）修复**：把 B029 companyfacts→比率合成抽进可部署 `workbench_api/data/fundamentals_sync.py`（scripts re-import 单一真源）；refresh.py 用 ticker_cik_map 分真 synthetic vs 真实 ticker，对真实 ticker fetch_raw_companyfacts→合成真实比率行（close 取自刚写 prices CSV），真实失败如实计 error（commit 0cd1f95）。**Finding #2（high，ModuleNotFoundError data_root）修复**：deploy.sh trade wheel `--upgrade→--force-reinstall` + trade 版本 0.1.0→0.2.0（commit dfb5702）。本地全门绿（backend 851 / root 792 / ruff 0 / mypy 0 / B029 backfill 42 不破）；新增 full-real 端到端单测证 data_source=real 可达（全 sleeve scored 含 us_quality）。**复验重点**：re-deploy 后 wheel 含 data_root+fundamentals_sync、手动刷新 fundamentals.csv 非 0 行、re-precompute data_source=real、/current us_quality 真实评分非 stub。signoff `docs/test-reports/B045-real-data-refresh-pipeline-signoff-2026-06-07.md`。
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
