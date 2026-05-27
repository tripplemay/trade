# B030 Real Data Cutover Signoff 2026-05-27

> 状态：**PASS**
> 触发：B030 F004 reverify 完成；L1 + L2 已满足 milestone A Layer 0→1 签收条件。

---

## 变更背景

B030 是 Phase 1 的终点批次：把 B028 unified prices + B029/B030 unified fundamentals 接入 Master Portfolio / sleeves / B025 us_quality 真实数据读路径，产出 fixture-vs-real 对比报告，并关闭 B026 synthetic banner。签收完成即代表 **里程碑 A：Layer 0→1 达成**。

---

## 变更功能清单

### F001-F003：real-data cutover / floor recovery / banner decommission

**Executor：** generator

**验收结论：**
- PASS：`data/snapshots/fundamentals/unified/fundamentals.csv` 为 `1122` 行（`1121` 数据行 + header），达到 `>=1000` floor。
- PASS：`BAC/JPM/V/LIN/NEE/PLD` 六个先前 structural-gap ticker 均可通过 `load_fundamentals(..., as_of=2026-05-01)` 取到真实行。
- PASS：`reports/fixture_vs_real/` 本机存在 `5 + 1` 报告产物，可读且指标非空。
- PASS：production 受保护页 `/strategies`、`/reports`、`/recommendations`、`/backtest`、`/risk` 的 HTML 检查均为 `BANNER_ABSENT`。

### F004：Codex L1 + L2 真 VM 验收

**Executor：** codex

**验收结论：**
- PASS：backend `pytest 408 passed, 2 skipped`、`ruff`、`mypy` 全绿。
- PASS：trade `pytest 778 passed`，且 `FORCE_FIXTURE_PATH=1` 下仍 `778 passed`；`mypy` 全绿。
- PASS：frontend `vitest 172 passed`、`build` 通过、`npm audit --omit=dev --audit-level=high` 仅 `moderate`。
- PASS：local Playwright `38 passed`。
- PASS：production `/api/health.version` 与本地 `main HEAD` 等价；authenticated `/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`。

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| broker / live trading | 永久边界未变，系统仍为 research-only |
| B026 组件文件本身 | `SyntheticDataBanner.tsx` 仍保留在代码树中，供未来显式 rollback 使用 |
| production 数据库写入 | Evaluator 本轮未执行任何 prod DB mutation |

---

## 类型检查 / CI

```text
workbench/backend: pytest 408 passed, 2 skipped
workbench/backend: ruff check . -> PASS
workbench/backend: mypy workbench_api tests -> PASS
repo root: pytest tests -q -> 778 passed
repo root: FORCE_FIXTURE_PATH=1 pytest tests -q -> 778 passed
trade/: mypy . -> PASS
workbench/frontend: npm test -> 172 passed
workbench/frontend: npm run build -> PASS
workbench/frontend: npm audit --omit=dev --audit-level=high -> 4 moderate / 0 high
workbench/frontend: npx playwright test -> 38 passed
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git SHA 等价性 | `curl https://trade.guangai.ai/api/health` 返回 `version=abf2ec4438a9605ff579c59fda425cda7db171f8`；签收前本地 `HEAD` 同为 `abf2ec4438a9605ff579c59fda425cda7db171f8` |
| recent-errors | authenticated `GET /api/debug/recent-errors` 返回 `{"count":0,"records":[]}` |
| banner 下线 | authenticated production HTML 检查：`/strategies`、`/reports`、`/recommendations`、`/backtest`、`/risk` 均为 `BANNER_ABSENT` |
| 真实数据 surface | authenticated `/api/recommendations/current` 返回 `as_of_date=2026-05-27`，`gate_checks=[kill_switch pass, min_equity pass]`；`/api/strategies` 返回 live strategy list 含 `B025-us-quality-momentum` |
| fixture-vs-real 报告 | 本机 `reports/fixture_vs_real/` 含 `master`、`momentum`、`risk_parity`、`us_quality`、`hk_china_proxy` + `overview` 共 11 文件 |

---

## Ops 副作用记录

本批次无数据库 ops。

---

## Harness 说明

本批改动经 Harness 状态机完整流程交付。`progress.json` 已设为 `status: "done"`，`docs.signoff` 已回填本报告路径。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `abf2ec4438a9605ff579c59fda425cda7db171f8` |
| Main HEAD (`git rev-parse HEAD`) | `abf2ec4438a9605ff579c59fda425cda7db171f8` |
| Diff (`git log --oneline <deployed>..HEAD`) | `0 commits` |

**判断：PASS。**

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + tests + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | `签收 commit 仅含 progress.json / features.json / .auto-memory / docs/test-reports / docs/screenshots / workbench/frontend/tests 等测试与证据文件，不含产品运行时代码或 deploy-impacting 配置；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。` |

---

## Milestone

**里程碑 A Layer 0→1 达成。**

支撑证据：
- unified fundamentals floor 已恢复到 `1121` 数据行
- Master / sleeves / us_quality 的 fixture-vs-real 报告已生成
- production 已不再展示 synthetic-data banner
- production `/api/health.version` 与当前 `main` 一致

---

## Soft-watch（不阻塞 done，需后续跟进）

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | `compare_fixture_vs_real.py` 仍是 equal-weight buy-and-hold proxy，不是 full strategy backtest；适合比较 data-source delta，不适合替代策略真实性能签收 | medium | 后续若要把报告升级为策略级 KPI，对比逻辑应单独起批次 |
| S2 | local harness 仍有两处漂移：`codex-setup.sh` 默认不注入 test auth env；`AGENTS.md` 写 `3099`，但当前脚本/Playwright 实际使用 `3000/8723` | low | 后续统一本地测试契约，避免 evaluator 每轮手动补 auth env |
| S3 | B030 需要把旧的 B026 Playwright banner 用例改写为 decommission 断言，说明测试基线会随层级迁移发生语义翻转 | low | 在 framework 中补一条“decommission batch 要同步翻转 legacy E2E 断言”的测试规约 |

---

## Framework Learnings

### 新规律
- Decommission 类批次不能只补 safety/unit 守门，原有 E2E 断言也必须同步翻转，否则会出现“产品正确、测试过期”的假红。
  - 来源：B030 F004 reverify 中 `tests/e2e/b026-synthetic-banner.spec.ts`
  - 建议写入：`framework/harness/evaluator.md`

### 新坑
- 仅靠 build-time env 关闭 UI surface 不够；若上层 layout 仍 import/render 组件、消息 key 仍留在 bundle，production HTML grep 可能继续命中旧 surface。
  - 来源：B030 首轮 blocker 与 fix-round 1
  - 建议写入：`framework/README.md` §经验教训

### 模板修订
- decommission / layer-upgrade 批次的 signoff 模板可补一条显式检查：legacy E2E 是否已从“presence assertion”改为“absence assertion”。
  - 建议修改：`framework/templates/signoff-report.md`
