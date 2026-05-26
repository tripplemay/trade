# B028 Real Data Backfill Signoff 2026-05-26

> 状态：**PASS**
> 触发：F004 fix-round-1 后，production HEAD drift 已解除

---

## 变更背景

B028 在 B027 的 Tiingo foundation 之上补齐 10+ 年历史价格 backfill、双层存储、yfinance 抽样 cross-check，以及 `trade/data/loader.py` 的 PIT 读取基础设施，但仍不切换 strategy 代码到真实数据路径。F004 的职责是对 F001-F003 做 L1 + L2 验收，并在 production 不回归的前提下完成签收。

---

## 变更功能清单

### F004：Codex L1 + L2 真 VM 验收 + signoff

**Executor：** codex

**文件：**
- `docs/test-reports/B028-real-data-backfill-signoff-2026-05-26.md`
- `docs/screenshots/B028-backfill/snapshots-structure.png`
- `docs/screenshots/B028-backfill/cross-check-report.png`
- `docs/screenshots/B028-backfill/spy-pit-spotcheck.png`
- `progress.json`
- `features.json`
- `.auto-memory/project-status.md`

**改动：**
- 完成 B028 的本地 L1 验收
- 完成 production focused L2 复验（SHA、`recent-errors`、B026 banner）
- 完成本机 backfill 产物与 PIT spot-check 证据归档
- 产出 signoff 报告并推进状态到 `done`

**验收标准：**
- backend/trade/frontend L1 门禁通过
- backfill 文件数、unified 行数、cross-check 报告与 PIT spot-check 满足 spec
- production `/api/health.version` 与签收前 `main` HEAD 等价，或仅存在 metadata-only 差异
- production `/api/debug/recent-errors` 为 0
- B026 banner 仍显示

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| strategy / sleeve / signal 业务逻辑 | B028 只做 backfill + loader infra，不切真实数据读路径 |
| 财务 snapshot / SEC EDGAR | 留 B029 |
| 每日 EOD cron | 本批次不做 |
| B026 synthetic banner 逻辑 | 只验证未受影响 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| 历史价格数据层 | 仅 fixture | 本地新增 52 个 vendor CSV + 1 个 unified CSV |
| `load_prices(..., as_of_date=...)` | 仅 fixture loader | 优先读 unified，并做 PIT `date <= as_of_date` 过滤 |
| cross-check | 无 yfinance 背书 | `25/25` 抽样在 `<0.5%` 容差内通过 |

---

## 类型检查 / CI

```text
L1 first-round evidence reused in reverify:
- backend: pytest 304 passed, 2 skipped
- backend: ruff check . -> pass
- backend: mypy workbench_api tests -> pass
- trade: mypy . -> pass
- trade: pytest -q -> no tests ran in 0.01s (当前目录无 pytest suite；结构现状，非新增回归)
- frontend: vitest 166 passed
- frontend: next build -> pass
- frontend: Playwright 38 passed
- frontend: npm audit --omit=dev --audit-level=high -> no high severity (4 moderate only)
- artifact grep: 未命中 TIINGO_API_KEY / api.tiingo.com / Yahoo endpoint 泄漏

Backfill spot-check:
- vendor files: 52
- unified rows: 153386
- validate_snapshot report: 25/25 PASS
- SPY PIT spot-check: as_of=2020-03-01 -> max date 2020-02-28
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git_sha == main HEAD | `curl https://trade.guangai.ai/api/health` 返回 `version=15dfb4bfcc4100b1bd1ec0755208ed8ee054fa42`；签收前本地 `HEAD=0cad66558308e08c0d0b2b470115f6ccf197cd6e`，diff 仅含 `progress.json` 与 `.auto-memory/project-status.md` 这 1 个 metadata commit |
| 端到端流验证 | production focused reverify：authenticated 请求 `https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`；authenticated `https://trade.guangai.ai/strategies` 命中中文 synthetic banner 文案 |
| 关键 invariant | B028 不部署新 production surface；本轮确认 production health/db_connectivity 均正常，且 backfill/PIT 本地结果不要求线上写入 |
| 浏览器手动验（如 UI 类） | 本轮以 authenticated HTML probe 验证 `/strategies` 上仍出现 `研究原型 · 仅含合成数据 · 不构成投资决策依据`；截图证据补在 `docs/screenshots/B028-backfill/`，另有 backfill 文件结构 / cross-check / SPY PIT PNG |

---

## Ops 副作用记录

| Agent | 阶段 | 操作摘要 | 副作用对齐 | 用户授权 |
|---|---|---|---|---|
| generator | building | 本机执行 `python scripts/backfill_prices.py --from 2014-01-01 --to 2026-05-26 --universe master`，生成 52 个 vendor CSV 与 unified `prices_daily.csv` 153386 行；Tiingo 52 calls，估算 `$0.0026` | 仅影响本地 `data/snapshots/**` 研究数据；未触及 production DB / prod runtime ✓ | 用户已授权继续批次实现与验收 |
| evaluator | reverifying | 本机执行 `load_prices(['SPY'], as_of_date=...)` PIT spot-check 与 cross-check 复核 | 只读本地 backfill 产物，无额外副作用 ✓ | 用户本轮明确授权开始复验 |

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → fixing → reverifying → done）交付。`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `15dfb4bfcc4100b1bd1ec0755208ed8ee054fa42` |
| Main HEAD (`git rev-parse HEAD`) | `0cad66558308e08c0d0b2b470115f6ccf197cd6e` |
| Diff (`git log --oneline <deployed>..HEAD`) | `1 commit` |

等价性判断：

- `git diff --name-only 15dfb4b..HEAD` 仅含 `.auto-memory/project-status.md` 与 `progress.json`
- 不含任何 `workbench/**`、`trade/**`、`scripts/**`、`docs/specs/**` 等产品代码或 spec 漂移
- 因此按 v0.9.25 规则接受不同步，视为**产品代码无漂移**

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | `N/A` |
| Workflow run 链接（若是） | `N/A` |
| Production 最终 SHA = signoff commit SHA | `N/A` |
| 接受不同步声明（若否） | `本次签收 commit 仅包含 signoff 报告、截图与状态机元数据，不含任何产品代码或 deploy-impacting 配置；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。` |

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | `trade pytest -q` 在当前目录返回空套件；本批次 coverage 主要来自 backend pytest 与 `tests/unit/test_pit_load_prices.py` | low | 后续若要把 trade 层单独做 CI gate，可明确整理 pytest suite 入口，避免“空套件 exit 5”语义含混 |
| S2 | `docs/test-reports/B028-cross-check-2026-05-26.md` 为了避开 Tiingo Starter hourly 429，Tiingo 侧引用了刚生成的 unified CSV，而不是同轮再次 live refetch | low | 若后续希望完全 live-to-live 复核，可在单独 follow-up 里给 `validate_snapshot` 加统一 CSV loader-injection 说明或延时运行策略 |

---

## Framework Learnings

本批次无 framework learnings。
