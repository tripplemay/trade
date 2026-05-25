# proposed-learnings v0.9.27 归档（2026-05-25）

## 背景

B025-us-quality-momentum-satellite 在 F006 acceptance 中要求 Codex 把 3 条 framework v0.9.27 候选写入 `framework/proposed-learnings.md`：
- (α) 多因子策略 fixture 设计模式（point-in-time + multi-factor + 合成数据明示）
- (β) Master Portfolio sleeve stub → implemented 转换流程（精准 1 处改动 + B011 既有测试同步 + 其他 sleeve 不动）
- (γ) Earnings calendar 规避在个股策略中的标准实现（fixture 字段 + construction step 顺序 + 3 场景）

Codex 在 `docs/test-reports/B025-us-quality-signoff-2026-05-25.md` §Framework Learnings 段列出了 3 条**实战踩坑教训**（与 spec 预想的 A 组 3 条不同）：
- 新规律：chore-only main commits 也需要可手动 deploy 的逃生口
- 新坑：复验时复用未知来源本地 `:3000` / `:8723` 进程导致 Playwright stale bundle 红灯
- 模板修订：Signoff 模板应加 post-signoff deploy 策略段

Codex 没有把 spec 预想的 A 组 3 条写入 proposed-learnings.md 实物（与 B024 同样的 Planner done 阶段补写时机问题）。Planner 在 done 阶段做评估，与用户协商后决定：

**A 组（spec 预想）3 条不沉淀，B 组（Codex 实战）3 条沉淀。** 理由：
- A-α 已在 v0.9.21 `docs/engineering/testing-and-fixture-policy.md` §Fixture vs Real-Data Signal Reversal 沉淀过，本批次仅执行规则不构成新规律
- A-β 复用价值有限——HK-China 是仅剩的一次 stub→implemented，之后不再发生
- A-γ 个股策略专属，HK-China ETF 不涉及，复用价值低

B 组 3 条跨批次通用（任何 cloud-deployed 批次都会撞 chore-deploy race；任何 workbench 后续批次的 Playwright 验收都可能踩 stale process；signoff 模板对所有项目都适用）。

## A 组（spec 预想，未沉淀）

| 候选 | spec 出处 | 不沉淀理由 |
|---|---|---|
| α 多因子策略 fixture 设计模式 | `docs/specs/B025-us-quality-momentum-satellite-spec.md` F006 acceptance | 已在 v0.9.21 沉淀（docs/engineering/testing-and-fixture-policy.md） |
| β Master Portfolio sleeve stub → implemented 转换流程 | 同上 | HK-China 是最后一次 stub→implemented，之后不再发生，复用价值低 |
| γ Earnings calendar 规避在个股策略中的标准实现 | 同上 | 个股策略专属，HK-China ETF 不涉及 |

## B 组（Codex 实战，已沉淀）3 条候选原文

摘自 `docs/test-reports/B025-us-quality-signoff-2026-05-25.md` §Framework Learnings：

> **新规律：**
> - chore-only `main` commits 也需要可手动 deploy 的逃生口，否则 cloud batch 的 `Production HEAD ≡ main HEAD` 会被状态机提交反复打破

> **新坑：**
> - 复验时如果直接复用未知来源的本地 `3000/8723` 进程，Playwright 红灯可能只是旧 bundle 污染

> **模板修订：**
> - Signoff 模板可增加一条说明：若签收提交只带元数据而会推进 `main`，Evaluator 应在 close-out 中显式记录 post-signoff deploy 策略

## 沉淀位置（已落地）

| 候选 | 落地文件 / 章节 |
|---|---|
| B-1 chore-only deploy 逃生口 | `framework/harness/generator.md` §12.7 "chore-only main commit 必须可手动 dispatch deploy（v0.9.27）" + `framework/harness/planner.md` §Cloud-deploy spec checklist v0.9.27 扩展 (e) |
| B-2 Playwright stale process 污染 | `framework/harness/evaluator.md` §20 "复验前必须 lsof 检查本地 dev 进程，避免 stale bundle 污染 Playwright（v0.9.27）" |
| B-3 Signoff 模板 Post-signoff Deploy | `framework/templates/signoff-report.md` §"Post-signoff Deploy（v0.9.27 — B025 沉淀）" + `framework/harness/evaluator.md` §21 "写 signoff 时 Production/HEAD 等价性 与 Post-signoff Deploy 必须双勾选（v0.9.27）" |

## 反面案例（B025 F006 4 轮 fix-round 复盘）

| Round | 触发 | 根因 | 本来可以避免的方式 |
|---|---|---|---|
| 1 | L1 缺独立 /risk 路由 + Playwright 双 locale 套件覆盖不足 | Spec F005 acceptance 措辞模糊（"Risk panel 加新 sleeve 一行"未明确独立 route vs 嵌入式 banner） | 这一轮属于正常 spec → implementation 偏差，非 framework 漏洞 |
| 2 | Playwright 红灯 → 误判产品 bug | 本地 `:3000` 有 1.5h 前的 stale Node 进程跑旧 bundle | §20 lsof 前置检查；5 分钟 lsof + kill 可避免整轮 fix-round |
| 3 | Production HEAD `afa154d` ≠ main HEAD `f45ac46` | Generator 推 fixing→reverifying chore commit 不触发 deploy CI | §12.7 chore commit 后 dispatch deploy；spec 应含 `workflow_dispatch` trigger |
| 4 | Production HEAD `afa154d` ≠ main HEAD `abaaf6e` | round-3 修复后又写一个 chore commit，main 再前进一格 | §12.7 同上；Evaluator 自行 dispatch 不必起新 fix-round（§Post-signoff Deploy） |

**净收益：** v0.9.27 沉淀后，B026（HK-China satellite）/ B027 / 后续任何 cloud-deployed 批次的 fix-round 上限应从 B025 的 4 轮压缩到 1-2 轮。

## Planner done 阶段补写时机说明

与 v0.9.26 相同的模式：F006 acceptance 字面要求 Codex 在 verifying 阶段把候选写入 proposed-learnings.md，但实际 Codex 在 signoff §Framework Learnings 段列出后跳过文件实物，Planner 在 done 收尾时 (1) 评估 A 组 vs B 组 真实复用价值 (2) 与用户确认沉淀范围 (3) 直接补做 framework 文件 + CHANGELOG + 本归档 + 不动 proposed-learnings.md（保持空）。

建议后续 spec 在 F00X codex acceptance 里改为：「在 signoff §Framework Learnings 列候选 3 条，Planner 在 done 阶段补做沉淀实物 + CHANGELOG bump + 归档」，而不要求 Codex 同步动 proposed-learnings.md——既符合实际工作流，也避免 Codex 重复写一次相同内容。

来源：B025-us-quality-momentum-satellite F006 4-round fix loop + signoff `docs/test-reports/B025-us-quality-signoff-2026-05-25.md`；Planner done 阶段 2026-05-25 与用户确认沉淀 B 组 3 条不沉淀 A 组 3 条。
