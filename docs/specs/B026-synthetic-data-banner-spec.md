# B026 — Synthetic Data Banner（防误用）

> Status：active (planning → building)
> Owner：Generator (F001) + Codex (F002)
> Predecessor：B025 (US Quality Momentum Satellite) — done 2026-05-25
> 估时：1 个轻量批次（参考 Phase 0 Lead-in 定位）
> 范围分类：post-MVP product alignment batch（Stream 0 / Phase 0；属 implementation-path-2026-05.md §4 第一个 batch）

## 1. 目标

在 workbench Layer 0 期间（所有 sleeve / 回测 / Recommendations / Risk Panel 仍基于 fixture 数据），所有 protected 页面顶部加持久 banner，**明确但克制**地标注 "Research prototype · Synthetic data only · Not for investment decisions" / "研究原型 · 仅含合成数据 · 不构成投资决策依据"，防止用户 / 任何看到 workbench 的人误把 synthetic 数字当作真实投资依据。

继承 framework v0.9.28 + B024 i18n + B025 双语 disclaimer 边界，不动业务逻辑、不动 DB schema、不动 broker 边界。

## 2. 决策矩阵（2026-05-25 用户已批）

| 维度 | 决策 |
|---|---|
| 显示位置 | 所有 protected pages 顶部（layout level，自动覆盖 Home / Strategies / Strategies/[id] / Recommendations / Risk / Reports / Reports/[slug] / Backlog / Backtest / Snapshots / Data / Logs / 5 execution 页 + login 页除外）|
| 可关闭性 | **本会话隐藏**（React state，session 级；reload / 跳走再回 / OAuth 后均**重现**）|
| Layer 状态控制 | **env var 手动控制**：`NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true`（默认）/ `=false`（隐藏）。Phase 1 Real Data 完成后由用户手动改 `.env.production` |
| 文案语气 | **明确但克制**。en: `Research prototype · Synthetic data only · Not for investment decisions`。zh-CN: `研究原型 · 仅含合成数据 · 不构成投资决策依据` |
| 视觉风格 | 浅黄 / 浅红 背景 + 暗色文本 + 信息图标（不走红色 WARNING / 不走 friendly 动画）；高度 ~36-48px；不遮挡内容（占 layout 一行）|
| 关闭按钮 | 右侧 `×` 按钮（aria-label 双语）；点击后本会话不再渲染（仅在当前 React tree 内 state.dismissed=true）|
| 双语 | 继承 B024 i18n：新 namespace `syntheticBanner.*`（headline / aria-close）；messages bundle key set bit-identical |
| 不在范围 | 登录页（不需要） / public 路径（无 protected 路径） / Markdown 报告内（已含双语 disclaimer） |

## 3. 永久硬边界（B026 起继续 enforced）

继承 B012-B025 + framework v0.9.28 全部边界，**本批次不放宽任何一条**：

- 系统层：no broker SDK / no live URL / no credential / no auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository pattern
- UI 层：中文按钮禁词（v0.9.26）/ Order ticket Markdown 双语 disclaimer 永存
- 数据 / CI 层：fixture-first 离线 CI / cloud-deploy 批次 deploy workflow 含 workflow_dispatch + Generator chore commit 后 dispatch deploy（v0.9.27）
- AI 边界 5 子条（v0.9.28）— 本批次不引入 AI，但 spec 仍列出（生效信号已固化）
- Production HEAD ≡ main HEAD（v0.9.25 §Production/HEAD 等价性）

## 4. 技术架构

### 4.1 前端组件

```
workbench/frontend/src/
├── components/
│   └── SyntheticDataBanner.tsx     # 新建：banner 主组件
├── app/
│   └── (protected)/
│       └── layout.tsx              # 改：layout 顶部插入 <SyntheticDataBanner />
└── lib/
    └── env-flags.ts                # 新建（或扩展既有）：读 NEXT_PUBLIC_SYNTHETIC_DATA_BANNER
```

### 4.2 组件设计

```tsx
// src/components/SyntheticDataBanner.tsx
'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Info, X } from 'lucide-react';

export function SyntheticDataBanner() {
  const t = useTranslations('syntheticBanner');
  const [dismissed, setDismissed] = useState(false);

  const enabled = process.env.NEXT_PUBLIC_SYNTHETIC_DATA_BANNER !== 'false';
  if (!enabled || dismissed) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-3 bg-amber-50 border-b border-amber-200
                 px-4 py-2 text-sm text-amber-900 dark:bg-amber-950
                 dark:border-amber-800 dark:text-amber-100"
    >
      <Info className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <span className="flex-1">{t('headline')}</span>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        aria-label={t('ariaClose')}
        className="hover:bg-amber-100 dark:hover:bg-amber-900 rounded p-1"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
```

### 4.3 i18n messages

`workbench/frontend/messages/zh-CN.json` + `en.json` 加新 namespace：

```json
{
  "syntheticBanner": {
    "headline": "研究原型 · 仅含合成数据 · 不构成投资决策依据",
    "ariaClose": "关闭此提示"
  }
}
```

英文版：

```json
{
  "syntheticBanner": {
    "headline": "Research prototype · Synthetic data only · Not for investment decisions",
    "ariaClose": "Dismiss this notice"
  }
}
```

### 4.4 Layout 集成

```tsx
// src/app/(protected)/layout.tsx
import { SyntheticDataBanner } from '@/components/SyntheticDataBanner';

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SyntheticDataBanner />
      <TopBar />
      <div className="flex">
        <SideNav />
        <main>{children}</main>
      </div>
    </>
  );
}
```

### 4.5 Env Var

`.env.example` 加：

```
# Synthetic data banner（Layer 0 期间防误用）
# 设 false 在 Phase 1 Real Data 完成后隐藏 banner
NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true
```

`.env.production`（部署 VM 上）保持 `=true` 直到 Phase 1 完成。

## 5. Feature 拆分

### F001 — Banner 组件 + Layout 集成 + 双语 messages + 测试（generator，2-3 天）

**Acceptance：**

(1) `src/components/SyntheticDataBanner.tsx`：'use client' + React useState dismissed + env flag check + lucide-react Info/X 图标 + 浅黄背景 + 双语 useTranslations('syntheticBanner') + aria-live="polite" + aria-label 双语 close button

(2) `messages/zh-CN.json` + `messages/en.json` 加 `syntheticBanner.headline` + `syntheticBanner.ariaClose`；key set bit-identical（既有 vitest `messages-key-parity.spec.ts` 通过）

(3) `src/app/(protected)/layout.tsx` 顶部插入 `<SyntheticDataBanner />`（不入 login 页 / 不入 root layout）；其他 layout 结构不动

(4) `.env.example` 加 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true` 注释行；`.env.production`（VM 上）保持 true；本机 dev 默认 true

(5) vitest 新增 ≥6 测试覆盖：
- env flag enabled + dismissed=false → 渲染
- env flag enabled + dismissed=true → 不渲染（点 × 后）
- env flag disabled → 不渲染
- key parity zh-CN/en 同步
- 双语 headline 文案断言（en + zh-CN 各一）
- aria-label / aria-live 可访问性断言

(6) Playwright 双 locale smoke：
- zh-CN: visit protected page → banner headline contains "研究原型 · 仅含合成数据"
- en: switch locale → banner headline contains "Research prototype · Synthetic data only"
- 点 × 后同会话 reload → banner 重新出现
- 至少 4 个新 Playwright assertion（双 locale × 2 行为）

(7) `tests/safety/no-execution-buttons.spec.ts` 既有 ≥15 spec assertions 0 命中（含中文禁词；新 banner 文案不含禁词）

(8) Gates：
- `npm run lint` exit=0
- `npm run typecheck` exit=0
- `npm test` ≥156 baseline + ≥6 新增 = ≥162 passed
- `npm run build` standalone OK
- `npm audit --omit=dev --audit-level=high` exit=0
- `grep -rE 'http://127\.0\.0\.1:|http://(127\.0\.0\.1|localhost):872[0-9]' .next/static/` exit=0
- Backend 不动；既有 backend pytest ≥320 不破

(9) **不动**：
- B024 i18n 既有 16 namespace（仅新增 1 namespace 不动旧）
- B023 manual execution flow / B022 workbench 6 页表 / B021 cloud deploy / B020 dev infrastructure
- DB schema / backend endpoint / strategy 代码 / Markdown 报告模板（已含双语 disclaimer 不变）
- AI 边界（本批次不引入 AI）

### F002 — Codex L1 + L2 真 VM 验收 + signoff + framework 候选记录（codex，1 天）

**L1 (CI 内)：**

- F001 generator 验收脚本全过：lint / typecheck / vitest ≥162 / build / npm audit / 同源 regression / safety regression
- messages key parity vitest 严格相等
- 中文按钮禁词 vitest grep 0 命中（含新 banner 文案）
- Backend pytest ≥320 + ruff + mypy 不破（本批次不动 backend）
- Playwright ≥29 baseline + ≥4 新 banner 双 locale = ≥33 passed

**L2 (真 VM)：**

1. OAuth → Home 默认 zh-CN：banner 头部"研究原型 · 仅含合成数据 · 不构成投资决策依据" 可见
2. 切 en → banner 头部 "Research prototype · Synthetic data only · Not for investment decisions" 可见
3. 切回 zh-CN cookie 持久 + banner 跟随切换
4. 5 protected 路由全部出现 banner（/strategies / /recommendations / /risk / /reports / /backtest 抽样 ≥3 个）
5. 点 banner × 后同会话页面不再显示；reload 后重新出现
6. Markdown 报告（B024 既有双语 disclaimer）不受影响
7. `/api/debug/recent-errors` count=0 after full L2 flow
8. Production HEAD ≡ main HEAD（同 SHA；本批次仅前端改动，触发 frontend CI → workbench-deploy.yml）
9. 副作用：本批次不动 account state；不需恢复

**Signoff：**

- `docs/test-reports/B026-synthetic-data-banner-signoff-2026-MM-DD.md` 用 `framework/templates/signoff-report.md`（含 §Production/HEAD 等价性 + §Post-signoff Deploy 双段；v0.9.27 / v0.9.28 模板）
- `docs/screenshots/B026-banner/{zh-CN,en}/` ≥4 PNG（zh + en 各 2 张：home + reports 或 strategies）

**Framework 候选记录（按 done 阶段评估）：**

预计本批次属"轻量 lead-in"，无重大新规律。若 fix-round 出现意外信号（如 banner 与既有 i18n 冲突 / Layer 状态语义不清），记录在 signoff §Framework Learnings 段。否则按 framework v0.9.28 留空。

## 6. 不做的事（YAGNI）

- ❌ 关闭按钮永久 cookie 记忆（违反"防误用"初衷；每次会话 reload 后 banner 重现是 by design）
- ❌ Layer 状态机自动判断（用户偏好 env var 手动控制；机制简单可靠）
- ❌ 红色 WARNING / 友好动画 / 闪烁（明确但克制是选定语气）
- ❌ Banner 上加 "see roadmap" 链接到 docs/product/positioning（external link 在 banner 内复杂度高，留至 Layer 0→1 完成后 release notes）
- ❌ Markdown 报告内再加 banner 文案（B024 已有双语 disclaimer，不重复）
- ❌ 多语种扩展（仅 zh-CN + en，与 B024 i18n 全集对齐）
- ❌ Banner A/B test（单用户产品无 AB）
- ❌ banner 出现频率 telemetry（success-metrics §1 不自动采集）
- ❌ 永久 footer 显示（顶部 banner 已足；不重叠）
- ❌ 修改 backend（本批次纯前端 + i18n messages）

## 7. 验收门槛汇总

| 门槛 | F# 责任 |
|---|---|
| SyntheticDataBanner 组件可渲染 + dismiss + env flag 控制 | F001 |
| messages key parity zh-CN/en bit-identical | F001 |
| Layout 集成（仅 protected pages，不入 login）| F001 |
| .env.example 含 NEXT_PUBLIC_SYNTHETIC_DATA_BANNER | F001 |
| vitest ≥162 通过 | F001 |
| Playwright ≥33 双 locale banner 测试通过 | F001 |
| safety regression 中文禁词 0 命中 | F001 |
| lint / typecheck / build / npm audit 全绿 | F001 |
| build artifact 无 127.0.0.1 / :872x | F001 |
| Backend 既有 pytest ≥320 / ruff / mypy 不破 | F001 + F002 |
| L2 真 VM 双 locale banner 显示 + dismiss + reload 重现 | F002 |
| L2 5 protected 路由抽样 ≥3 banner 可见 | F002 |
| L2 /api/debug/recent-errors=0 | F002 |
| Production HEAD ≡ main HEAD | F002 |
| Signoff 报告 framework/templates/signoff-report.md 全段（含 v0.9.27 §Post-signoff Deploy）| F002 |
| docs/screenshots/B026-banner/{zh-CN,en}/ ≥4 PNG | F002 |

## 8. 参考文档

- `docs/product/implementation-path-2026-05.md` §4 Phase 0 / §7 永久边界 / §8 Planner 接续 checklist / §9 spec 撰写要点
- `docs/product/positioning-2026-05.md` §1.1 AI 角色与边界 + §6.1 永久边界 5 子条
- `docs/product/user-personas-and-journeys-2026-05.md` §7 UI 优先级（banner 在所有路由）+ §8 边界与安全信号
- `docs/specs/B024-i18n-zh-cn-spec.md` §4 i18n 技术架构（参考 namespace 与 messages 模式）
- `framework/STRUCTURE.md` framework/ 目录语义
- `framework/harness/planner.md` §"AI 边界精细化（v0.9.28）"
- `framework/harness/generator.md` §15 i18n middleware chain（next-intl 模式）
- `framework/templates/signoff-report.md`（含 §Production/HEAD 等价性 + §Post-signoff Deploy）
- `framework/CHANGELOG.md` v0.9.28

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Banner 占顶部一行可能挤压 TopBar / 既有 layout 高度 | CSS 高度 36-48px 软约束；layout 测试 + Playwright viewport 截图确认无重叠 |
| messages key parity 漂移（zh-CN 改字漏改 en）| 既有 vitest `messages-key-parity.spec.ts` 守门 + F001 acceptance 明示 |
| Layer 1 完成后 banner 仍显示（env var 忘改）| Phase 1 Real Data done 阶段 acceptance 列入"修改 .env.production NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false" 强制项 |
| 用户点 × 后 reload 重现 → 觉得"烦人"| 这是 by design（与防误用初衷一致）；signoff 报告记录但不视为缺陷 |
| Markdown 报告显示风险 | 不动报告；B024 双语 disclaimer 已覆盖；banner 仅 UI 层 |
| Build artifact 含 banner 文案（脱敏）| 文案是 UI 文本，非 secret；可入 build；构建产物 grep 中性 |

## 10. 与既有批次的边界

- 不动 B024 既有 16 namespace（仅新增 1 namespace `syntheticBanner`）
- 不动 B024 中文按钮禁词集（banner 文案不含禁词）
- 不动 B023 manual execution flow
- 不动 B022 workbench 6 表 schema / 12 页表
- 不动 B021 cloud deploy + OAuth + nginx
- 不动 B025 Master Portfolio 4 sleeve + us_quality_momentum
- 不动 backend pytest / ruff / mypy（本批次纯前端）
- 不动 `.auto-memory/role-context/` 或 `framework/harness/`（无 framework 候选）

## 11. 后续批次（不在 B026 范围）

按 implementation-path §4 顺序：

- **B027 = Phase 1 / Stream 1.A** Real data 选型 + B009 snapshot 路径增强（Polygon Starter 接入）
- **B028 = Phase 1 / Stream 1.B** 历史价格 backfill
- **B029 = Phase 1 / Stream 1.C** 财务 snapshot（SEC EDGAR PIT）
- **B030 = Phase 1 / Stream 1.D** 全 sleeve 切真数据 + 回测重跑 → 里程碑 A

**Phase 1 完成时（B030 done），由 Planner 在 done 阶段同步修改 `.env.production` `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false`，让 banner 自然下线。**

---

> 本 spec 完成后，progress.json status=building，current_sprint=F001，Generator 接 SyntheticDataBanner 组件实现。
