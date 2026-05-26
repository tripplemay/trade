---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B029-fundamentals-snapshot：`building`**；F001+F002 completed；F003 generator 接手；F004 待 codex。Spec：`docs/specs/B029-fundamentals-snapshot-spec.md`。
- F002 落 3 scripts + 1 测试 (20 cases) + sec_edgar_loader.py 方法拆 + concept alias chain + ticker_cik DUK fix + .gitignore 扩 *.json + PIT 报告。Commits: feat `11270ff` + fix-round 1 `9187445`。
- 本机跑真 SEC backfill 实际产出：**685 行**（vs spec ≥1000 floor — sector-structural shortfall；6/27 ticker BAC/JPM/V/LIN/NEE/PLD 产 0 行因银行/支付/REIT/utility 概念不匹配；21/27 产 1-59 行）；3 synthetic ticker skip 不阻塞（裁决 #3）；27 CIK 目录入 `data/snapshots/fundamentals/sec_edgar/`；unified 入 `data/snapshots/fundamentals/unified/fundamentals.csv`。
- **PIT validation 25/25 PASS** — `report_date >= fiscal_quarter_end + 30d` invariant 全成立。报告 `docs/test-reports/B029-pit-validation-2026-05-26.md`。
- F002 fix-round 1 重大决策：(a) DUK CIK 0000017797 retired → 1326160 holding co；(b) SEC_CONCEPT_NAMES 从 `dict[str, str]` 升级为 `dict[str, list[str]]` 别名链（驱动按 alias 顺序聚合 entries 后 bucket；解决 ASC 606 ticker 切到 RevenueFromContractWithCustomerExcludingAssessedTax + JNJ 用 StockholdersEquityIncludingPortion... + JNJ OperatingIncomeLoss 2015 后转 IncomeLossFromContinuingOperationsBeforeIncomeTaxes... 等）；(c) SHARES_OUTSTANDING_ALIASES 多 namespace fallback (dei + us-gaap)；(d) 6 ticker 0 行问题确认 sector-structural，B030 cutover per-sector ratio model 调整解决。
- 本机 Gates 全绿：backend pytest **361 passed** 2 skipped（B028 baseline 304 → +57；vs spec ≥326 floor +35 buffer）/ ruff 0 / mypy 0（143 source files）/ frontend vitest 166（baseline 不破）。
- 永久边界 (h)(i)(j) 落地 + production aligned (`ef421e9` SEC_EDGAR_CONTACT_EMAIL via bootstrap-env.yml；config tripplezhou@gmail.com on VM)。
- 下一 sprint F003：`trade/data/loader.py` 加 `load_fundamentals(tickers, as_of_date) → dict[str, FundamentalsRow | None]`；PIT enforcement: `effective_date = report_date + 1 business day`；读 `data/snapshots/fundamentals/unified/fundamentals.csv` if exists else fall back B025 fixture (B025 既有回测 deterministic 不变 = F003 acceptance 硬要求)；pytest ≥10 (≥336 floor)。
- 后续路径：B029 done → B030 (Stream 1.D 全 sleeve 切真 + reports/ fixture vs real 对比 + per-sector ratio model 解决 6 sector ticker 缺数据 + .env.production NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false 让 B026 banner 下线) → 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B028 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B028 Real Data Backfill signoff 2026-05-26（1 fix-round）；B027 signoff 2026-05-26；B026 signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live；production HEAD = `ef421e9`（F001 SEC_EDGAR_CONTACT_EMAIL pre-flight 已 wired）；F002 本批次产品代码改 trade/+workbench_api/+scripts/，paths-trigger 自然 deploy。

## 永久硬边界（B029 起继续；v0.9.29 + §12.7.1）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / **B026 banner 保留**
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g)：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced
- **B029 起 (h)(i)(j)：** SEC EDGAR User-Agent 必含 contact email（ban IP 30d）/ Rate limit 10/sec hard / 8 ratio 公式锁定 strategy doc §6 + B029 spec §4.4

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY`（B027）+ `SEC_EDGAR_CONTACT_EMAIL` (B029 F001 prod-side aligned) 已配。
- B029 unified fundamentals 685 行 < spec ≥1000；6 sector ticker 缺数据；F003 fall back B025 fixture 保 backtest；B030 cutover per-sector ratio model 调整解决。
