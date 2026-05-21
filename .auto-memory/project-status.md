---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B024-i18n-zh-cn：`fixing`**（Codex F006 首轮 L1 验收发现 blocker）；F001-F005 已完成，F006 首轮未过。已验证通过：backend `ruff`/`mypy`/`pytest 236 passed 2 skipped`，frontend `lint`/`typecheck`/`vitest 146 passed`/`build`，`npm audit --audit-level=high` 仅 4 moderate 且 exit 0，`.next/static` 无后端端口，中文按钮禁词 safety 与 key parity 全绿，Playwright 19 项在安装本机浏览器后通过，本地双 locale UI smoke 也通过。
- Spec：`docs/specs/B024-i18n-zh-cn-spec.md`
- 当前 blocker：`PUT /api/execution/account` 的 `cash<0` 负向校验仍返回 Pydantic 默认英文 422；`Accept-Language=zh-CN` 与 `?locale=en` 都不生效，不满足 F006 明确验收项。另有 spec 内部冲突：`docs/specs/B024-i18n-zh-cn-spec.md` 第 188 行要求翻译该 422，第 205 行又写“不翻译 Pydantic validation error”。
- 决策矩阵：next-intl@^3 / zh-CN+en 默认中文 / Header 下拉 + NEXT_LOCALE cookie 365d 持久 / 无 URL prefix / 翻范围 = 前端 UI + 后端 HTTPException detail + Markdown disclaimer / 不翻 docs / 专业术语保留英文（Sharpe/drawdown/slippage/bps/kill-switch/rebalance/sleeve/Top N/ETF）/ Disclaimer 双语并存 / Markdown 永不按 locale 切内容。
- 中文按钮禁词扩集（与英文禁词同级 enforced）：`执行 / 下单 / 发送券商 / 立即买入 / 实盘 / 真实交易 / 自动交易 / 一键交易`。

## 已完成签收 + MVP 完工
- B001-B023 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B023 manual execution `docs/test-reports/B023-workbench-phase2-signoff-2026-05-19.md`。

## 生产状态
- `https://trade.guangai.ai` live with full 12 页 + 6 表 + OAuth + /api/health + /api/debug/recent-errors + daily 03:00 UTC backup。Production HEAD = main HEAD（v0.9.25 §Production/HEAD 等价性 强制）。B024 完工后 = 中文 UI live。

## 永久硬边界（B024 起继续）
no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file / 任何按钮 labelled execute/place order/send to broker 禁 + 中文等价禁词同级 / framework v0.9.21-v0.9.25 全约束。

## post-MVP backlog（按优先级）
- **BL-B011-S2 high**（US Quality + HK-China satellite，B024 完工后接 B025 候选）
- BL-B010-S1 low / BL-B013-D1 low / BL-B013-D2 low / BL-B023-S1 low / BL-B023-S2 low

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- 本机首次跑 Playwright 需先 `npx playwright install chromium` 下载浏览器，否则不会进入页面断言。
- framework/proposed-learnings.md 当前空；B024 F006 完工后预留 3 条 v0.9.26 候选。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
