# B029 Fundamentals Snapshot Signoff 2026-05-26

> 状态：**PASS**
> 触发：B029 F004 Evaluator 首轮验收完成，L1 + L2 均满足签收条件。

---

## 变更背景

B029 为 B025 `us_quality_momentum` universe 建立真实 SEC EDGAR fundamentals snapshot 基础设施：离线 backfill、统一 CSV、PIT loader，以及不破坏既有 B025 回测确定性的 fallback 路径。F004 负责对 F001-F003 做本地与 production focused 验收，并决定是否签收。

---

## 变更功能清单

### F001-F003：SEC EDGAR fundamentals infra / backfill / PIT loader

**Executor：** generator

**验收结论：**
- PASS：backend `pytest 361 passed, 2 skipped`、`ruff`、`mypy` 全绿。
- PASS：trade `pytest 755 passed`、`mypy` 全绿。
- PASS：frontend `vitest 166 passed`、`build` 通过，B026 banner 不回归。
- PASS：artifact grep 未发现 `SEC_EDGAR_CONTACT_EMAIL` 实值泄漏到前端构建产物。
- PASS：`data/snapshots/fundamentals/sec_edgar/` 目录数为 `27`，`data/snapshots/fundamentals/unified/fundamentals.csv` 为 `686` 行（`685` 数据行 + header）。
- PASS：PIT 验证报告 [B029-pit-validation-2026-05-26.md](/Users/yixingzhou/project/trade/docs/test-reports/B029-pit-validation-2026-05-26.md) 为 `25/25 PASS`。
- PASS：`load_fundamentals(['AAPL'], as_of=2026-05-01)` 返回最近可见季度；`load_fundamentals(['AAPL'], as_of=2020-03-01)` 返回 `2018Q2`，满足 PIT cutoff。

**备注：**
- 本地 backend 首次 `pytest` 因宿主机代理变量污染失败：`httpx.Client(trust_env=True)` 误读到 `127.0.0.1:7897` SOCKS 代理，而当前 `.venv` 未装 `socksio`。在取消 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY` 等环境变量后，失败用例单测与全量 backend `pytest` 均通过。该问题属 evaluator 本机环境污染，不构成产品 blocker。

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| strategy 代码 | 本批次不做 B030 的真 fundamentals cutover |
| workbench UI 行为 | 仅回归验证，不做产品实现修改 |
| production 数据库写入 | Evaluator 本轮未执行任何 prod DB mutation |

---

## 类型检查 / CI

```text
workbench/backend: pytest 361 passed, 2 skipped
workbench/backend: ruff check . -> PASS
workbench/backend: mypy workbench_api tests -> PASS
repo root: pytest tests -q -> 755 passed
trade/: mypy . -> PASS
workbench/frontend: npm test -> 166 passed
workbench/frontend: npm run build -> PASS
workbench/frontend: npm audit --omit=dev --audit-level=high -> PASS (no high)
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git SHA 等价性 | `curl https://trade.guangai.ai/api/health` 返回 `version=c3ec920f96587bf9945c4e384fc151fc774f9696`；签收时 `main` HEAD 为 `4c2edd9c8a22aa25e126b6c0b5f92cd0c9ef2de9`，两者 diff 仅 1 个 metadata-only commit |
| 端到端 production focused 验证 | authenticated `GET /api/debug/recent-errors` 返回 `200 {\"count\":0,\"records\":[]}` |
| 关键 invariant | production `/strategies` 仍命中 B026 banner 文案 `研究原型 · 仅含合成数据 · 不构成投资决策依据` |
| 本机数据验证 | `find data/snapshots/fundamentals/sec_edgar -mindepth 1 -maxdepth 1 -type d | wc -l = 27`；`wc -l fundamentals.csv = 686`；`load_fundamentals` 双 spot-check 通过 |

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
| Production version (from `/api/health.version`) | `c3ec920f96587bf9945c4e384fc151fc774f9696` |
| Main HEAD (`git rev-parse HEAD`) | `4c2edd9c8a22aa25e126b6c0b5f92cd0c9ef2de9` |
| Diff (`git log --oneline <deployed>..HEAD`) | `1 commit` — `4c2edd9 chore(B029): F003 generator done → handoff to Codex F004 verifying` |

**判断：PASS。** `git diff c3ec920..HEAD --name-only` 仅含：
- `progress.json`
- `features.json`
- `.auto-memory/project-status.md`

不含 `trade/**`、`workbench/**`、`scripts/**` 或 deploy-impacting 配置，因此按 metadata-only drift 接受不同步。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | `本签收 commit 仅含 progress.json / features.json / .auto-memory / docs/test-reports / docs/screenshots 等证据文件，不含产品代码或 deploy-impacting 配置；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。` |

---

## Soft-watch（不阻塞 done，需后续跟进）

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | unified fundamentals 仅 `685` 数据行，低于 spec 中原始 `≥1000` 目标；`BAC/JPM/V/LIN/NEE/PLD` 六个 ticker 为 sector-structural 0-row，已在 PIT validation 报告中解释 | medium | 在 B030 引入 per-sector ratio model / alias 细化，解决 0-row sector coverage |
| S2 | backend `pytest` 对 evaluator 本机代理环境敏感；若宿主机注入 SOCKS 代理而 `.venv` 无 `socksio`，会出现假阴性 | low | 后续 evaluator 运行 backend tests 时默认 unset `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY` |

---

## Framework Learnings

本批次无 framework learnings。
