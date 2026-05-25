---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B024-i18n-zh-cn：`done`**；F001-F006 全部完成并已签收。Signoff：`docs/test-reports/B024-i18n-signoff-2026-05-22.md`。
- F006 结论：L1 + L2 全 PASS。生产 `trade.guangai.ai` 已实测默认 zh-CN、LocaleSwitcher 英中切换与 cookie 持久、logout 后英文登录页、`cash<0` locale 422、zh/en 两轮 manual execution 闭环、Markdown 双语落盘、`/api/debug/recent-errors`=0、账户恢复为 `cash=0 / positions=[]`。
- Production HEAD = main HEAD = `0176056c68ef6e7f2923b2c15bfadd96f898c519`；systemd `workbench-backend.service` / `workbench-frontend.service` 均 `active (running)`。
- Spec：`docs/specs/B024-i18n-zh-cn-spec.md`
- Spec 内部冲突（line 188 vs 205）已通过「精准 manual check」方案落地并经 L1/L2 双层验证：未引入全局 Pydantic 翻译框架，但 `cash<0` 这一路径按 locale 返回中英 detail。
- 决策矩阵：next-intl@^3 / zh-CN+en 默认中文 / Header 下拉 + NEXT_LOCALE cookie 365d 持久 / 无 URL prefix / 翻范围 = 前端 UI + 后端 HTTPException detail + Markdown disclaimer / 不翻 docs / 专业术语保留英文（Sharpe/drawdown/slippage/bps/kill-switch/rebalance/sleeve/Top N/ETF）/ Disclaimer 双语并存 / Markdown 永不按 locale 切内容。
- 中文按钮禁词扩集（与英文禁词同级 enforced）：`执行 / 下单 / 发送券商 / 立即买入 / 实盘 / 真实交易 / 自动交易 / 一键交易`。

## 已完成签收 + MVP 完工
- B001-B023 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B023 manual execution `docs/test-reports/B023-workbench-phase2-signoff-2026-05-19.md`。

## 生产状态
- `https://trade.guangai.ai` live with双语 workbench（默认 zh-CN，可切 en）+ OAuth + /api/health + /api/debug/recent-errors + daily 03:00 UTC backup。Production HEAD = main HEAD（v0.9.25 §Production/HEAD 等价性 强制）。

## 永久硬边界（B024 起继续）
no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file / 任何按钮 labelled execute/place order/send to broker 禁 + 中文等价禁词同级 / framework v0.9.21-v0.9.26 全约束。

## Framework 状态
- 最新版本 **v0.9.26**（2026-05-25 沉淀完成）：B024 3 候选已写入 planner.md（中文按钮禁词扩集 + bilingual disclaimer 双语永存）+ generator.md §15（next-intl + NextAuth middleware chain 7 子节）+ CHANGELOG bump + `framework/archive/proposed-learnings-archive-v0.9.26.md` 归档。proposed-learnings.md 当前空。

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（US Quality + HK-China satellite；B024 已完成，可进入 B025 候选）
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium` 下载浏览器，否则不会进入页面断言。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
