# B025-us-quality-momentum-satellite Signoff 2026-05-25

> 状态：**PASS**
> 触发：F006 fix-round-4 后，production SHA 等价性恢复，B025 第 4 轮复验完成

## 变更背景

B025 将 Master Portfolio 的 `satellite_us_quality` 从 stub 升级为 implemented strategy，并把 5 因子美股质量动量策略贯通到 workbench 的双语展示面。F006 的职责是对 F001-F005 做 L1 本地验收、L2 真 VM 验收，并在 `Production HEAD ≡ main HEAD` 成立时完成签收。

## 变更功能清单

### F006：Codex L1 + L2 真 VM 验收 + signoff

**Executor：** codex

**文件：**
- `docs/test-reports/B025-us-quality-signoff-2026-05-25.md`
- `docs/screenshots/B025-us-quality/{zh-CN,en}/*.png`
- `progress.json`
- `.auto-memory/project-status.md`

**改动：**
- 完成最终 L1/L2 复核
- 输出 10 张双语截图证据
- 完成 signoff 报告并推进状态到 `done`

**验收标准：**
- 本地关键 smoke 通过
- 生产 5 路由双语通过
- `/api/debug/recent-errors` 为 0
- Production SHA 与 `main` 等价

## 未变更范围

| 事项 | 说明 |
|---|---|
| `trade/**` / `workbench/**` 业务代码 | fix-round-4 之后无新的产品实现改动，本轮仅做复验与签收 |
| 账户状态 | 本批次未做 execution/account 写操作，无需恢复 cash / positions |
| B026 / HK-China satellite | 明确保留在后续批次，不属于 B025 范围 |

## 类型检查 / CI

```text
round-3 已完成完整 L1 绿灯：
- backend: pytest 241 passed, 2 skipped / ruff / mypy
- trade: pytest 727 passed / mypy
- frontend: lint / typecheck / vitest 157 passed / build / npm audit

round-4 确认从 `afa154d` 到验收时 `abaaf6e` 无产品代码差异：
git diff --stat afa154d..abaaf6e
  .auto-memory/project-status.md
  docs/test-reports/B025-us-quality-reverify3-blocker-2026-05-25.md
  progress.json

round-4 focused smoke：
- local `tests/e2e/b025-us-quality-bilingual.spec.ts` → 14 passed
```

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git_sha == main HEAD | `curl https://trade.guangai.ai/api/health` 在签收前返回 `version=abaaf6e6a162d0ce73305e71ec1c29b54512da5f`，与当时 `git rev-parse HEAD` 一致 |
| 端到端流验证 | 用 `__Secure-authjs.session-token` 分别在 `zh-CN` / `en` 下走 `/strategies` → `/recommendations` → `/risk` → `/reports` → `/reports/B025-us-quality-momentum-backtest`，全部渲染出 B025 surface |
| 关键 invariant | `/api/debug/recent-errors` 返回 `200 {"count":0,"records":[]}` |
| 浏览器手动验 | 截图证据已落盘到 `docs/screenshots/B025-us-quality/{zh-CN,en}/` |
| locale switch 最小复现 | production 上 zh-CN → en → `/risk` 的 focused repro `3/3` 成功，`NEXT_LOCALE=en` 可持久到下一页 |

> 聚合脚本里 locale switch 曾偶发回退为中文；focused 最小复现稳定通过，判定为脚本时序噪音而非产品缺陷。

## Ops 副作用记录

本批次无数据库 ops。

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → fixing/reverifying 多轮循环 → done）交付。
`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `abaaf6e6a162d0ce73305e71ec1c29b54512da5f` |
| Main HEAD (`git rev-parse HEAD`) | `abaaf6e6a162d0ce73305e71ec1c29b54512da5f` |
| Diff (`git log --oneline <deployed>..HEAD`) | `0 commits` |

签收提交本身只会引入 signoff / 状态机元数据。为避免再次出现 metadata-only drift，本次 signoff 提交后会立即执行 `gh workflow run "Workbench Deploy" -r main`，把 production 追到最终 signoff SHA。

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 本地 `3000/8723` 若残留旧栈，会把 Playwright 结果污染成假红 | low | 继续坚持 `lsof` 检查 + `bash scripts/test/codex-setup.sh` 前台唯一启动 |
| S2 | `fixing -> reverifying -> done` 的状态机 chore commit 会天然制造 metadata-only deploy drift | medium | framework v0.9.27 应沉淀 deploy race 处理规范，避免每轮靠 ad-hoc dispatch 收尾 |

## Framework Learnings

### 新规律
- chore-only `main` commits 也需要可手动 deploy 的逃生口，否则 cloud batch 的 `Production HEAD ≡ main HEAD` 会被状态机提交反复打破

### 新坑
- 复验时如果直接复用未知来源的本地 `3000/8723` 进程，Playwright 红灯可能只是旧 bundle 污染

### 模板修订
- Signoff 模板可增加一条说明：若签收提交只带元数据而会推进 `main`，Evaluator 应在 close-out 中显式记录 post-signoff deploy 策略
