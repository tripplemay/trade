# B024 — Workbench i18n (zh-CN + en)

> Status：active (planning → building)
> Owner：Generator (F001-F005) + Codex (F006)
> Predecessor：B023 (Workbench Phase 2 — Manual Execution UI)
> 估时：3-4 周
> 范围分类：post-MVP feature batch（不在 PRD §10/§11/§12 内）

## 1. 目标

让 workbench (`https://trade.guangai.ai`) 支持中英双语，**默认中文**。用户可在 Header 右上角一键切换，cookie 持久。

所有 PRD §5 非 MVP 边界 + B012/B021/B022/B023 永久硬边界 100% 继承。本批次只动 i18n 表层，不动业务逻辑、不动 DB schema、不动 broker boundary、不动安全 guard。

## 2. 决策矩阵（用户已批）

| 维度 | 决策 |
|---|---|
| 库 | `next-intl` v3（Next.js 15 App Router 原生 RSC 支持，cookie-based locale） |
| 语言集 | `zh-CN` + `en` |
| 默认 locale | `zh-CN`（首访 cookie 缺省视为 zh-CN） |
| 切换 UX | Header 右上角下拉 `中文 / English`，写 `NEXT_LOCALE` cookie，刷新即生效 |
| URL 路由 | **不加 locale prefix**（保持现有 `/(protected)/...` 路由不变；middleware 仅读写 cookie） |
| 翻译范围 | (a) 前端 UI 所有 hardcoded 字符串 (b) 后端 API HTTPException detail 文本 (c) Order ticket Markdown 模板 + disclaimer |
| 不翻范围 | docs/dev/*.md / docs/specs/*.md / docs/prd/*.md / 注释 / 变量名 / SQL / log 文本 |
| 专业术语 | Sharpe / drawdown / slippage / bps / kill-switch / rebalance / sleeve / Top N / ETF / momentum 等保留英文不译 |
| Disclaimer | **双语并存**：英文原句保留（不破现有 unit test 断言）+ 中文译句加在下一行；Markdown 永不按 locale 变化（保历史 diff 稳定） |
| 中文按钮禁词 | 「执行」「下单」「发送券商」「立即买入」「实盘」「真实交易」「自动交易」「一键交易」等永远不可作为按钮 label（与英文 `execute`/`place order`/`send to broker` 同性质 enforced） |

## 3. 永久硬边界（B024 起继续 enforced）

继承 B012/B021/B022/B023 所有边界，**i18n 不放宽任何一条**：

- 无 broker SDK 引入 / 无 paper/live API URL / 无凭证 / 无自动下单
- 单用户 / 无注册 UI / 单 email allowlist / 无 multi-user 路径
- 同源 `/api/*`（v0.9.24 #3）/ Repository pattern / auth-gated
- 中文按钮 label 不可含 §2 禁词（同 Vitest grep + Playwright assert L1 强制规则，扩中文集）
- Order ticket Markdown 必含英文 disclaimer 字面串 `'research-only; this is a manual review checklist, not a trading instruction'`（unit test 断言；本批次只**新增**中文双语断言，**不替换**英文断言）
- Production HEAD ≡ main HEAD（v0.9.25 §Production/HEAD 等价性）

## 4. 技术架构

### 4.1 前端

```
workbench/frontend/
├── messages/
│   ├── zh-CN.json     # 翻译 key 嵌套 by namespace: { common, header, sidebar, home, strategies, recommendations, risk, logs, backtest, data, execution: { positionDiff, ticket, fills, journalHistory, account, riskPanel }, auth, errors, toast, form }
│   └── en.json        # 同 schema 英文原版
├── src/
│   ├── i18n.ts        # next-intl config: locales=['zh-CN', 'en'], defaultLocale='zh-CN', loadMessages()
│   ├── middleware.ts  # 现有 NextAuth 中间件 chain + next-intl locale detection（先 auth 后 locale）
│   └── components/
│       └── LocaleSwitcher.tsx  # Header 下拉，setLocaleCookie('NEXT_LOCALE', value, 365d)
└── next.config.mjs    # 加 next-intl plugin createNextIntlPlugin('./src/i18n.ts')
```

**Server / RSC**：用 `getTranslations('namespace')` async。
**Client**：用 `useTranslations('namespace')` hook。
**类型**：定义 `messages/zh-CN.json` 为权威 schema → `declare module 'next-intl'` 加 `IntlMessages = typeof zhCNMessages`；Codex L1 类型检查跑 `npx next typecheck` 命中 `t('foo.bar')` typo。

### 4.2 后端

**不引入新 dep**。在 `workbench/backend/workbench_api/i18n/` 加：

```python
# messages.py
MESSAGES: dict[str, dict[str, str]] = {
    'zh-CN': {
        'errors.invalid_csv_row': '第 {row} 行：{detail}',
        'errors.unknown_ticket': '订单清单 {ticket_id} 不存在',
        # ... ~25 keys
    },
    'en': {
        'errors.invalid_csv_row': 'Row {row}: {detail}',
        'errors.unknown_ticket': 'Order ticket {ticket_id} not found',
        # ... 同集
    },
}

def t(key: str, locale: str, **kwargs) -> str: ...  # fmt.format(**kwargs)
def detect_locale(request: Request) -> str: ...  # ?locale=... > Accept-Language > 'zh-CN'
```

FastAPI dependency `Depends(detect_locale)` 注入每个 endpoint；`HTTPException(status_code=400, detail=t('errors.invalid_csv_row', locale, row=N, detail='...'))`。

所有现有 raise 站点（约 25 处）grep 全量改造。pytest fixture：parametrize over `['zh-CN', 'en']` × 至少一个 error 路径每 endpoint。

### 4.3 Order Ticket Markdown

模板（双语永远并排，不按 locale 变）：

```markdown
# Order Ticket {ticket_id}

> **research-only; this is a manual review checklist, not a trading instruction**
> **仅供研究使用；这是一份人工核对清单，不构成交易指令**

## Trades to place / 待下达交易
| Symbol | Side | Shares | Notes |
|---|---|---|---|
...

## After execution checklist / 执行后核对清单
- [ ] Recorded fills in workbench / 在 workbench 记录成交
- [ ] Reconciled ticket / 完成订单对账
- [ ] Updated account snapshot / 更新账户快照
```

Unit test：
- 保留原英文断言：`assert 'research-only; this is a manual review checklist, not a trading instruction' in markdown`
- 新增中文断言：`assert '仅供研究使用；这是一份人工核对清单，不构成交易指令' in markdown`
- 新增双语字段断言：`assert 'Trades to place / 待下达交易' in markdown`

## 5. Feature 拆分

### F001 — i18n 基建（generator，3-4 天）

**Acceptance：**
- `workbench/frontend/package.json` 加 `next-intl@^3`
- `workbench/frontend/src/i18n.ts` + middleware chain（NextAuth + next-intl 共存验证）
- `workbench/frontend/messages/{zh-CN,en}.json` 起始骨架（common namespace + nav 项 ≥10 keys）
- `LocaleSwitcher` Header 下拉，写 `NEXT_LOCALE` cookie maxAge 365d
- 首访 cookie 缺失 → 视为 `zh-CN`
- TypeScript 类型链通：`t('common.foo.typo')` typecheck 报错
- Codex L1 grep `*\.tsx?$` 残余 hardcoded 英文字符串（白名单：技术术语 §2 + 注释 + log）
- 验收：`bash scripts/test/codex-setup.sh` 启动后 home 页 zh-CN 默认 + 切换 en + 切回 zh-CN cookie 持久
- vitest 117 baseline + 新加 LocaleSwitcher 单测 + middleware 单测 ≥120
- `npm audit --omit=dev --audit-level=high` exit 0；build artifact 无 127.0.0.1

### F002 — 前端 UI 翻译 Pass A（generator，8-10 天）

**Acceptance：**
- 9 页全量翻译（Header / Sidebar / Home / Strategies / Recommendations / Risk / Logs / Backtest Runs / Data）+ 共享组件（AllocationBar / DataTable / Chart 标题 / Loader）
- 翻译 key 嵌套合理（按页 namespace）；no flat keys >3 层
- `messages/zh-CN.json` 与 `messages/en.json` key set **bit-identical**（CI 跑 `diff <(jq keys-recursive zh-CN.json) <(jq keys-recursive en.json)` exit 0）
- Playwright zh-CN + en 双 locale 跑 9 页 smoke：每页 H1 + 至少 3 个 nav/label assertion 双 locale
- 截图 9 页 × 2 locale = 18 PNG ≤300 KB 存 `docs/screenshots/B024-i18n/{zh-CN,en}/`
- Codex L1 grep 残余英文 hardcode：≤5 项白名单（技术术语）
- vitest + lint + typecheck + build 绿；same-origin regression 绿

### F003 — 前端 UI 翻译 Pass B（generator，6-8 天）

**Acceptance：**
- 5 execution 页全量（position-diff / ticket / fills / journal-history / account）+ NextAuth login + 所有 toast / form validate / error page
- 中文按钮禁词 grep 新规则（Vitest）：`['执行', '下单', '发送券商', '立即买入', '实盘', '真实交易', '自动交易', '一键交易']` 任一作为按钮 label 直接 fail
- Form validate 消息双 locale（cash≥0 / weights≤1 / 无重复 symbol / positive shares 等）
- Toast 错误消息接 backend `Accept-Language` 协议（F004 完成后联调）
- Playwright zh-CN + en 跑 manual execution 主链：position-diff → ticket → fills upload → reconcile → journal-history 至少 5 个 assertion 双 locale
- 截图 5 页 × 2 = 10 PNG 存 `docs/screenshots/B024-i18n/{zh-CN,en}/execution/`
- 共 zh + en 各 14 张截图（9 + 5）= 28 PNG

### F004 — 后端 API error i18n（generator，3-5 天）

**Acceptance：**
- `workbench/backend/workbench_api/i18n/messages.py`（dict-of-dict，无新 dep）+ `detect_locale` 依赖
- 25 个 HTTPException 站点全量改造（grep `raise HTTPException` 全覆盖）
- API contract：`Accept-Language: zh-CN`（前端 fetch wrapper 自动带）+ `?locale=zh-CN` 覆盖
- Pytest parametrize `['zh-CN', 'en']` × 每 endpoint 至少 1 个 error 路径
- 前端 fetch wrapper 自动注入 `Accept-Language` header（基于当前 locale cookie）
- F003 toast 消息端到端连通（点击 invalid CSV → backend 返中文 → toast 显示中文）
- pytest 202 baseline + 新加 ≥30 测试 ≥232；ruff + mypy 清

### F005 — Order ticket Markdown 双语 + 模板字段（generator，1-2 天）

**Acceptance：**
- 模板按 §4.3 改造，双语永远并存（不按 locale 切换 Markdown 文件内容）
- Unit test 保留原英文断言 + 加中文断言 + 加双语字段断言（≥3 个）
- 历史 ticket（B023 留下的 `tkt-20260519-99d04c95`）re-generate 测试：旧 ticket 不变（DB 已落 schema 不动），新 ticket 产出双语 Markdown
- Markdown 文件名格式不变（`order-ticket-<id>.md`）
- pytest 全绿；Playwright ticket detail page assert 双语 disclaimer 双块都可见

### F006 — Codex L1+L2 真 VM 验收 + signoff（codex，2-3 天）

**L1 (CI 内)：**
- F001-F005 全部 generator 验收脚本跑通（vitest / lint / typecheck / build / pytest / ruff / mypy / npm audit / same-origin / safety regression）
- 新加：`diff jq keys-recursive zh-CN.json en.json` exit 0（key set 完整）
- 新加：grep 中文按钮禁词 Vitest 测试通过
- 新加：grep 前端残余英文 hardcode 字符串 ≤5 白名单
- Playwright `19 + N` passed（N 为 zh/en 双 locale 新增测试数）

**L2 (真 VM)：**
- OAuth → Home zh-CN 默认渲染中文 ✓
- LocaleSwitcher 切 en → 整站英文（含 NextAuth login signout 后再 login 也是 en） ✓
- 切回 zh-CN cookie 持久 ✓
- 全 manual execution 流程跑一遍 zh-CN locale + 一遍 en locale（seed account → ticket → fill CSV → reconcile → journal → slippage → debug recent-errors count=0）
- Markdown ticket 文件 disclaimer 双语 + 字段双语都出现
- `/api/execution/account` PUT 故意触发 validate error（cash<0）→ Accept-Language=zh 返中文 detail；?locale=en 覆盖返英文 detail
- Production HEAD ≡ main HEAD
- `/api/debug/recent-errors` count=0
- 副作用恢复（同 B023 模式：account 恢复 cash=0 / positions=[]）

**Signoff：**
- `docs/test-reports/B024-i18n-signoff-2026-MM-DD.md` 用 `framework/templates/signoff-report.md`（含 §Production/HEAD 等价性 段）
- Framework v0.9.26 候选记录：
  1. **i18n 中文按钮禁词扩集**（与英文禁词同等约束，写入 generator.md §safety regression）
  2. **next-intl + NextAuth middleware chain pattern**（写入 generator.md §13 sub-pattern #6 或新 §15）
  3. **bilingual disclaimer 双语永远并存策略**（compliance 内容禁按 locale 分支，避免历史 diff 混乱；写入 generator.md 或新 compliance policy 章节）

## 6. 不做的事（YAGNI）

- ❌ URL prefix 路由（`/zh-CN/...` / `/en/...`）—— single-user + auth-gated，不需要 SEO
- ❌ 翻译 docs/ 任何文件
- ❌ 后端引入 babel / gettext / fluent 等重型 i18n 库
- ❌ Pydantic validation error 后端翻译（前端用 react-hook-form + next-intl 翻译已足够）
- ❌ 译稿翻译记忆 / TMS 集成
- ❌ 第三种语言（zh-Hant / ja / ko）—— spec 不为未来扩展预留任何抽象，要加再起新 batch

## 7. 验收门槛汇总

| 门槛 | F# 责任 |
|---|---|
| 默认渲染 zh-CN（cookie 缺省 + 切 en + 切回 zh-CN 持久） | F001 |
| zh-CN / en JSON key set bit-identical | F002 |
| 中文按钮禁词 Vitest grep | F003 |
| 前端 fetch 自动注入 Accept-Language | F004 |
| backend HTTPException detail i18n + pytest parametrize | F004 |
| Markdown disclaimer 双语并存 + unit test 双断言 | F005 |
| L1 vitest + lint + typecheck + build + pytest + ruff + mypy + npm audit 全绿 | F006 |
| L2 真 VM zh + en 双 locale 走通 manual execution 完整链路 | F006 |
| Production HEAD ≡ main HEAD | F006 |
| `/api/debug/recent-errors` count=0 after full L2 flow | F006 |
| Signoff 报告 framework/templates/signoff-report.md 全段 | F006 |

## 8. 参考文档

- `docs/prd/mvp-completion-declaration-2026-05-20.md` — MVP 完工范围
- `docs/specs/B023-workbench-phase2-manual-execution-spec.md` — manual execution 边界
- `framework/harness/generator.md` §10 (safety regression) / §12-13 (cloud deploy patterns) / §14 (FastAPI 观测)
- `framework/templates/signoff-report.md` (含 §Production/HEAD 等价性)
- `framework/CHANGELOG.md` v0.9.25
- next-intl docs：https://next-intl-docs.vercel.app/docs/getting-started/app-router

---

> 本 spec 完成后，progress.json status=building，current_sprint=F001，Generator 接 i18n 基建。
