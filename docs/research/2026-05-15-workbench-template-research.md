# Workbench UI/UX Template Research Report

## 1. 背景与目标 (Context & Objective)
根据 `docs/adr/2026-05-15-workbench-direction.md` 中制定的 "Workbench-First" 路线 (Path A)，B020 将进入 Workbench Phase 1 的开发。
目标：寻找符合 **Next.js 14+ App Router + shadcn/ui + Tailwind CSS** 技术栈的优质开源 Dashboard 模板，要求达到或接近 **Bloomberg / TradingView / Koyfin** 级别的专业、现代、高颜值体验，避免从零手搓外壳导致的时间浪费。

## 2. 核心调研对象评估 (Evaluated Templates)
在 GitHub 范围内筛选了高 Stars、活跃维护且契合所选技术栈的模板：

| 模板名称 / 仓库 | 核心技术栈 | 亮点与优势 | 劣势与隐患 | 适用度 |
| :--- | :--- | :--- | :--- | :--- |
| **next-shadcn-dashboard-starter**<br>(by Kiranism, 6.4k+ stars) | Next.js 14, React 18, Tailwind v4 | 极度规范的 `features/` 目录组织；拥有极佳的侧边栏、面包屑和搜索命令面板；提供 cleanup 脚本剥离冗余功能。 | 基于 React 18，技术选型处于稳定期但并非最前沿。 | ⭐⭐⭐⭐ |
| **shadcn-admin**<br>(by Satnaing, 2.6k+ stars) | Vite, React, TanStack Router | 侧边栏及响应式体验极佳；黑白模式切换丝滑。 | 非 Next.js App Router，与 ADR 技术选型有偏差。 | ⭐⭐ |
| **horizon-ui/shadcn-nextjs-boilerplate**<br>(AI Native 模板) | Next.js, shadcn/ui | 主打 AI Native（ChatGPT UI）风格；大面积毛玻璃效果及悬浮卡片；适合原生对话流（Copilot）布局。 | 过于“花哨”；信息密度低，不符合彭博等量化终端的极简克制风格。 | ⭐⭐⭐ |
| **shadcn-dashboard-landing-template**<br>(by ShadcnStore) | **Next.js 15, React 19**, Tailwind v4 | **当前全网最新底层引擎**；内置 `tweakcn` 实时主题编辑器；提供多套 Layout 变体；代码极其纯净规范；完全免费的 **MIT 协议**（可商用）。 | 包含较多展示用的 Dummy Apps（Mail, Tasks 等），初期需要进行一定程度的裁剪。 | ⭐⭐⭐⭐⭐ |

## 3. 推荐结论 (Recommendation)
**强烈推荐采用 `shadcn-dashboard-landing-template` (by ShadcnStore) 作为 Workbench Phase 1 的基础外壳底座。**

### 核心推荐理由：
1. **极致前沿，生命周期长**：它是极少数全面拥抱 **React 19 + Next.js 15 + Tailwind CSS v4** 的开源模板。在初期打下这样的基建，能保证 Workbench 在未来 2-3 年内不落伍。
2. **专业且克制的设计基底**：相较于主打 AI 炫酷特效的模板，它提供了纯净、严谨的后台界面风格，非常适合通过简单的微调（Tweaks）转换为高信息密度的量化金融终端。
3. **零版权风险**：完全宽松的 MIT License，授权极其清晰，允许修改、分发及闭源商业使用。
4. **内置利器**：集成了 `tweakcn`，能在开发初期极其方便地预览和敲定符合金融风格的暗黑冷色调主题（Zinc / Slate）。

## 4. UI/UX 落地定制策略 (Financial UI/UX Tweaks)
确定模板后，为了达成 Koyfin / TradingView 级别的高级感，需在开发初期（B020 第一阶段）执行以下全局覆盖：

1. **提升数据密度 (Compactness)**：覆盖全局的 Tailwind padding/margin 设置，将常规 SaaS 的宽间距（如 `p-4`）缩减为高密度间距（如 `p-2`），并缩小 Button 及 Table Row 的默认高度。
2. **强制等宽数字 (Tabular Nums)**：在全局基础 CSS 或组件层面注入 `tabular-nums` 甚至引入 `JetBrains Mono` / `Inter` 字体，确保所有 PnL、夏普比率、回撤及权重等数字在表格中绝对对齐，消除刷新抖动。
3. **严肃的金融暗色系 (Professional Dark Mode)**：依照 ADR，默认开启 Dark Mode。通过 `tweakcn` 摒弃纯黑或偏蓝的底色，改用高阶的 `Zinc` 或 `Slate` 色系。
4. **盈亏高对比色系**：弃用默认的 `destructive` 红色，采用高饱和冷色系替代（盈利/Up：`#00c853`，亏损/Down：`#ff3b30`）。
5. **动态布局支持 (Dockable Panels)**：在核心回测图表页引入 shadcn 的 `<ResizablePanelGroup>`，实现左侧策略目录、右上 Lightweight Charts 图表、右下 AG Grid 报表的专业多窗格拖拽体验。

## 5. Next Steps (To Planner)
1. **确认采用**：确认采纳 `shadcn-dashboard-landing-template` 作为基建模板。
2. **B020 任务规划**：在规划 B020 Phase 1 Scope 时，将“Clone 基底模板并进行金融级 UI 预配置（清理冗余 App、调整间距/配色/字体）”列为第一个脚手架 Task。
3. **代码隔离**：在项目根目录拉取模板并重命名为 `workbench/`，与 `trade/` 并列，保持 Python / Node 依赖圈的完全隔离。