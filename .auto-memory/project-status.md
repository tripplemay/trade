---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B026-synthetic-data-banner：`reverifying`（fix-round 2）**；F001 fix（commit d02ad79）给 dismiss 加 vanilla DOM fallback；等 Workbench Deploy 自动触发后 Codex 在 production 复测。
- 目标：Layer 0 期间所有 protected 页面顶部加持久 banner，明确但克制标注「研究原型 · 仅含合成数据 · 不构成投资决策依据」+ 英文。防止误用 synthetic 数字做实盘决策。
- Codex reverify 结论：Generator 关于首轮本地红项的判断是对的；`rm -rf .next node_modules && npm ci` 后，frontend `npm run build`、`/login`、full Playwright `38 passed` 全部恢复，证明上一轮 L1 问题是本机环境污染，不是产品实现回归。L2 唯一红项是 production 点击 dismiss 后 banner 不隐藏。
- fix-round 2 修复：SyntheticDataBanner 保留 React onClick → setDismissed 主路径，新增 useEffect 绑 vanilla addEventListener 把 container.style.display 设 'none' 作为冗余路径；任一路径独立满足『hide now』；reload 仍由 SSR 重渲实现『reappear』。本地 vitest 166 / lint / typecheck / build / npm audit / safety / local prod-mode Playwright b026 6/6 全绿。L2 4 张截图一并入 commit `docs/screenshots/B026-banner/`。
- 本批次属 implementation-path-2026-05.md §4 **Phase 0 第一个 batch**（独立无依赖）。预估 1 个轻量批次。
- 后续路径：B027 (Phase 1.A 数据源选型) → B028 (1.B 价格) → B029 (1.C 财务) → B030 (1.D 全 sleeve 切真) → 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B025 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B025 US Quality Momentum Satellite signoff 2026-05-25；B024 i18n zh-CN + en signoff 2026-05-22。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench（默认 zh-CN，可切 en）+ OAuth + /api/health + /api/debug/recent-errors + daily 03:00 UTC backup + 4 sleeve 完整持仓展示（含 satellite_us_quality 5 因子，仍 synthetic data）。
- Production HEAD = main HEAD = `c9274b5`；当前阻塞不是 deploy drift，而是生产上的 banner dismiss 交互未生效。

## 永久硬边界（B026 起继续；v0.9.28）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级（v0.9.26）/ Order ticket Markdown 双语 disclaimer 永存
- 数据 / CI 层：fixture-first 离线 CI / cloud-deploy 批次 workflow_dispatch + Generator chore commit 后 dispatch deploy（v0.9.27）
- **AI 边界（v0.9.28，本批次不引入 AI 但 spec 列）：** (a) no auto-execution / (b) no 收益预测数字 / (c) no 替代 quant / (d) 必须可引用 / (e) 解释/summarize/translate/context aggregation 允许

## Framework 状态
- 最新版本 **v0.9.28**（2026-05-25 沉淀完成）：结构澄清（删项目根 stale .md / harness-rules.md + CLAUDE.md 明确路径 / framework/STRUCTURE.md）+ AI 边界精细化（5 子条取代一刀切）。proposed-learnings.md 空。

## 产品规划状态（B025 done 阶段，approved 2026-05-25）
- 8 份 product docs 全 approved：positioning / user-personas-and-journeys / roadmap / llm-provider-evaluation / data-source-evaluation / ai-safety-evals / success-metrics / **implementation-path**（接续地图）
- 产品定位：AI-augmented personal portfolio decision support tool, built on a quant-strategy chassis（单人 / 永不商业化 / 永不连 broker / AI 是叠加层不是替代层）

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（HK-China satellite；US Quality 已在 B025 落地剥离）→ Phase 4 长尾按需
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium` 下载浏览器。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
