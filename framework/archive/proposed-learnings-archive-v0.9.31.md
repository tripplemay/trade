# proposed-learnings v0.9.31 归档（2026-05-27）

## 背景

B030 done 阶段，Codex F004 signoff §Framework Learnings **first-class 主动列入 3 条候选**（与 B027/B028/B029 Codex 标"无 learnings"模式不同 — 本次确实是 first-class framework discovery，不需要 Planner 重新评估反转）：

1. **新规律**：Decommission 类批次原有 E2E 断言必须同步翻转（presence → absence），否则"产品正确、测试过期"假红
2. **新坑**：仅靠 build-time env 关闭 UI surface 不够；上层 layout 仍 import/render + messages keys 仍 ship → production HTML grep 仍命中旧 surface
3. **模板修订**：decommission / layer-upgrade 批次 signoff 模板补 "legacy E2E presence → absence 翻转检查"段

Planner done 阶段评估：3 条同源（围绕 feature decommission），合并沉淀为 v0.9.31。

## 反 anti-pattern 严格描述

B030 F003 Generator 实施时按 v0.9.30 §12.9 「production secret 三处接线」模式做：
- `.env.example` 保留 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=true`（本机 dev default enable）
- `.env.production` 加 `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false`
- `.github/workflows/bootstrap-env.yml` 加 inject `NEXT_PUBLIC_SYNTHETIC_DATA_BANNER=false`

Generator 推论：env flag = false → React 组件 `enabled` check 返回 null → banner 不渲染 → done。

**Codex F004 verify L1 grep 命中：**
- production HTML 拉 `https://trade.guangai.ai/strategies` (authenticated)
- grep `研究原型 · 仅含合成数据` → 1+ hit
- grep `SyntheticDataBanner` → 1+ hit

**根因（fix-round 1 调查）：**
- React build 正确 dead-code-eliminate `<SyntheticDataBanner>` 内部到 `return null`
- **但** `(protected)/layout.tsx` 仍含 `import { SyntheticDataBanner } from ...` + `<SyntheticDataBanner />` JSX → component 名字仍在 layout chunk
- **且** `messages/{zh-CN,en}.json` 仍含 `syntheticBanner.headline = "研究原型 · 仅含合成数据 · 不构成投资决策依据"` → i18n keys ship 在 RSC payload

Codex grep 命中 **i18n bundle 字面值 + chunk component 名**，不是渲染 DOM。本批次 spec 当初按"env flag 关 = 完全 disable"的假设过于乐观。

## 四处清理铁律（fix-round 1 真正解决路径）

| 处 | 操作 | 影响 |
|---|---|---|
| 1. Layout / Page JSX | 从 `(protected)/layout.tsx` 移除 `<SyntheticDataBanner />` JSX + `import` 行 | component 名字不再在 layout chunk |
| 2. i18n messages JSON | 删 `syntheticBanner.*` keys from `messages/{zh-CN,en}.json` | i18n 字面值不再 ship RSC payload |
| 3. 组件文件保留 + decommission notice | `SyntheticDataBanner.tsx` 保留（永久边界 (k) 可重启路径）；加 `// DECOMMISSIONED 2026-05-27 by B030, see decommission spec` 注释；改 useTranslations → 硬编码双语 + useLocale（重启不需重新加 i18n keys） | 单文件 layout edit 即可重启 |
| 4. 守门测试 | `tests/safety/synthetic-data-banner-decommissioned.spec.ts` 6 个 guard tests + `tests/unit/synthetic-data-banner-component.spec.tsx` 9 个 isolation tests + `tests/e2e/b026-synthetic-banner.spec.ts` presence assertion → absence assertion | 长期守门防止退役状态被回滚 / E2E 假红 |

## 与 v0.9.30 §12.9 secret 三处接线对比（同源 anti-pattern 不同场景）

| 维度 | v0.9.30 §12.9 secret 三处接线 | **v0.9.31 §16 decommission 四处清理** |
|---|---|---|
| 场景 | 新加 production secret | 退役 UI feature |
| Generator 走错路径 | "deploy.sh check 已够" 漏 bootstrap-env.yml | "env flag = false 已够" 漏 layout + i18n + tests |
| Codex 发现机制 | production VM `cat /etc/workbench/workbench.env` grep | production HTML grep 组件名 + i18n 字面值 |
| Manual 清理需要 | 4 处（.env.example / config.py / deploy.sh / bootstrap-env.yml）| 4 处（layout JSX / i18n keys / 组件保留 + notice / 守门测试 + E2E 翻转）|
| 是否真二例 | B027 + B029 真二例 | B030 单一案例（Codex first-class 列入）|
| 是否沉淀 | v0.9.30 ✓ | v0.9.31 ✓ |

**共同模式：** 自动化机制忽略某层 → manual 清理必需 → spec acceptance 必显式列全部处接线 / 清理 → 守门测试 enforce。

## 沉淀位置（已落地）

| 内容 | 落地文件 |
|---|---|
| 四处清理铁律 + ASCII art + 反面案例表 + 与 §12.9 对比 | `framework/harness/generator.md` §16 |
| E2E presence→absence 翻转规约 + 反面案例 | `framework/harness/evaluator.md` §22 |
| Decommission Checklist 7 行检查项表 + Evaluator 强制 | `framework/templates/signoff-report.md` §Decommission Checklist |

## v0.9.X "deploy hygiene + decommission" 系列演进

| 版本 | 教训 | 哪一层 |
|---|---|---|
| v0.9.25 §12.5 | deploy.sh 没 source env file → alembic 跑 scratch DB | deploy script |
| v0.9.25 §12.6 | alembic 跑后 schema 不一致 | deploy script |
| v0.9.27 §12.7 | chore-only commit 不触 CI / deploy → drift | deploy workflow |
| v0.9.27 §12.7.1 | 产品代码 paths-trigger gap → drift | deploy workflow |
| v0.9.27 §20 (evaluator.md) | production VM stale dev process | runtime process |
| v0.9.29 §12.8 | wheel install 缺 dev extras → ImportError | packaging |
| v0.9.30 §12.9 | 新 secret 漏 bootstrap-env.yml → production env 缺 secret | secret 注入 |
| **v0.9.31 §16/§22** | **Feature decommission 仅 env flag off → production HTML 残留组件名 + i18n 字面值** | **UI feature 退役** |

**系列演进趋势：** 每个 v0.9.X 补一层 production-only edge 防御。覆盖面渐趋完整：
- ✅ deploy script (12.5/12.6)
- ✅ deploy workflow (12.7/12.7.1)
- ✅ runtime process (§20)
- ✅ packaging (12.8)
- ✅ secret 注入 (12.9)
- ✅ **UI feature 退役 (16/22)**
- ⏳ frontend bundle 层（已部分覆盖：§13 same-origin + build artifact grep）
- ⏳ nginx / reverse proxy 层（已部分覆盖：§13.5 dev rewrite mirror nginx）
- ⏳ systemd / cron 层

## 预防价值

Phase 3 Home UI 重构（B037+）核心是大量 UI 组件 decommission + 切换：
- 旧 Home dashboard 切到新 dashboard with NAV / Day P&L / market context / AI Advisor
- Reports 页面 Robinhood-style 简化（旧 Sharpe/Sortino 表格 decommission）
- Recommendations 页面简化（旧 target positions table decommission）
- Risk Panel 微调

Phase 4 长尾 batches 同样涉及切 sleeve / 切 vendor / 关 feature 等 decommission 操作。

本节预防的核心问题：**"语义残骸"**（旧 import / 旧 i18n keys / 旧 E2E presence assertion 未同步清理）。Generator 主动按 §16 + Evaluator 主动按 §22 + signoff 走 §Decommission Checklist ≈ 1 个 fix-round 节省/批次。

## 未沉淀（继续 hold）

| 候选 | 决策 | 理由 |
|---|---|---|
| B026 React event edge（vanilla DOM fallback 双路径）| 继续 hold | 仍单一案例。B030 decommission edge 机制不同（UI 退役 vs 事件处理），不与 React event edge 合并。等下一例 React UI 互动 local-pass-prod-fail 出现再合并 |
| B030 S1 `compare_fixture_vs_real.py` 是 data-quality proxy | 不沉淀 | 策略层细节；后续策略级 KPI 升级单独起 batch |
| B030 S2 local harness `codex-setup.sh` / `AGENTS.md` 3099 漂移 | 不沉淀 | 项目 local config 不是 framework 教训；可在 evaluator role-context 加 auth env unset 即可 |

## Planner done 阶段评估说明

**与 v0.9.26 / v0.9.27 / v0.9.28 / v0.9.29 / v0.9.30 沉淀模式不同：**
- 之前批次：Codex 标"本批次无 framework learnings"，Planner 在 done 阶段独立评估 + 与用户确认沉淀
- **本批次（v0.9.31）：Codex first-class 主动列入 3 条 + Planner 评估同源合并沉淀**（不需重新评估反转）

**说明：** Codex 视角在某些"真正的 first-class framework discovery"案例下会主动列入。Planner done 阶段应：
- 评估 Codex 列出的是否同源（本次 3 条都围绕 decommission 即同源）
- 合并相关候选为单一 framework version（v0.9.31 §16/§22/§Decommission Checklist 三处一体）
- 验证 Generator 已有的实现是否能直接作为 framework pattern（本次 6 guard + 9 isolation + presence→absence 翻转已是 ready-to-use pattern）

来源：B030 F004 fix-round 1 commits `abf2ec4` + `095e91d`；signoff `docs/test-reports/B030-real-data-cutover-signoff-2026-05-27.md` §Framework Learnings + §Soft-watch S3；本归档由 Planner 在 done 阶段 2026-05-27 与用户确认后落地。
