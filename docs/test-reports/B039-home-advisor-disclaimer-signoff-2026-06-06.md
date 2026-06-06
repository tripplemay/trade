# B039 Home Advisor Disclaimer Signoff 2026-06-06

> 状态：**PASS**
> 触发：B039 F002 首轮验收通过

---

## 变更背景

B037 已经把 AdvisorSection 复用到 Home 第二段，advice / references / insufficient fallback 都已存在。B039 的实际缺口不是后端能力，而是 personas §2 mockup 里的研究声明没有渲染出来。本批是一个纯前端、最小范围的补齐：在 Home AI Advisor 段把双语 disclaimer 稳定渲染出来，并用守门锁住。

---

## 变更功能清单

### F001：AdvisorSection 双语 disclaimer + 永存守门

**Executor：** generator

**文件：**
- `workbench/frontend/src/components/advisor/AdvisorSection.tsx`
- `workbench/frontend/messages/en.json`
- `workbench/frontend/messages/zh-CN.json`
- `workbench/frontend/tests/unit/advisor/AdvisorSection.spec.tsx`
- `workbench/frontend/tests/unit/messages-key-parity.spec.ts`
- `workbench/frontend/tests/safety/no-execution-buttons.spec.ts`
- `workbench/frontend/tests/e2e/b037-home.spec.ts`

**改动：**
在 AdvisorSection 内增加 `advisor-disclaimer` 元素，双语渲染固定研究声明；ok / insufficient / empty 三态常驻，loading / error 隐藏；同时补齐 i18n key、双语永存守门、no-execution 扩展和 Home Daily Journey 断言。

**验收标准：**
- disclaimer 在 Home AI Advisor 段可见
- zh-CN / en 双语都有
- 无执行/下单按钮
- backend 无改动

### F002：Codex L1 + L2 验收与签收

**Executor：** codex

**文件：**
- `docs/test-reports/B039-home-advisor-disclaimer-signoff-2026-06-06.md`
- `docs/screenshots/B039-home-advisor-disclaimer/advisor-disclaimer-zh-CN.png`
- `docs/screenshots/B039-home-advisor-disclaimer/advisor-disclaimer-en.png`
- `docs/screenshots/B039-home-advisor-disclaimer/browser-check.json`
- `progress.json`
- `features.json`
- `.auto-memory/project-status.md`

**改动：**
完成 frontend targeted L1、production Home 双语免责声明浏览器手验、截图与状态机收口。

**验收标准：**
- L1 targeted frontend tests 全绿
- production disclaimer 双语可见
- `recent-errors=0`
- 旧 dashboard / synthetic banner 不复活

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| `/api/advisor` schema | 本批无后端改动 |
| Master-level 一句话总结 | 用户已明确不做，留后续 |
| AdvisorSection 既有 advice / citations / fallback | 继续沿用 B036/B037 行为，仅追加 disclaimer |
| B038 新闻段 / market-context / Home 三段结构 | 均不改 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| Home AI Advisor 合规提示 | 无 disclaimer | advice / references 下方常驻研究声明 |
| 双语一致性 | mockup 缺口 | zh-CN / en 均补齐 |
| 空 advisor / insufficient 场景 | disclaimer 可能缺失 | empty / insufficient 仍显示 disclaimer |

---

## 类型检查 / CI

```text
frontend targeted vitest: 38 passed
  - tests/unit/advisor/AdvisorSection.spec.tsx
  - tests/safety/no-execution-buttons.spec.ts
  - tests/unit/messages-key-parity.spec.ts
artifact secret grep: 0 hits
generator handoff baseline gates:
  - frontend lint 0
  - frontend typecheck pass
  - frontend vitest 219
  - Playwright green
backend diff: none
```

---

## L2 实测记录（v0.9.9 — BL-031 沉淀）

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | production `/api/health.version=c4efd65f8e48eff3ff16b37cc49b0b2e28059bc7`；签收前 `main HEAD=4abab7b451d7cfda1f66d4240fd003fffaf78d7e`，diff 仅 1 个 metadata commit，按 §Production/HEAD 接受等价不同步。 |
| 端到端流验证 | 注入 production Auth.js session cookie 后访问 Home，第二段 AdvisorSection 正常渲染，disclaimer 在 zh-CN / en 两轮都可见。 |
| 关键 invariant | authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}`。 |
| 新增 user-facing 路由真 VM authenticated 200（v0.9.32 — B034 沉淀） | N/A。本批纯前端，无新路由。 |
| 浏览器手动验（如 UI 类） | headless Playwright 只读手验结果落在 `docs/screenshots/B039-home-advisor-disclaimer/browser-check.json`：两轮都满足 `disclaimerHasSnippet=true`、`disclaimerButtonCount=0`、`advisorButtonCount=0`、`oldDashboardCount=0`、`syntheticBannerCount=0`、console/api errors 为空。 |

> 说明：本批是纯前端 UI 补齐，L2 重点是 production Home 的实际渲染和无回归，不涉及新 API 或 systemd timer。

---

## Ops 副作用记录（v0.9.9 — BL-030/BL-031 沉淀）

本批次无数据库 ops。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → done）交付。
本签收完成后，`progress.json` 已更新为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Production / HEAD 等价性（v0.9.25 — B022 沉淀）

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `c4efd65f8e48eff3ff16b37cc49b0b2e28059bc7` |
| Main HEAD (`git rev-parse HEAD`) | `4abab7b451d7cfda1f66d4240fd003fffaf78d7e` |
| Diff (`git log --oneline <deployed>..HEAD`) | `4abab7b chore(B039): F001 done + Frontend CI green -> status=verifying (handoff to Codex F002)` |

**等价性判断：**

`git diff --name-only c4efd65..4abab7b` 仅含：

- `.auto-memory/project-status.md`
- `features.json`
- `progress.json`

无 `workbench/**`、`docs/specs/**`、`framework/**` 等产品或 deploy-impacting 改动，因此 production 与当前 HEAD 产品等价，不阻断签收。

---

## Post-signoff Deploy（v0.9.27 — B025 沉淀）

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | N/A |
| Workflow run 链接（若是） | N/A |
| Production 最终 SHA = signoff commit SHA | N/A |
| 接受不同步声明（若否） | 本次 signoff commit 仅含 signoff 报告、screenshots、`progress.json`、`features.json`、`.auto-memory/project-status.md` 等状态机/证据文件；不含产品代码或 deploy-impacting 改动。按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需额外 dispatch。 |

---

## Decommission Checklist（v0.9.31 — B030 沉淀）

本批次不含新 decommission，但复核既有 absence 未回归：

| 检查项 | 状态 | 证据 |
|---|---|---|
| 旧 Home dashboard 未复活 | **是** | `browser-check.json` 中 `oldDashboardCount=0` |
| B026 synthetic banner 未复活 | **是** | `browser-check.json` 中 `syntheticBannerCount=0` |

---

## Soft-watch（不阻塞 done，需后续跟进）

无。

---

## Framework Learnings

无。该批次属于纯前端最小范围补丁，现有 v0.9.26 / v0.9.31 守门已足够覆盖。

---

## Conclusion

可以签收。B039 已把 Home AI Advisor 段缺失的双语 disclaimer 补齐，并在 production 上验证了双语可见、no-execution 不回归、旧 dashboard 与 synthetic banner 不复活。
