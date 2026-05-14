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

<!-- 2026-05-12: IA refactor redirect scope learning 已按用户确认沉淀到 .auto-memory/role-context/generator.md + .auto-memory/role-context/planner.md。 -->

## [2026-05-15] Claude CLI — 来源：B017 real-data validation cross-batch finding

**类型：** 新坑（backtest evaluation discipline）

**内容：** Synthetic-fixture 信号可能与真实数据信号反向。B016 HRP vs inverse-vol 在 synthetic fixture 上 HRP 略优；B017 真实 yfinance snapshot 上 HRP -$496 + turnover +41%（完全反转）。此类反转风险在任何 fixture-first MVP 框架下都存在 —— fixture 仅证明实现正确性，不能用作策略 conclusion。

**建议写入：**
- `docs/engineering/testing-and-fixture-policy.md` 新增 §"Fixture vs real-data signal reversal" 警示段
- `.auto-memory/role-context/evaluator.md` 加入"fixture-only PASS 不构成策略性能 conclusion"提醒
- 未来策略类批次 spec 起草模板：acceptance gate 涉及性能/收益比较时，应在 real-data 上 reverify，而非依赖 synthetic 结果

**状态：** 待确认

---

## [2026-05-15] Claude CLI — 来源：B017 negative findings × 2

**类型：** 新规律（research debt）

**内容：** B013/B010 vs static 60/40 的 absolute-return gap（B013 calm window 让 60/40 ~25pp / B010 calm window 让 60/40 ~53pp）**经验上证明根源不是 L1 trend gating 也不是 weighting method**：B015 三种 activation policy 都不缩窄（only_non_normal 反而更差），B016 HRP 反而比 inverse-vol 还差。Gap 的真实来源是 open research question，候选包括：vol_target 8% 太保守、defensive sleeve（SGOV/IEF/TLT 等）drag 太重、universe 资产选择不利 calm-period upside、rebalance cadence 不适配。

**建议写入：**
- `framework/research-patterns.md`（如有）或新增策略研究批次 spec 起草模板：当批次结论是"假设的修复方案 X 没有效果"时，明确写下"已排除 X"并把 root cause investigation 作为后续候选
- 可考虑新开 B018 = Gap root-cause attribution batch（vol target sweep / universe ablation / defensive drag 量化）作为最高 ROI 后续

**状态：** 待确认
