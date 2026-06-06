# B037 Home Restructure Signoff 2026-06-06

> 状态：**PASS**
> 触发：B037 F004 fix-round 1 完成后复验通过

---

## 变更背景

B037 将 Home 从旧 quant dashboard 重构为 daily-engagement 中心，落三段结构：`NAV + Day P&L`、`AI Advisor`、`market context + sleeve breakdown`。本批还引入 `price_snapshot` + `workbench-prices.timer` 作为 Day P&L 的生产价格来源，并按 v0.9.31 §16 直接退役旧 Home。

---

## 变更功能清单

### F001：后端 Home 数据基座

**Executor：** generator

**文件：**
- `workbench/backend/workbench_api/routes/home.py`
- `workbench/backend/workbench_api/services/home.py`
- `workbench/backend/workbench_api/services/prices_provider.py`
- `workbench/backend/workbench_api/db/models/price_snapshot.py`
- `workbench/backend/workbench_api/db/repositories/price_snapshot.py`
- `workbench/backend/workbench_api/prices/cli.py`
- `workbench/backend/workbench_api/db/migrations/versions/0009_b037_price_snapshot.py`

**改动：**
新增 `/api/home`、`price_snapshot`、价格读取抽象、每日只读 prices timer，以及 mark-to-market 的 Day P&L / sleeve breakdown 聚合。

**验收标准：**
- `/api/home` auth-gated，payload 结构为 `nav / day_pnl / sleeves`
- `price_snapshot` 路径遵守 §12.10，自包含、只读、无 execution surface

### F002：前端三段 Home

**Executor：** generator

**文件：**
- `workbench/frontend/src/app/(protected)/page.tsx`
- `workbench/frontend/messages/en.json`
- `workbench/frontend/messages/zh-CN.json`

**改动：**
新 Home 替换旧 quant dashboard，渲染三段结构，双语文案，保留 no-execution 边界。

**验收标准：**
- 三段结构在 zh-CN / en 均可见
- 无下单/执行按钮，无中文禁词回归

### F003：旧 Home 退役 + Daily Journey E2E

**Executor：** generator

**文件：**
- `workbench/frontend/tests/e2e/b037-home.spec.ts`
- `workbench/frontend/tests/e2e/protected-routes.spec.ts`
- `workbench/frontend/tests/safety/legacy-home-decommissioned.spec.ts`
- `workbench/frontend/tests/safety/no-execution-buttons.spec.ts`

**改动：**
旧 Home presence→absence 翻转，新增 Daily Journey 双 locale E2E，加入 legacy decommission 守门。

**验收标准：**
- 旧 Home 元素 absent
- 新 Home E2E、i18n、no-execution 守门通过

### F004：Codex L1 + L2 验收

**Executor：** codex

**文件：**
- `docs/test-reports/B037-home-restructure-blocker-2026-06-05.md`
- `docs/test-reports/B037-home-restructure-signoff-2026-06-06.md`
- `docs/screenshots/B037-home-restructure/home-zh-CN.png`
- `docs/screenshots/B037-home-restructure/home-en.png`

**改动：**
完成首轮 blocker 记录、fix-round 1 复验、production `/api/home` 真机 authenticated 验收、浏览器截图与最终签收。

**验收标准：**
- L1 门禁全部通过
- L2 `/api/home` authenticated 200、旧 dashboard absent、prices timer 已安装 enabled、recent-errors 为 0

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| AI Advisor 内容逻辑 | 本批仅承接 B036 已上线组件，不扩 AI 内容本身 |
| market context 数据语义 | 本批只在 Home 中承接卡片位置，不改 B035 数据契约 |
| Reports / Recommendations / Risk 重构 | 留给 B040-B042 |
| broker / execution | 永久不做，Home 继续保持 research-only |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| Home 入口 | 旧 quant dashboard | 三段 daily-engagement Home |
| Day P&L 数据源 | 无生产 mark-to-market 路径 | `price_snapshot` + `workbench-prices.timer` |
| 旧 Home 状态 | 仍有 legacy surface 风险 | 已按 §16 退役并有 absence 守门 |

---

## 类型检查 / CI

```text
backend pytest: 757 passed, 17 skipped
backend targeted smoke: 21 passed
ruff: All checks passed
mypy: Success: no issues found in 247 source files
frontend lint: No ESLint warnings or errors
frontend typecheck: pass
frontend vitest: 198 passed
frontend targeted vitest smoke: 31 passed
playwright (local): 44 passed
```

---

## L2 实测记录（v0.9.9 — BL-031 沉淀）

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | 生产使用 `curl https://trade.guangai.ai/api/health`；返回 `version=77c50faa1b4ea7dc046312ac8c39f47d24ff9fe2`。当前 `main HEAD=710e77e3dd651f232ba6998bbd3e6249dc677c63`，diff 仅 1 个 metadata/state commit `710e77e`，不含产品代码，按 §10 接受等价不同步。 |
| 端到端流验证 | 使用 VM env 派生的临时 Auth.js 会话 cookie 访问 production：authenticated `/api/auth/session` 返回 allowlisted 用户；authenticated `/api/home` 返回 200；authenticated `/` 渲染新 Home，而非 `/login`。 |
| 关键 invariant | authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}`；unauthenticated `/api/home` = `401 Unauthorized`。 |
| 新增 user-facing 路由真 VM authenticated 200（v0.9.32 — B034 沉淀） | `curl -H "Cookie: __Secure-authjs.session-token=<temp>" https://trade.guangai.ai/api/home | jq` 返回 `nav: 0.0`, `day_pnl: null`, `sleeves: [regime, risk_parity, satellite_us_quality]`。这是 spec 允许的空账户路径，不是错误。 |
| 浏览器手动验（如 UI 类） | 用 Playwright 对 production 注入 `__Secure-authjs.session-token` + `NEXT_LOCALE` 做两轮只读手验。`docs/screenshots/B037-home-restructure/home-zh-CN.png` 与 `home-en.png` 均成功落盘；`browser-check.json` 记录两轮 `/api/home` 都是 200，`home-hero` / `home-sleeves` 按钮数均为 0，旧 `dashboard-card-nav` 计数为 0，console errors 为空。 |

> RSC server action / 不可 curl-simulate 类 endpoint：本次登录 happy-path 仍未走真实 Google OAuth 交互，而是使用 production env 派生的临时 session cookie 做 authenticated read-only 验证。对本批 `/api/home` 与首页受保护渲染已足够，不阻塞 done。

---

## Ops 副作用记录（v0.9.9 — BL-030/BL-031 沉淀）

| Agent | 阶段 | 操作摘要 | 副作用对齐 | 用户授权 |
|---|---|---|---|---|
| Generator | fixing | 在 production VM 一次性安装并启用 `workbench-prices.service` / `workbench-prices.timer`，并手动触发一次 `workbench-prices.service` 验证只读路径 | 仅 systemd unit install + timer enable + one-shot read-only fetch；journal 结果为 `price_cli_no_holdings symbols=0 saved=0 errors=0`，未写入持仓/交易类业务数据 | 本轮 fix-round 1 用户已授权 direct VM admin |

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → fixing → reverifying → done）交付。
本签收完成后，`progress.json` 已更新为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Production / HEAD 等价性（v0.9.25 — B022 沉淀）

| 项 | 值 |
|---|---|
| Production version (from `/api/health`) | `77c50faa1b4ea7dc046312ac8c39f47d24ff9fe2` |
| Main HEAD (`git rev-parse HEAD`) | `710e77e3dd651f232ba6998bbd3e6249dc677c63` |
| Diff (`git log --oneline <deployed>..HEAD`) | `710e77e fix(B037-F004): install prod workbench-prices.timer (L2 blocker) → reverifying` |

**等价性判断：**

`git diff --name-only 77c50fa..710e77e` 仅包含：

- `.auto-memory/project-status.md`
- `docs/test-reports/B037-home-restructure-blocker-2026-06-05.md`
- `features.json`
- `progress.json`

无 `workbench/**` / `docs/specs/**` / `framework/**` 等产品代码或运行时配置变更，因此按 §10 接受不同步：production 与 HEAD 产品等价，不阻断签收。

---

## Post-signoff Deploy（v0.9.27 — B025 沉淀）

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | N/A |
| Workflow run 链接（若是） | N/A |
| Production 最终 SHA = signoff commit SHA | N/A |
| 接受不同步声明（若否） | 本次 signoff commit 仅含 signoff 报告、screenshots、`progress.json`、`features.json`、`.auto-memory/project-status.md` 等状态机/证据文件；不含产品代码或 deploy-impacting 改动。按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。 |

---

## Decommission Checklist（v0.9.31 — B030 沉淀）

| 检查项 | 状态 | 证据 |
|---|---|---|
| (1) 退役组件 import + JSX 已从 layout / page 移除 | **是** | production Home 浏览器手验 `oldDashboardCount=0`；legacy testid `dashboard-card-nav` 不再出现 |
| (2) i18n messages JSON 中 namespace keys 已删除 | **是** | `tests/safety/legacy-home-decommissioned.spec.ts` 通过；local targeted vitest smoke 31 passed |
| (3) 组件文件保留 + decommission notice + 重启路径 | **N/A** | 本批直接替换旧 Home，不要求保留可重启 legacy 组件 |
| (4a) 守门测试：`tests/safety/<feature>-decommissioned.spec.ts` 存在 | **是** | `workbench/frontend/tests/safety/legacy-home-decommissioned.spec.ts` 存在且通过 |
| (4b) 隔离测试：`tests/unit/<feature>-component.spec.tsx` 存在 | **N/A** | 本批是首页整体替换，不保留独立 legacy 组件重启路径 |
| (4c) Legacy E2E presence → absence 翻转 | **是** | `workbench/frontend/tests/e2e/b037-home.spec.ts` + `protected-routes.spec.ts` 已将旧 Home 元素翻转为 absence |
| Production HTML grep 组件名 / i18n keys 字面值 | **0 hits** | authenticated production HTML 含 `home-hero` / `home-sleeves`，不含 `dashboard-card-nav` |

---

## Soft-watch（不阻塞 done，需后续跟进）

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | `workbench-prices.timer` 的修复依赖一次性 admin 手工安装；B035/B036/B037 三次重复出现同类摩擦。当前批次已通过，但 deploy 用户 sudoers 仍不足以自动完成这类 timer 安装。 | low | 后续由 Planner 评估是否扩大 deploy sudoers 白名单，让 `deploy.sh` 能自动 install/enable `workbench-*.timer`。 |

---

## Framework Learnings

### 新坑
- Cloud deploy 批次新增 read-only timer 时，endpoint/DB 已绿并不代表 production 运维接线完成；L2 必须直接检查 `systemctl is-enabled` / `status` / timer trigger，而不是只看 health 与表结构。
  - 来源：B037 F004 fix-round 1
  - 建议写入：`framework/harness/evaluator.md`
