# B009 Public Data Snapshot MVP Signoff 2026-05-13

> 状态：**Evaluator 复验通过**（progress.json status=done）
> 触发：B009 F006 独立验收与 B009-F006-1 / B009-F006-1R 修复复验。

---

## 变更背景

B009 在 B008 研究级数据基础上补齐 MVP PRD 中“可复现本地研究数据快照”的关键闭环：手动公开数据导入、本地 snapshot manifest、显式 snapshot loader、imported data quality/report labels、research run artifact，同时继续保持默认 CI fixture/mock-first、无 secret、无默认网络、无 broker、无 paper/live、无 AI trading 路径。

---

## 变更功能清单

### F001：建立手动公开数据导入 CLI 安全边界

**Executor：** generator

**验收结果：** PASS

### F002：生成本地研究数据 snapshot manifest

**Executor：** generator

**验收结果：** PASS

### F003：接入显式 snapshot 历史数据加载路径

**Executor：** generator

**验收结果：** PASS

### F004：导入数据质量门禁与报告限制标记

**Executor：** generator

**验收结果：** PASS

### F005：建立可复现 research run artifact 结构

**Executor：** generator

**验收结果：** PASS

### F006：独立验收 B009 Public Data Snapshot MVP

**Executor：** codex

**文件：**
- `docs/test-reports/B009-public-data-snapshot-mvp-review-2026-05-13.md`
- `docs/test-reports/B009-public-data-snapshot-mvp-reverification-2026-05-13.md`
- `docs/test-reports/B009-public-data-snapshot-mvp-signoff-2026-05-13.md`

**验收标准：**
- Evaluator 在 local/CI-safe 环境执行 L1 验收和复验。
- 确认默认 CI offline fixture/mock-first。
- 确认 public import manual/disabled，输出 gitignored。
- 确认 report/research-run artifacts 引用真实 importer 生成的 snapshot manifest 和 limitations。
- 确认 quality gates 生效，且无 secret/broker/live/paper/AI-trading 路径。

**验收结果：** PASS

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| Broker / Live 操作 | 未连接真实券商，未使用 API key，未执行 paper/live broker 或真实资金测试。 |
| External network | Required L1 tests and evaluator verification did not require public network access. Public import remains local-file copy only. |
| Paid / account data | 未提交付费数据、真实账户导出、API key、`.env` 或生成的市场数据 snapshot。 |
| Frontend / Browser E2E | 未引入 frontend dashboard、React/Next.js、Vitest、Playwright、Cypress 或浏览器 E2E。 |
| OMS / Tax / AI trading | 未实现 OMS、税务优化、税务建议、AI 下单或 AI 改参数。 |
| CD / Deployment / Database | 未引入 CD、部署配置、数据库 schema 或 migrations。 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| B009 验收状态 | F006 pending / fixing loop | F006 independent L1 re-verification PASS |
| Public data import | B008 disabled stub only | Manual confirmed local-file import with manifest generation |
| Snapshot lineage | Generated manifest was not referenced by artifacts | Real importer output is matched by loader and referenced in JSON report + research-run artifact |
| Research run artifact | Strategy/report/target weights linked | Adds auditable manifest reference for imported snapshots |
| Safety posture | Fixture-first no-live guards | Preserved fixture-first, no-secret, no-default-network, no-broker, no-paper/live, no-AI-trading boundaries |

---

## 类型检查 / CI

```text
.venv/bin/python -m pytest
62 passed in 1.20s

.venv/bin/python -m ruff check .
All checks passed!

.venv/bin/python -m compileall trade tests
PASS

.venv/bin/python -m mypy --install-types --non-interactive trade
Success: no issues found in 22 source files
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | N/A - B009 is local/CI-safe L1 data snapshot workflow; no staging deployment impact. |
| 端到端流验证 | Local E2E under `/tmp/opencode/b009-reverify2/`: created fixture-shaped manual source, ran `import_public_data()` with explicit manual confirmation into gitignored `data/public-cache`, then ran `run_fixture_workflow()` on `result.output_file`. |
| 关键 invariant | JSON report `data.snapshot_manifest` and research-run `snapshot_reference.manifest` both referenced `data/public-cache/public:eval-provider-round2:9aa9f876caec416a-manifest.json` and `public:eval-provider-round2:9aa9f876caec416a`; imported snapshot labels included public-best-effort, non-PIT, research-only, not-live-trading-ready; artifact stayed `human-review-only` and `broker_free = true`. |
| 浏览器手动验 | N/A - no UI changes. |

---

## Ops 副作用记录

本批次无数据库 ops，无外部服务写入，无券商 API 调用，无真实资金操作。

---

## Harness 说明

本批次按 Harness 状态机完成独立 Evaluator 验收和复验。`progress.json` 已设置为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | Public data snapshot remains public-best-effort and non-PIT; it improves reproducibility but not production-grade data assurance. | medium | Keep explicit labels in reports; require separate data-source qualification before production or paper/live use. |
| S2 | Manifest lookup scans sibling `*-manifest.json` files and matches `files[].path` + `sha256`; this is safe for local cache scale but may need indexing if cache grows. | low | Revisit if `data/public-cache` accumulates many manifests. |
| S3 | Report `run.environment` remains `local_or_ci_fixture` even for imported local snapshots. | low | Consider renaming to `local_or_ci_research` in a future schema cleanup if user-facing wording matters. |

---

## Framework Learnings

本批次无 framework learnings。
