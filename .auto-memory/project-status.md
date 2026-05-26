---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B029-fundamentals-snapshot：`done`**；F004 已由 Codex 于 2026-05-26 签收。Signoff：`docs/test-reports/B029-fundamentals-snapshot-signoff-2026-05-26.md`。证据图：`docs/screenshots/B029-fundamentals/`。
- F003 落 `trade/data/loader.py`：加 `FundamentalsRow` (12 字段；frozen+slots；与 B025 fixture 列序 1:1) + `UNIFIED_FUNDAMENTALS_PATH` / `B025_FIXTURE_FUNDAMENTALS_PATH` / 12-列 `UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS` + `load_fundamentals(tickers, as_of_date)` PIT 函数 (`effective_date = report_date + 1 business day`；unified-first / fixture fallback；缺数据 None；future as_of clamp；schema 缺列 FixtureDataError 含 regen 指引)；trade/ 独立定义 FundamentalsRow 避免 → workbench_api 反向 import。
- F003 tests/unit/test_pit_load_fundamentals.py 16 用例：latest visible row / PIT drops post-cutoff / Friday → Monday business-day offset / 缺数据 None / future clamp / multi-ticker / 3 source 优先级 / schema violation / frozen+slots+12 字段 / parametrized 5 (as_of, expected_fq) AAPL 2019 cadence walkthrough。Commit `c3ec920`。
- 本机 Gates 全绿：trade pytest **755 passed** (739 → +16；vs spec ≥749 floor +6 buffer) / workbench backend pytest 361 passed 2 skipped (不动) / ruff 0 / mypy 0 / frontend vitest 166 不动 / **B025 既有回测 deterministic 不变** (F003 acceptance §(4) 硬要求验证通过)。
- Production HEAD `d6622e6` (F002 chore commit); F003 commit `c3ec920` trade/+tests/ 触 Python CI + paths-trigger 触 Workbench Backend CI (trade/ in paths)；自然 deploy。
- 本机数据状态: `data/snapshots/fundamentals/unified/fundamentals.csv` 685 行 / 27 CIK vendor 目录 / 21 真 ticker 1-59 行 / 6 sector-structural 0 行 (BAC/JPM/V/LIN/NEE/PLD) / 3 synthetic skip (ZQAI/ZQPT/ZQLH)；PIT 25/25 spot-check PASS。报告 `docs/test-reports/B029-pit-validation-2026-05-26.md`。
- B029 关键决策回顾：(1) Pre-impl 裁决全 A (commit `c07867f`)：12-字段 schema 含 fiscal_quarter_end / fiscal_quarter '2014Q4' 无短横线 / 30 ticker map 含 3 synthetic null + ValueError skip 模式 / 不引入新 dep。(2) F002 fix-round 1 alias chain 扩 (`SEC_CONCEPT_NAMES` dict[str,list[str]] + `SHARES_OUTSTANDING_ALIASES` 多 namespace；DUK CIK 17797→1326160)。(3) F003 strategy 层独立 FundamentalsRow 不 import workbench_api。
- F004 验收结论：L1 通过（backend pytest 361 passed 2 skipped / trade pytest 755 passed / frontend vitest 166 passed / build 通过）；L2 focused checks 通过（production `/api/health.version=c3ec920`、`/api/debug/recent-errors={"count":0,"records":[]}`、`/strategies` B026 banner 仍可见）。Production 与签收时 HEAD 仅有 metadata-only drift，按规则接受，无需额外 deploy。
- 后续路径：B030 (Stream 1.D 全 sleeve 切真 + reports/ fixture vs real 对比 + per-sector ratio model 调整解决 6 sector 0-row + `.env.production NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false` 让 B026 banner 下线) → 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B028 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B028 Real Data Backfill signoff 2026-05-26（1 fix-round）；B027 signoff 2026-05-26；B026 signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live；B029 production `/api/health.version` 为 `c3ec920f96587bf9945c4e384fc151fc774f9696`，signoff 时与 `main` 的差异仅 metadata-only commit，可接受。

## 永久硬边界（B029 起继续；v0.9.29 + §12.7.1）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / **B026 banner 保留**
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g)：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced
- **B029 起 (h)(i)(j)：** SEC EDGAR User-Agent 必含 contact email（ban IP 30d）/ Rate limit 10/sec hard / 8 ratio 公式锁定 strategy doc §6 + B029 spec §4.4

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY`（B027）+ `SEC_EDGAR_CONTACT_EMAIL` (B029 F001 prod-side aligned) 已配。
- B029 unified fundamentals 685 行 < spec ≥1000；6 sector ticker 缺数据 sector-structural；F003 fall back B025 fixture 保 backtest；B030 cutover per-sector ratio model 调整解决。
