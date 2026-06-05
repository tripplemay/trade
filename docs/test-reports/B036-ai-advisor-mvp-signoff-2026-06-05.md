# B036 AI Advisor MVP Signoff 2026-06-05

> 状态：**已签收**
> 触发：B036 F001-F003 已完成，production 上 alembic 0008、advisor timer、当日 precompute 与 `/api/advisor` 已就绪，进入 F004 首轮验收。

---

## 变更背景

B036 是项目首次真正生成式 AI 批次，也是 **里程碑 B / Phase 2 终点**。本批把 quant signal、B034 news、B035 market context 组合成 grounding，调用 gateway 生成结构化 AI 建议，并通过 B032 的 red-team judge gate 强制执行安全边界。首页新增 AI Advisor 段，production 每日预计算 advisor 结果落库，由 `/api/advisor` 向前端提供只读数据。

---

## 变更功能清单

### F001-F003：Generator 交付范围

**Executor：** generator

**改动：**
- 新增 advisor grounding / schema / service / repository / alembic `0008_b036_advisor`
- 把 red-team 15 样本接到真实 `AdvisorService` + 真 judge
- 新增 `workbench-advisor.timer` / `.service`
- 新增 `/api/advisor` 与 Home `AI Advisor` 段

**验收结果：**
- L1 后端 / 前端 / Playwright 全通过
- AI Safety Eval workflow 对 `9cce841...` 成功
- L2 production 上 `/api/advisor`、advisor timer、当日 precompute、Home AI Advisor 段均通过

### F004：Codex L1 + L2 真 VM 验收 + signoff

**Executor：** codex

**文件：**
- `docs/test-reports/B036-ai-advisor-mvp-signoff-2026-06-05.md`
- `docs/screenshots/B036-ai-advisor-mvp/home-ai-advisor-production.png`
- `docs/screenshots/B036-ai-advisor-mvp/strategies-banner-absence.png`
- `docs/screenshots/B036-ai-advisor-mvp/alembic-current-0008.png`
- `docs/screenshots/B036-ai-advisor-mvp/advisor-response.json`

**验收标准：**
- L1：pytest / ruff / mypy / alembic roundtrip / frontend lint+typecheck+vitest+Playwright / AI safety workflow latest success
- L2：production health / authenticated `/api/advisor` 200 / recent-errors / DB head=0008 / advisor timer enabled / Home AI Advisor 段手验 / no-execution UI boundary

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 交易执行面 | AI Advisor 只生成研究建议，不触达 broker / order / execution |
| B033 news scheduler 边界 | 仍保持无 news scheduler / cron / APScheduler |
| B035 market-context 基础设施 | 本轮只复验其被 B036 grounding 复用，不改 B035 既有行为 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| Home AI 建议 | 无生成式建议 | 显示按 sleeve 预计算的结构化 AI 建议 |
| Production `/api/advisor` | 无 | auth-gated 200，返回 3 个 sleeve 的建议 |
| 每日 advisor 预计算 | 无 | `workbench-advisor.timer` enabled + active |

---

## 类型检查 / CI

```text
backend pytest: 735 passed, 17 skipped
B036 focused backend guards: 31 passed
backend ruff: pass
backend mypy: pass (233 source files)
alembic: 0008_b036_advisor -> 0007_b035_market_context -> 0008_b036_advisor
frontend lint: pass
frontend typecheck: pass
frontend vitest: 185 passed
frontend Playwright: 41 passed
GitHub Actions ai-safety-eval.yml latest run: success (headSha=9cce841fbd3d2bc49d87a17b94f81571f5f328cc)
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Staging / production git_sha 与 main HEAD 等价 | production `/api/health.version = 9cce841fbd3d2bc49d87a17b94f81571f5f328cc`；签收前 `main HEAD = d29717124284f164e2c9de37570197f09d799c1d`；`git diff --name-only 9cce841..HEAD` 仅 `.auto-memory/project-status.md` + `progress.json` 两个状态机文件，产品代码无漂移 |
| 端到端流验证 | authenticated `/api/protected-test` = `{"status":"ok","email":"tripplezhou@gmail.com"}`；authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}` |
| 关键 invariant | anonymous `GET /api/advisor` = 401；authenticated `GET /api/advisor` = 200；返回 `regime` / `risk_parity` / `satellite_us_quality` 三个 sleeve，全部 `status=ok`，模型为 `claude-haiku-4.5`；AI Safety Eval workflow latest run 对同一 deployed SHA 为 success |
| 新增 user-facing 路由真 VM authenticated 200 | `/api/advisor` 返回结构化字段 `sleeve/advice/rationale/references/status/generated_at`；引用中仅见 `quant_signal_sha`，未出现越界 URL；响应落盘：`docs/screenshots/B036-ai-advisor-mvp/advisor-response.json` |
| 浏览器手动验 | production Home AI Advisor 段正常渲染 3 个 sleeve，无下单按钮，截图：`docs/screenshots/B036-ai-advisor-mvp/home-ai-advisor-production.png`；策略页 B026 banner 未复活，截图：`docs/screenshots/B036-ai-advisor-mvp/strategies-banner-absence.png` |

---

## Ops 副作用记录

| Agent | 阶段 | 操作摘要 | 副作用对齐 | 用户授权 |
|---|---|---|---|---|
| Generator | building / fixing | 升 production alembic 0008；安装启用 `workbench-advisor.timer`；手动运行 advisor precompute；修复 SQLite writer lock，重新部署 `9cce841` | DB schema、timer、当日 advisor 结果同步就位；market/news 边界保持 | 用户已允许 production 前置与复验 |
| Evaluator | verifying | 只读验证 `/api/health`、authenticated API、systemd、DB、workflow 状态、浏览器截图 | 无写入动作 | 用户本轮要求开始验收 |

---

## Harness 说明

本批经 `planning -> building -> verifying -> done` 闭环完成。`docs.signoff` 已写入本报告路径。**里程碑 B / Phase 2 终点达成。**

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `9cce841fbd3d2bc49d87a17b94f81571f5f328cc` |
| Main HEAD (`git rev-parse HEAD`) | `d29717124284f164e2c9de37570197f09d799c1d` |
| Diff (`git log --oneline <deployed>..HEAD`) | `d297171 chore(B036): record L2 prereqs ready (advisor precompute errors=0 on prod, 9cce841)` |

判断：接受不同步。`git diff --name-only 9cce841..HEAD` 仅含 `progress.json` 与 `.auto-memory/project-status.md`，属于状态机元数据，production 与当前产品代码等价。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | N/A |
| Workflow run 链接（若是） | N/A |
| Production 最终 SHA = signoff commit SHA | N/A |
| 接受不同步声明（若否） | 本次签收提交仅包含 signoff 报告、截图、`progress.json`、`features.json`、`.auto-memory/project-status.md` 等元数据/证据文件，不含产品代码或 deploy-impacting 配置；按 v0.9.25 §Production/HEAD 等价性接受不同步，无需 post-signoff deploy。 |

---

## Decommission Checklist

本批次不含新的 decommission。L2 仅回归确认 B026 synthetic banner 未复活。

---

## Soft-watch

无。

---

## Framework Learnings

本批次无新增 framework learnings。B036 的 production writer-lock 问题已由 generator 修入实现与单测，本轮未出现新的通用验收缺口。
