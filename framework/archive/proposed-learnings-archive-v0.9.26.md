# proposed-learnings v0.9.26 归档（2026-05-25）

## 背景

B024-i18n-zh-cn 在 F006 acceptance 中要求 Codex 把 3 条 framework v0.9.26 候选写入 `framework/proposed-learnings.md`：
- (α) i18n 中文按钮禁词扩集
- (β) next-intl + NextAuth middleware chain pattern
- (γ) bilingual disclaimer 双语永存策略

Codex 在 `docs/test-reports/B024-i18n-signoff-2026-05-22.md` §Framework Learnings 段如实列出了 3 条候选，但**没有把候选追加到 `framework/proposed-learnings.md` 文件实物**。Planner 在 done 收尾阶段察觉差异后，直接按 v0.9.21-v0.9.25 既有模式补写 framework 文件 + CHANGELOG bump + 本归档，不再走"先写 proposed-learnings 再用户确认"的中间步骤——用户已通过 done 阶段 AskUserQuestion 明确确认"3 条全沉淀"。

## 3 条候选原文（摘自 B024 signoff §Framework Learnings）

> - 候选 1：i18n 中文按钮禁词扩集应继续作为 safety regression 长期保留。
> - 候选 2：`next-intl` + NextAuth middleware chain + locale cookie 持久模式已在生产 L2 验证可行。
> - 候选 3：compliance / disclaimer 文案保持双语并存、而不是按 locale 分叉，可避免历史 Markdown diff 漂移。

## 沉淀位置（已落地）

| 候选 | 落地文件 / 章节 |
|---|---|
| α 中文按钮禁词扩集 | `framework/harness/planner.md` §"i18n 加新 locale 时 safety regression 必须扩集等价禁词（v0.9.26）" |
| β next-intl middleware chain | `framework/harness/generator.md` §15 "i18n middleware chain — next-intl + NextAuth + locale cookie 持久（v0.9.26）"（7 子节） |
| γ bilingual disclaimer 双语永存 | `framework/harness/planner.md` §"i18n disclaimer / compliance 文案双语永存（v0.9.26）" |

## 来源 commits（B024 实装链）

- F001 i18n 基建：`fde867d` + `9e398a1`
- F002 UI Pass A：`caa2495` + `d6b90f1`
- F003 UI Pass B（含中文按钮禁词扩集 + safety regression 扩集）：`57e6132`
- F004 backend API error i18n：`125e370` + `67ef393`
- F005 Markdown 双语 disclaimer：`791c43e`
- F006 fix-round 1（cash<0 locale 422）：`0176056`

## Planner done 阶段时序说明

`framework/proposed-learnings.md` 是用户确认前的暂存区，按 v0.9.20 起的惯例由 Generator / Evaluator 在工作中追加。本批次因 Codex signoff 已显式列候选 + 用户在 done 阶段对话直接确认 3 条全沉淀，跳过 proposed-learnings 暂存中间步骤，直接走 framework 实物写入 + CHANGELOG bump + 本归档。后续批次 Evaluator 若有候选仍应优先追加到 proposed-learnings.md，Planner 在 done 阶段再决定沉淀/推迟/不沉淀。
