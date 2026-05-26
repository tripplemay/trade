---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B030-real-data-cutover：`verifying`**；F001+F002+F003 done (generator)；F004 pending（codex L1+L2 验收 + signoff）。Spec：`docs/specs/B030-real-data-cutover-spec.md`。
- **F001 done 2026-05-27** (fd680a4 + 70e2f4d)：per-sector alias chains (Financials/Utilities/Real Estate × 6 concept) + universe sector 映射；重跑 backfill **685 → 853 rows (+24.5%)**；4/6 sector ticker 恢复。BAC/V structural gap 文档化转 Planner。
- **F002 done 2026-05-27** (f83d2df)：trade/data/us_quality_universe.py 4-tier 解析 (explicit fixture_dir > FORCE_FIXTURE_PATH=1 > unified > default fixture)。schema 12-col / 8-col 完全相同 → zero conversion。B025 deterministic tests 用 autouse FORCE_FIXTURE_PATH=1 per-module fixture 锁定。+23 new tests。
- **F003 done 2026-05-27**：scripts/compare_fixture_vs_real.py 5 sleeve buy-and-hold proxy；reports/fixture_vs_real/ 11 files；B026 banner 4 处接线关闭 (.env.example=true + .env.production=false + workbench-deploy.yml env + bootstrap-env.yml 注释)；+19 new tests。
- 🎯 **Phase 1 终点 / 里程碑 A Layer 0→1**：F004 codex evaluator 接手 L1 + L2 完成后达成。
- 新增永久产品边界 (k)：**Layer 状态不可逆向滑落** — B030 done 后若真数据严重 unreliable 必须新批次 spec 决议，不 silent rollback。
- 本批次属 implementation-path-2026-05.md §4 **Phase 1 第五个 batch（Stream 1.D 终点）**。
- 后续路径：F004 codex L2 验收 → 🎯 里程碑 A Layer 0→1 → Phase 2 (B031+ LLM advisory / B033+ News ingest)。

## 已完成签收 + MVP 完工
- B001-B029 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B029 Fundamentals Snapshot signoff 2026-05-26（0 fix-round；27 CIK + 685 rows + PIT 25/25 PASS）；B028 signoff 2026-05-26；B027 signoff 2026-05-26；B026 signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live；B029 production `/api/health.version` 为 `c3ec920f96587bf9945c4e384fc151fc774f9696`；B030 F004 后 production 将 cutover 到真数据 + B026 banner 下线。

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
- **B030 F001 残留 (gap → Planner)**：853 < 1000 row floor (-15%)；BAC/V 仍 0 row。BAC 无标准 capex（银行不发 PaymentsToAcquirePropertyPlantAndEquipment 只发证券购买），V 无 quarterly shares_outstanding（只发年度 cover-page）。Forward path: (a) Financials capex=0 fallback + (b) V annual-shares interpolation → ~920 rows；或 (c) B025 universe 移除 BAC/V。详 `docs/test-reports/B030-pit-validation-2026-05-27.md` §4+§9。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
