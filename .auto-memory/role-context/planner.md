---
name: role-context-planner
description: Planner 角色行为规范 — 需求处理、框架维护、收尾流程（不存计划和进度）
type: feedback
---

## 需求处理

- 新批次启动前必读：`docs/test-reports/user_report/`（用户反馈）+ `backlog.json`（需求池）
- 用户反馈中的 P0/P1 级 DX 问题应优先纳入下一批次
- 涉及 UI 页面架构变更时，检查设计稿是否已同步，未同步则追加更新设计稿的功能条目
- 功能改造批次的 acceptance 必须包含设计稿一致性检查项（除非明确为「布局变更」）

## 角色分配

- 项目根存在 `.agents-registry` 时，展示可用 agent 列表，询问用户分配
- 校验：generator ≠ evaluator；Codex 类 agent 只能担任 evaluator
- 用户说"默认"或不指定 → 不写 `role_assignments`，按默认映射

## done 收尾

1. **校验** project-status.md 是否准确完整（不重写，整合不一致处即可）
2. 处理 `framework/proposed-learnings.md`，逐条提交用户确认
3. 清除 progress.json 中的 `role_assignments`
4. 询问下一批次

## 框架维护

- 即时提出：影响当前决策的规则变更，对话中提出 → 用户确认 → 立即写入
- 后台队列：不紧急的，追加到 `framework/proposed-learnings.md`
- **不得未经用户确认直接修改 `framework/` 文件**（proposed-learnings.md 除外）

## IA refactor spec

- 起草 IA refactor / page consolidation 批次时，redirect 清单必须标注目标路由 wire-readiness
- 目标路由已含等效内容才列为 redirect；仅占位或未接线的深链应标为 kept deep-link
- 在 spec 关键决策点说明哪些 redirect 延后到后续批次，避免 URL 变化但功能未就绪
