# framework/ 目录结构与语义

> 本文档由 B025 done 阶段 v0.9.28 沉淀建立，澄清 framework/ 各子目录的真实角色。
> 来源：B025 done 阶段用户提问 "framework 目录只是模板，并不是本项目要遵守的规则文件" 引发的结构性调查。

## 一句话总结

**framework/ 目录是双重身份：**

1. **本项目自身的规则知识库 + 历史沉淀目标位置**（active 维护中）
2. **给其他新项目复用的 Triad Workflow 模板源**（通过 `framework/bootstrap.sh` 与 `tripplemay/harness-template` repo 分发）

本项目（trade workbench）既是 Triad Workflow framework 的**开发者**，也是它的**用户**。

## 各子目录语义

| 子目录 / 文件 | 语义 | 加载时机 |
|---|---|---|
| **`framework/harness/{planner,generator,evaluator}.md`** | **规则知识库**：含 v0.9.X 沉淀的深度规则（§8-N）。**不是 always-loaded**；Planner 在写 spec 时查阅 / Evaluator 在 verifying 时参考 / Generator 在遇到 acceptance 模糊时查阅。 | 按需查阅 |
| `framework/harness/harness-rules.md` | **状态机规则模板**（与项目根 `harness-rules.md` 同名；项目根才是 active 加载的版本） | 项目根版本：每次启动必读 |
| `framework/harness/ai-action-contract.md` | AI 行动契约模板（B025 起精细化为 5 子条永久边界） | Planner / Generator 在 AI 类批次起草时查阅 |
| `framework/harness/database-patterns.md` | 数据库模式知识库 | 数据库批次查阅 |
| `framework/harness/deploy-patterns.md` | 部署模式知识库 | cloud-deploy 批次查阅 |
| `framework/harness/i18n-namespace-add-checklist.md` | i18n checklist | 加 namespace 时查阅 |
| `framework/harness/material-symbols-pattern.md` | Material Symbols 模式 | 前端 icon 批次查阅 |
| `framework/harness/pre-impl-adjudication.md` | 实施前裁决 | Planner 起 spec 时查阅 |
| `framework/harness/ui-fidelity-guardrail.md` | UI 还原守门 | 设计稿还原批次查阅 |
| `framework/harness/progress.init.json` | progress.json 初始模板 | 新项目 bootstrap 时复制 |
| **`framework/templates/`** | **新项目模板**（给 `bootstrap.sh` 复制到新项目用）：`CLAUDE.md` / `AGENTS.md` / `signoff-report.md` / `pre-commit-hook.sh` / `features.template.json` / `migration-batch-checklist.md` / `prod-launch-audit-template.md` | 本项目不加载，新项目 bootstrap 时复制 |
| **`framework/proposed-learnings.md`** | 提案暂存区 | Planner / Generator / Evaluator 在工作中发现新规律时追加；done 阶段 Planner 集中沉淀 |
| **`framework/archive/`** | 已闭环提案归档 | 不加载，历史归档 |
| **`framework/CHANGELOG.md`** | 版本历史 | Planner 沉淀新版本时 append |
| **`framework/README.md`** | 给新项目用的 Triad Workflow 介绍 + bootstrap 指南 | 不加载，外部文档 |
| **`framework/bootstrap.sh`** | 新项目 bootstrap 脚本 | 新项目运行；本项目不再运行（init 时已用过） |

## 项目根 vs framework/harness/ 的关系

**bootstrap.sh 设计意图：** 新项目运行 bootstrap.sh 时，把 `framework/harness/{harness-rules,planner,generator,evaluator}.md` **复制**到项目根作为可独立维护的副本。

**本项目实际历史：**
- init commit `6fb81a6` 把 4 个文件写入项目根
- 此后 25 批次（B001-B025）所有 v0.9.X 沉淀都进 `framework/harness/{角色}.md`
- 项目根的 `planner.md / generator.md / evaluator.md` **从未被更新**（stale 雏形）
- **v0.9.28（B025 done）已删除项目根 3 个 stale .md**
- `harness-rules.md` 在项目根保留（active 加载）

## agent 启动加载流（v0.9.28 起明确）

```
1. harness-rules.md (项目根)             — 状态机规则
2. .auto-memory/MEMORY.md (T0)           — 记忆索引
3. .auto-memory/project-status.md (T0)   — 项目状态快照
4. .auto-memory/environment.md (T0)      — 环境信息
5. .auto-memory/role-context/{角色}.md (T1)  — active 行为规范（按当前角色加载）
6. framework/harness/{角色}.md           — 按需查阅（不 always-loaded）
7. framework/harness/{其他}.md           — 按需查阅（database-patterns / deploy-patterns / i18n-checklist 等）
```

## v0.9.X 沉淀的写入位置（Planner done 阶段参考）

| 沉淀类型 | 写入位置 |
|---|---|
| 状态机规则修订 | `framework/harness/harness-rules.md` + 项目根 `harness-rules.md` |
| 角色行为规则（active，每次会话遵守）| `.auto-memory/role-context/{角色}.md` |
| 角色深度规则（按需查阅）| `framework/harness/{角色}.md` |
| 跨项目通用模板 | `framework/templates/{模板}.md` |
| 数据库 / 部署 / i18n 类专题 | `framework/harness/{专题}.md` |
| 产品边界 | `.auto-memory/project-status.md` §永久硬边界 + `docs/product/positioning-*.md` §相关边界段 |
| 版本记录 | `framework/CHANGELOG.md` 顶部 append |
| 归档 | `framework/archive/proposed-learnings-archive-vX.Y.md` |

## 维护原则

1. **`.auto-memory/role-context/{角色}.md` 保持简短（37-50 行）** — 这是 agent 每次启动加载，长则污染 context
2. **`framework/harness/{角色}.md` 可任意长** — 知识库属性，按需查阅
3. **二者内容不重复** — role-context 是 active rules（"该怎么做"），framework/harness/ 是 deep knowledge（"为什么 + 反面案例 + 完整规约"）
4. **新增规则时 Planner 判断写入位置：** 角色每次必遵守 → role-context；按场景查阅 → framework/harness/；产品级 → project-status.md / positioning.md
5. **跨多副本一致性：** `framework/harness/harness-rules.md` 与项目根 `harness-rules.md` 是 framework 维护层 + 本项目 active 层；本项目 active 层为权威，framework/harness/ 版本作为发布给其他项目的快照（沉淀新版本时同步两份）

---

来源：B025 done 阶段 v0.9.28 沉淀（结构澄清 + AI 边界精细化合并 commit）；用户提问 "framework 目录只是模板，并不是本项目要遵守的规则文件" 引发的完整调查。
