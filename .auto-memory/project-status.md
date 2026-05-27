---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B030-real-data-cutover：`done`**；F004 已于 2026-05-27 复验签收。Signoff：`docs/test-reports/B030-real-data-cutover-signoff-2026-05-27.md`；证据图：`docs/screenshots/B030-cutover/`。
- **F001 done + F004 fix-round 1 floor recovered 2026-05-27**：unified rows **853 → 1121 (+63.6% vs B029 baseline)**；6/6 sector ticker recovered (BAC 32 / JPM 56 / V 38 / LIN 31 / NEE 53 / PLD 58)。三层补丁：(a) default chain 补 `LongTermDebtAndCapitalLeaseObligations` (HD/XOM/ECL/APD +130 rows)；(b) Financials capex=0 fallback (BAC/JPM +75 rows)；(c) V dividend-derive shares (V +38 rows)。+7 regression tests。
- **F002 done 2026-05-27** (f83d2df)：trade/data/us_quality_universe.py 4-tier 解析。+23 new tests。
- **F003 done 2026-05-27 + F004 fix-round 1 banner truly off**：从 (protected)/layout.tsx 移除 banner JSX+import + 删 messages 中 syntheticBanner.* keys → 组件 chunk 不在 layout 加载 + i18n 字符串不在 RSC payload。组件文件保留 + hardcoded 双语 + useLocale。+15 frontend tests (6 decommission guard + 9 component isolation)。Local build grep '研究原型' / 'SyntheticDataBanner' = 0 hit。
- F004 复验结论：L1 全绿（backend pytest 408 / trade pytest 778 / FORCE_FIXTURE_PATH=1 仍 778 / frontend vitest 172 / build / local Playwright 38）；L2 focused checks 也通过（production HEAD 等价、recent-errors=0、protected HTML 均 `BANNER_ABSENT`）。
- 🎯 **Phase 1 终点 / 里程碑 A Layer 0→1 已达成**。
- 新增永久产品边界 (k)：**Layer 状态不可逆向滑落** — B030 done 后若真数据严重 unreliable 必须新批次 spec 决议，不 silent rollback。
- 本批次属 implementation-path-2026-05.md §4 **Phase 1 第五个 batch（Stream 1.D 终点）**。
- 后续路径：Phase 2 (B031+ LLM advisory / B033+ News ingest)。

## 已完成签收 + MVP 完工
- B001-B029 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B029 Fundamentals Snapshot signoff 2026-05-26（0 fix-round；27 CIK + 685 rows + PIT 25/25 PASS）；B028 signoff 2026-05-26；B027 signoff 2026-05-26；B026 signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live；production `/api/health.version` = `abf2ec4438a9605ff579c59fda425cda7db171f8`，与签收前 `main` 等价；B026 synthetic banner 已从 production 受保护页面下线。

## 永久硬边界（B030 起继续；v0.9.30 + §12.9）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / **B026 banner 在 B030 done 后下线**（B030 起组件代码保留可重启路径）
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g)：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced
- B029 起 (h)(i)(j)：SEC EDGAR User-Agent 必含 contact email / Rate limit 10/sec hard / 8 ratio 公式锁定 strategy doc §6
- B030 起 (k) + v0.9.30 §12.9：production secret 必须 3+1 处接线 (.env.example + config.py + deploy.sh + bootstrap-env.yml) + **Layer 状态不可逆向滑落**（B030 done 后 Layer 1 稳定，回滚需新批次 spec）

## Framework 状态
- 最新版本 **v0.9.30**（2026-05-26 沉淀完成）：B027 + B029 二例合并沉淀 "production secret 三处接线铁律"（§12.9）。"deploy hygiene" 系列已覆盖 5 层 production-only edge 防御（deploy script / deploy workflow / runtime process / packaging / secret 注入）。proposed-learnings.md 空。B026 React event edge 仍单一案例 hold。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY`（B027）+ `SEC_EDGAR_CONTACT_EMAIL`（B029）已配；B030 本批次不引入新 secret 无需用户介入。
- **B030 soft-watch**：`compare_fixture_vs_real.py` 仍是 data-quality delta proxy，不是 full strategy backtest；local harness 仍有 auth env / `3099` 契约漂移。详 signoff Soft-watch。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
