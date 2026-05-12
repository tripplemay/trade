# Framework 提案暂存区

> Generator 和 Evaluator 在工作中发现值得沉淀的经验时，追加到本文件。
> Planner 在 done 阶段读取本文件，逐条提交给用户确认。
> 确认后由 Planner 正式写入 `framework/` 对应文件，并在 `CHANGELOG.md` 追加记录，最后从本文件移除已确认条目。
> 已闭环条目归档到 `framework/archive/proposed-learnings-archive-vX.Y.md`。

---

<!-- 2026-05-04: v0.9.9 沉淀完成（8 条 learnings 来源 BL-030/BL-031/BL-032），全部已写入 framework/ 对应文件 + CHANGELOG。 -->

<!-- 2026-05-04: v0.9.10 沉淀完成（3 条 learnings 来源 BL-033 + prod-mvp-readiness-audit），全部已写入 framework/ 对应文件 + CHANGELOG。 -->

<!-- 2026-05-05: v0.9.11 沉淀完成（5 条 learnings 来源 BL-020 + backend-full-scan-2026-05-04 audit），全部已写入 framework/ 对应文件 + 项目根 .nvmrc + .auto-memory/environment.md + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.11.md。 -->

<!-- 2026-05-05: v0.9.12 沉淀完成（3 条 learnings 来源 BL-034），全部已写入 pre-impl-adjudication.md §11 + database-patterns.md §8.1 + deploy-patterns.md §5 + evaluator.md §17 + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.12.md。 -->

<!-- 2026-05-06: v0.9.13 沉淀完成（2 条 learnings 来源 BL-024），全部已写入 deploy-patterns.md §5.1 + ai-action-contract.md §4.7 + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.13.md。 -->

<!-- 2026-05-06: v0.9.14 沉淀完成（2 条 learnings 来源 BL-040 + BL-041 audit 过期 + BL-043 staging fix），全部已写入 planner.md 铁律 1 矩阵 +2 行延伸 + deploy-patterns.md §1.7（v0.9.7 §1.6 范围扩展）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.14.md。 -->

<!-- 2026-05-07: v0.9.15 沉淀完成（2 条 learnings 来源 BL-021 F002 撤再翻盘 + BL-049 测试基建 audit），全部已写入 planner.md 铁律 1 矩阵 +2 行（v0.9.15 #1 跨 pool 复现 + #2 stub environment-agnostic）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.15.md。 -->

<!-- 2026-05-08: v0.9.16 沉淀完成（1 条 learning 来源 BL-052 verifying P5 裁决），全部已写入 planner.md §"Planner 裁决职责" §P5.2 段 + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.16.md。 -->

<!-- 2026-05-08: v0.9.17 沉淀完成（1 条 learning 来源 BL-012 apify-kol fork audit），全部已写入 planner.md 铁律 1 矩阵 +1 行（v0.9.17 记忆条目陈旧风险）+ 反面案例段（BL-012 5/7→5/8 实战）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.17.md。 -->

<!-- 2026-05-08: v0.9.18 沉淀完成（1 条 learning 来源 BL-012 F001 fix-round 1 admin role enum mismatch），全部已写入 planner.md 铁律 1 矩阵 +1 行（v0.9.18 auth role enum 实物核查）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.18.md。 -->

<!-- 2026-05-08: v0.9.19 沉淀完成（1 条 learning 来源 BL-012 F002 fix-round 2 prod zod schema mismatch），全部已写入 planner.md 铁律 1 矩阵 +1 行（v0.9.19 external API response zod schema 实物 sample 验证）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.19.md。 -->

<!-- 2026-05-10: v0.9.20 沉淀完成（1 条 learning 来源 BL-060 fix-round 1→2 e2e suite-level isolation vs 单 case 信号区分），写入 .auto-memory/role-context/evaluator.md §"E2E suite 稳定性诊断" + .auto-memory/role-context/generator.md §"扩范围 vs 单点修的判断"。后续 batch 候选（抽 tests/e2e/helpers/auth.ts + global-setup.ts + storageState 复用）入 backlog 跟踪。归档暂未写 framework/archive/proposed-learnings-archive-v0.9.20.md（git history 已有 commits cae1f8f / 821c094 完整记录）。-->

---

## [2026-05-11] Claude CLI — 来源：BL-064 fix-round 3 实战（顶层 IA refactor 7→4 路由）

**类型：** 新规律 / 模板修订（适用未来所有 IA refactor / page consolidation 批次）

**事实链：**

1. BL-064 spec §4 原预期 redirect ~12 条（7 老路由 + 子路径继承 + parametric）
2. fix-round 1-3 实战发现：embed-old-components 策略下，redirect 到 destination route **未 wire ready** 时（如 /campaigns/new → /brief?action=new 但 /brief 本批次只 embed /knowledge-base，没 wire form action），用户体验比 kept 旧路由 **差** — 跳转后看到的是 placeholder URL 但内容仍是旧的，反而 confusing
3. 最终缩减到 6 条 redirect = 5 content-equivalent prefix（/dashboard→insight / /discovery→match / /database→match / /knowledge-base→brief / /outreach→reach）+ 1 parametric（/campaigns/[id]→/match?campaignId=:id）
4. 4 条原预期 redirect 改 kept deep-link，推迟到后续 Phase 批次 wire destination 后再启：
   - /campaigns 列表 → kept；BL-066 wire /match view=campaigns 后启
   - /campaigns/new → kept；BL-069 wire /brief form 后启
   - /roi / /weekly-report / /analytics → kept；BL-070 unify /insight 后启
   - /outreach/templates 等 sub-path → kept；BL-070 wire /reach 子路由后启

**升级后的教训（适用未来批次）：**

A. **IA refactor batch 的 redirect scope 应根据 destination route wire-readiness 评估** — 不是所有老路由都立即 redirect，destination route 必须含等效或更优的功能才启 redirect；否则 kept deep-link 让 UX 不退化

B. **embed-old-components 占位策略下的 redirect 评估清单**（spec 起草时套用）：
   - destination route 是否已 wire 该 content？（如有则 redirect OK）
   - destination route 仅 embed-old 占位时，redirect 到那里只是 URL 换名 → UX 不变但用户认知混乱，**kept 更优**
   - 决策点放 spec §4 关键决策点，让 Planner 起草时 explicit 标记每条 redirect 的 wire-readiness 状态

C. **redirect scope 缩减是良性 fix-round** — fix-round 数不计入"质量问题"，反映 IA refactor 需要 building 中段实战验证才能确定最优 scope

**建议写入：**
- 主位置：`.auto-memory/role-context/generator.md` 新增 §"IA refactor redirect scope 评估"（~8 行）
- 次位置：`.auto-memory/role-context/planner.md`（spec 起草时 §"IA refactor 类批次 redirect 清单"评估流程，~5 行）
- （可选）`framework/templates/ia-refactor-spec-template.md` 新模板含 wire-readiness checklist（如未来 IA refactor 高频可加）

**状态：** 待用户确认沉淀位置
