# proposed-learnings v0.9.29 归档（2026-05-26）

## 背景

B027-real-data-snapshot-foundation F003 reverify 阶段 Codex L2 production smoke 失败：本地 `pytest 273 passed` 全部通过，但 production wheel install 启动 `TiingoSnapshotLoader().health_check()` 时 `ImportError: No module named 'httpx'`。Generator F002 fix-round 1（commit `468d380`）把 `httpx>=0.27` 从 `[project.optional-dependencies].dev` 提升到 `[project].dependencies`，并主动加 safety regression test 守门。

Codex 在 signoff `docs/test-reports/B027-real-data-snapshot-foundation-signoff-2026-05-26.md` §Framework Learnings 段标"本批次无 framework learnings"。Planner 在 done 阶段做独立评估：

**沉淀理由：**
1. 与 v0.9.X 系列「local pass + prod fail」教训一脉相承（v0.9.25 §12.5 deploy.sh source env / v0.9.27 §12.7 chore-only deploy / v0.9.27 §20 lsof stale process）；本节是该系列的 **deploy-time install 层** 教训
2. Generator 主动加的 safety regression test (`test_runtime_dependencies_pinned.py`) 是 **framework-grade pattern**，已经具备复用形态（ast walker + STDLIB_MODULES + TRANSITIVE_ALLOWLIST + CRITICAL_RUNTIME_DEPS pin）
3. **后续批次几乎每个都会引入新 dep**：B028 (yfinance + Alpha Vantage) / B029 (SEC EDGAR XBRL parser) / B031 Phase 2 LLM gateway / B033 news ingest / B040 Reports UI；不沉淀则每批次都可能撞同样 wheel install 问题
4. 单一案例但**机制清晰、防御方案成熟、复用窗口大**，比"等二例"原则更适合即时沉淀

## 候选清单

| 候选 | 来源 | 沉淀决策 | 理由 |
|---|---|---|---|
| **httpx runtime vs dev hygiene + safety regression test** | B027 commit `468d380` | **沉淀 v0.9.29** | framework-grade pattern；高复用价值 |
| health_check 没走 budget guard wiring 漏 | B027 commit `49462d6` | 不沉淀 | spec acceptance 完整性教训，单一案例；提示 Planner 后续 spec 起草时 acceptance 显式列每个 method 的 wiring |
| Soft-watch S1 env file 文案漂移（`.env.production` vs `workbench.env`） | signoff §Soft-watch S1 | 不沉淀 | spec accuracy 教训属已有 planner.md 铁律 3（spec 写"在 X.md 加段"前必须 ls 实物），无需新沉淀 |
| B026 production-only React event edge | B026 fix-round 2 | 继续 hold | 单一案例；本批次 B027 是 deploy-time install edge 机制不同，不与 React event edge 强合并；等下一例 React UI 互动 local-pass-prod-fail 再合并 |

## 沉淀位置（已落地）

| 候选 | 落地文件 / 章节 |
|---|---|
| httpx runtime vs dev hygiene + safety regression test | `framework/harness/generator.md` §12.8 "pyproject runtime vs dev dependency hygiene（v0.9.29 — B027 沉淀）" |
| safety regression test 完整模板 | 同上 §12.8.1 `tests/safety/test_runtime_dependencies_pinned.py` |
| 反面案例 | 同上 §12.8.2（commit `468d380` 之前/之后 现象对比表）|
| 「local vs prod」系列对比 | 同上 §12.8 末尾 4 行表格（v0.9.25 §12.5 / v0.9.27 §12.7 / v0.9.27 §20 / **v0.9.29 §12.8**）|

## 5 行 dep 类型判断规则（核心规约）

| 依赖类型 | 判断 | 放哪 |
|---|---|---|
| 业务代码 import（`workbench_api/`、`trade/` 等 source tree）| **runtime 必需** | `[project].dependencies` |
| 测试代码 import（`tests/`）| **仅 dev** | `[project.optional-dependencies].dev` |
| 既被 source 又被 tests import | **runtime 必需**（按 source 范围判定）| `[project].dependencies` |
| Type checker / linter / formatter（mypy / ruff）| 仅 dev | `[project.optional-dependencies].dev` |
| Stub packages（`types-*`）| 仅 dev | `[project.optional-dependencies].dev` |

## 「local vs prod」教训系列演进

| 版本 | 现象 | 防御 | 哪一层 |
|---|---|---|---|
| v0.9.25 §12.5 | 本地 alembic OK，production deploy.sh 没 source env file → 跑 scratch DB | deploy.sh source EnvironmentFile | deploy script |
| v0.9.27 §12.7 | 本地 commit push，chore-only commit 不触 CI / deploy → production HEAD drift | workflow_dispatch + chore commit 后 dispatch | deploy workflow |
| v0.9.27 §20 (evaluator.md) | 本地 Playwright pass，production VM stale dev process 让 dismiss UI 失败 | lsof check + kill 再启 | runtime process |
| **v0.9.29 §12.8** | **本地 pytest pass，production wheel install 缺 dev extras → ImportError** | **runtime vs dev 判断 + safety regression test 守门** | **packaging / install** |

**演进趋势：** v0.9.X 系列每个版本逐渐补一层 production-only edge 防御。后续可能再撞的层：
- frontend bundle 层（已部分覆盖：v0.9.24 §13 same-origin + build artifact grep）
- nginx / reverse proxy 层（已部分覆盖：v0.9.24 §13.5 dev rewrite 1:1 mirror nginx）
- production env var 层（已部分覆盖：v0.9.25 §12.5 deploy.sh source env + §12.6 schema-assert）
- systemd / cron 层（B028 EOD cron 上线时可能再撞）

## Planner done 阶段补写时机说明

与 v0.9.26 / v0.9.27 / v0.9.28 沉淀模式一致：
- Codex 在 signoff §Framework Learnings 段做的是产品 spec 角度 PASS / FAIL 判断
- Planner 在 done 阶段做的是**跨批次 framework 演进**视角评估
- 两者视角不同；Codex 标"无 learnings" ≠ Planner 评估"无沉淀价值"
- Planner 重新评估时考虑：(a) 与既有 v0.9.X 系列教训是否同脉络 (b) 防御方案是否 framework-grade (c) 复用窗口（后续多少批次会用到）

来源：B027-real-data-snapshot-foundation F002 fix-round 1；commits `468d380` + `49462d6`；Generator handoff at `49462d6`；signoff `docs/test-reports/B027-real-data-snapshot-foundation-signoff-2026-05-26.md`；本归档由 Planner 在 done 阶段 2026-05-26 与用户确认后落地。
