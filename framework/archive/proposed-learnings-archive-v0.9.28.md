# proposed-learnings v0.9.28 归档（2026-05-25）

## 背景

B025 done 阶段在 framework v0.9.27 沉淀完成、产品规划 docs（positioning-2026-05.md + user-personas-and-journeys-2026-05.md）approved 之后，用户提出关键质疑：

> "framework 目录只是模板，并不是本项目要遵守的规则文件"

这一直觉性质疑揭示了 framework/ 目录的**双重身份混乱**：(a) 项目自身规则知识库 (b) 给其他新项目复用的 Triad Workflow 模板。Planner 在 done 阶段做了完整结构性调查，并把调查结论与同期的"AI 边界精细化"打包成 v0.9.28 沉淀。

## 结构性调查 5 个关键证据

| # | 证据 | 含义 |
|---|---|---|
| 1 | 项目根 `planner.md / generator.md / evaluator.md` git history 全部仅 1 commit：`6fb81a6 Initialize harness-based AI quant trading repository` | 三个文件自项目初始化后从未被更新过，是 stale 雏形 |
| 2 | `framework/harness/{planner,generator,evaluator}.md` git history 含 v0.9.7-v0.9.27 全部沉淀（最近 `4412471` v0.9.27 / `43c07f1` v0.9.26 / `b3488fc` v0.9.25 / `8c7e6ae` v0.9.24 / `9836766` v0.9.23）| 这是真正在被维护的规则知识库 |
| 3 | `harness-rules.md` 第 156 行原文 "根据第二步的判断结果加载 planner.md / generator.md / evaluator.md 并严格执行"（路径模糊）| 设计意图与实际机制不对齐的根因 |
| 4 | `harness-rules.md` 第 348 行 "建议写入：`framework/harness/xxx.md` / 其他"；25 批次所有 v0.9.X 沉淀均进 framework/harness/ | 沉淀写入位置实际是 framework/harness/ |
| 5 | `framework/README.md` §134-161 + `framework/bootstrap.sh` 第 123 行揭示设计意图：bootstrap.sh 把 framework/harness/ 文件**复制**到项目根作为 active 副本。但本项目 init 时复制后从未 re-sync | bootstrap.sh 设计与本项目实际历史不一致 |

## 真实加载机制（v0.9.28 明确化前的实际状态）

按 framework v0.5.0+ 分层加载演进，agent 启动加载流实际为：

```
1. harness-rules.md (项目根)             ← T0 必读
2. .auto-memory/MEMORY.md (T0)           ← 记忆索引
3. .auto-memory/project-status.md (T0)
4. .auto-memory/environment.md (T0)
5. .auto-memory/role-context/{角色}.md (T1)  ← 真实加载的 active 行为规范（37-50 行简短版）
6. framework/harness/{角色}.md           ← 按需查阅（不 always-loaded；Planner 写 spec 时 / Evaluator 验收时 / Generator 遇模糊时）
7. framework/harness/{其他}.md           ← 按需查阅（database-patterns / deploy-patterns / i18n-checklist 等）
```

**项目根 `planner.md / generator.md / evaluator.md` 从未被加载。** 25 批次实际运行证明：B021/B022 fix-round 触发的 §12.5 deploy.sh source env / §12.6 schema-assert 等规则只在 framework/harness/generator.md 存在；项目根 generator.md 239 行 stale 版本不含这些规则。

## 沉淀范围（5 件 + AI 边界）

| # | 改动 | 文件 |
|---|---|---|
| 1 | 删除 3 个 stale 雏形 | 项目根 `planner.md` / `generator.md` / `evaluator.md` |
| 2 | 明确加载路径 + 改默认映射表 | `harness-rules.md` 第三步章节 |
| 3 | 启动流程从 2 步改 4 步 | `CLAUDE.md` 第 8-10 行 |
| 4 | 新建目录结构澄清文档 | `framework/STRUCTURE.md`（新文件，139 行）|
| 5 | AI 边界一刀切 → 5 子条 | `framework/harness/planner.md` 新增 §"AI 边界精细化（v0.9.28）"段 + `.auto-memory/project-status.md` §永久硬边界 4 层结构化 + `docs/product/positioning-2026-05.md` §6.1 状态变 approved |
| 6 | CHANGELOG bump | `framework/CHANGELOG.md` 顶部 v0.9.28 entry |
| 7 | 归档（本文件）| `framework/archive/proposed-learnings-archive-v0.9.28.md` |

## AI 边界 5 子条（从 v0.9.21-v0.9.27 一刀切迁移）

| 子条 | 内容 | 类型 |
|---|---|---|
| (a) | `no-AI auto-execution` — AI 不可触发任何自动下单 / 交易 / 调仓 | 永久禁止 |
| (b) | `no-AI 收益预测数字输出` — AI 不输出"预期年化 X%" / 任何收益预测数字 | 永久禁止 |
| (c) | `no-AI 替代 quant 评分作为唯一决策依据` — AI 是 quant signal 的叠加层 | 永久禁止 |
| (d) | `AI 输出必须基于 quant signal + real data + 可引用 news` — 无引用建议禁止 | 强制要求 |
| (e) | AI 做以下事项允许：解释 / summarize / translate / context aggregation / Robinhood-style 简化文案 | 允许 |

## 用户 Q&A 时序（B025 done 阶段，2026-05-25）

| 轮 | 用户答 | 关键决策 |
|---|---|---|
| 1 | "目前我们项目的功能完成到什么阶段了" | Planner 给出完工度全景 + synthetic vs real 区分 |
| 2 | "调低技术优先级，先做产品规划" | 切独立任务模式，不走 spec-driven |
| 3 (产品定位 + research 层 + 核心问题) | 单人 / Layer 0→1 下个里程碑 / 财产管理决策辅助工具 | 产品定位浮现 |
| 4 (使用频率 + 现有工具 + 量化背景) | 每天看 / 首个系统化工具 / 不懂量化术语 / 需 Robinhood 简化 | 揭示 quant researcher tool → portfolio dashboard 转向 |
| 5 (资产范围 + Home 看什么) | 全部投资资产 / 市场新闻聚合 | 揭示 Home 重构方向 |
| 6 (3 关键 draft 判断) | 同等重要并行 / 接受 Master Portfolio / **希望 AI 给具体投资建议** | 揭示与永久边界 `no-AI fit/predict` 的根本冲突 |
| 7 (AI 路径选择) | "AI 基于成熟量化策略 + 新闻分析 → 投资建议" = 路径 B 精细版 | 锁定 AI 角色 |
| 8 (3 doc 校正 / 批准 / 继续规划) | 同意 / 批准 / 继续 | doc approved + 续做产品规划 |
| 9 (下一份规划是？) | **"framework 目录只是模板，并不是本项目要遵守的规则文件"** | **触发结构性调查 + v0.9.28 沉淀** |
| 10 (3 选 1 方案 A/B/C) | "先调查明白、别急重组" | Planner 深查 |
| 11 (调查结论后 A) | "继续调查 / 有其他发现" | Planner 续查 |
| 12 (精细修正方案 7 步) | "推进 7 步 全部" | v0.9.28 sink 落地 |

## 后续注意事项

1. `framework/harness/harness-rules.md`（templates 副本）与项目根 `harness-rules.md`（active）在 v0.9.28 起明确分工：项目根 active，framework 副本仅作快照（同步两份在下次沉淀时）
2. `framework/STRUCTURE.md` 为未来 framework 维护者提供 single source of truth；任何新增 framework 子目录必须更新本 doc
3. AI 边界 5 子条配套需要在后续 AI advisory engine 类批次 spec acceptance 显式引用全集（见 framework/harness/planner.md §"AI 边界精细化" §spec acceptance 段落模板）
4. 用户最终选择路径 B 精细版（quant + real data + news → AI 综合建议），而非路径 C（全 AI 决策），这个选择固化在 v0.9.28 边界中。后续若用户想软化到路径 C，需要新一轮产品规划批次 + framework v0.9.29 沉淀

来源：B025 done 阶段独立任务模式 12 轮 Q&A；commits `12de7fe`（docs(product) 路径 B 整合）+ `5d3a425`（doc approved）+ 本次 v0.9.28 sink commit。
