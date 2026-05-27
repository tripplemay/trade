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

<!-- 2026-05-15: v0.9.21 沉淀完成（2 条 learnings 来源 B017 cross-batch finding + B018 attribution methodology），写入 docs/engineering/testing-and-fixture-policy.md §Fixture vs Real-Data Signal Reversal + .auto-memory/role-context/evaluator.md §Fixture-only PASS 不构成策略性能 conclusion + 新增 docs/engineering/gap-attribution-methodology.md + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.21.md。 -->

<!-- 2026-05-15: v0.9.22 沉淀完成（1 条 learning 来源 B019 F005 signoff §Framework Learnings + Soft-watch S1），写入 docs/engineering/backtest-report-schema.md §"Snapshot Tail Headroom for T+1 Execution" + Non-Goals 段刷新（删除"No formal frontend dashboard"绝对禁令、改为指向 PRD §7）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.22.md。 -->

<!-- 2026-05-15: v0.9.23 沉淀完成（3 条 learnings 来源 B020-F001/F002/F003），全部写入 framework/harness/generator.md §9-11（Dev environment prerequisites / GitHub Actions Node runtime forward-compat / Python 编码约定 ruff SIM300 trap）+ 立即把 FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true 应用到 .github/workflows/workbench-{backend,frontend}.yml + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.23.md。 -->

<!-- 2026-05-17: v0.9.24 沉淀完成（8 candidates 归并为 3 groups + 1 sub-pattern 来源 B021 F003-F006 fix-round 1-7 + Planner first-time VM bootstrap）：Group A 写入 framework/harness/planner.md §"Cloud-deploy spec checklist"（first-time bootstrap feature 必含 + 8 secrets prep 含 DEPLOY_SSH_KNOWN_HOSTS）；Group B 写入 generator.md §12 四子节（/etc/<app>/ 目录 traversal / systemctl 多 service vs sudoers / PrivateTmp+snap / snap-confine+systemd → 走 apt 装 cloud CLI）；Group C 写入 generator.md §13"Frontend SSR vs Browser context"（NEXT_PUBLIC_* build-time / same-origin / regression test）；Sub-pattern 扩 generator.md §10 加 pre-flight PLACEHOLDER-REPLACE-ME grep scope to deployable source。CHANGELOG v0.9.24。归档：framework/archive/proposed-learnings-archive-v0.9.24.md。 -->

<!-- 2026-05-18: v0.9.25 沉淀完成（9 candidates 归并为 4 groups 来源 B022 F014 fix-round 1-4 + Codex signoff Framework Learnings）：Group 1 (cloud deploy hardening 4 条) 写入 planner.md §Cloud-deploy spec checklist v0.9.25 扩展 + generator.md §12.5/12.6（deploy.sh source env + post-alembic schema-assert）；Group 2 (Next.js dev rewrite parity) 写入 generator.md §13 sub-pattern #5；Group 3 (npm audit + FastAPI SSE/全局异常 logger) 写入 generator.md §10 扩 + 新 §14 FastAPI 运行时观测 ergonomics；Group 4 (signoff 模板 SHA 等价性) 写入 framework/templates/signoff-report.md 新增 §"Production / HEAD 等价性"段。CHANGELOG v0.9.25。归档：framework/archive/proposed-learnings-archive-v0.9.25.md。 -->

<!-- 2026-05-20: B023 done — 零新 framework learnings。Codex signoff §Framework Learnings 明确「本批次无」；3 fix-rounds 命中的两个 blocker（npm audit + canonical boot schema gate）都属 v0.9.25 既有规则的执行细化（generator.md §10 与 §12.6 内已覆盖），未触发新规律。框架版本停留 v0.9.25，不 bump CHANGELOG。-->

<!-- 2026-05-25: v0.9.26 沉淀完成（B024，3 grouped learnings 来源 §Framework Learnings α/β/γ）：写入 planner.md §"i18n 加新 locale safety regression 扩集禁词" + §"i18n disclaimer 双语永存" + generator.md §15 "i18n middleware chain"（7 子节）+ CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.26.md。-->

<!-- 2026-05-25: v0.9.27 沉淀完成（B025，3 grouped learnings 来源 signoff §Framework Learnings 新规律 / 新坑 / 模板修订）：写入 generator.md §12.7 "chore-only main commit 必须可手动 dispatch deploy" + evaluator.md §20 "复验前 lsof 检查 stale dev 进程" + evaluator.md §21 "signoff Production/HEAD + Post-signoff Deploy 双勾选" + planner.md §Cloud-deploy spec checklist v0.9.27 扩展 (e) + templates/signoff-report.md §"Post-signoff Deploy" 段 + CHANGELOG。归档：framework/archive/proposed-learnings-archive-v0.9.27.md。A 组 spec 预想 3 条（多因子 fixture / sleeve stub→implemented / earnings 规避）经用户评估复用价值不足不沉淀。-->

<!-- 2026-05-25: v0.9.28 沉淀完成（B025 done 阶段独立任务：结构澄清 + AI 边界精细化合并 sink）：(1) 删除项目根 3 个 stale 雏形 planner.md/generator.md/evaluator.md（init commit 6fb81a6 后从未更新）；(2) harness-rules.md 第三步章节明确加载 `.auto-memory/role-context/{角色}.md`（active）+ 按需查阅 framework/harness/{角色}.md（规则知识库）；(3) CLAUDE.md 启动流程从 2 步改 4 步明确分层加载；(4) 新建 framework/STRUCTURE.md 澄清目录语义 + agent 启动加载流 6 步明确化；(5) framework/harness/planner.md 新增 §"AI 边界精细化（v0.9.28）"：把 no-AI fit/predict 一刀切替换为 5 子条（no auto-execution / no 收益预测 / no 替代 quant / 必须可引用 / 解释 summarize translate context aggregation 允许）+ spec acceptance 段落模板；(6) .auto-memory/project-status.md §永久硬边界从一行单段改为 4 层结构化；(7) docs/product/positioning-2026-05.md §6.1 状态变 approved。归档：framework/archive/proposed-learnings-archive-v0.9.28.md。-->

<!-- 2026-05-26: B026 done — production-only React event edge 现象观察记账（不沉淀为正式规约，等二例再合并）。本批次 F001 fix-round 2 commit d02ad79 为 banner dismiss 加 vanilla DOM fallback（双路径：React onClick + useEffect 绑 addEventListener + containerRef.style.display='none'）。本地多环境（vitest 165 / next dev / next start / GH Actions CI on c9274b5）全过；production VM 上点 × 视觉不收起。Generator 无法远程调试，根因未明，5+ hypothesis（hydration mismatch / event delegation / nginx buffer / CSP / production React build mode 边角）留待未来调查。若 Phase 3 Home/Reports 改造再撞类似 local-pass-prod-fail UI 互动问题，由当时 Planner 合并 B026 + 新案例沉淀（建议位置：framework/harness/generator.md UI 互动新章节 'production-only React event edge 防御性双路径设计模式'）。参考 v0.9.20 BL-060 模式：单一案例不入沉淀。注：B027 沉淀的 v0.9.29 §12.8 是 deploy-time install layer 教训，机制与本现象不同，不强合并。-->

<!-- 2026-05-26: v0.9.29 沉淀完成（B027 done 阶段：pyproject runtime vs dev dependency hygiene + safety regression test pattern）：(1) framework/harness/generator.md 新增 §12.8 "pyproject runtime vs dev dependency hygiene（v0.9.29 — B027 沉淀）"，含 5 行 dep 类型判断规则 + 3 条规约 + §12.8.1 完整 safety regression test 模板 (tests/safety/test_runtime_dependencies_pinned.py ast walker) + §12.8.2 反面案例表 + 「local vs prod」系列对比 (v0.9.25 §12.5 / v0.9.27 §12.7 / v0.9.27 §20 / v0.9.29 §12.8)。(2) framework/CHANGELOG.md v0.9.29 entry 含变更摘要 + 未沉淀候选记录（B026 React event edge 仍 hold / B027 health_check budget guard wiring 漏 单一案例 / Soft-watch S1 env file 文案漂移 属已有铁律 3）。(3) framework/archive/proposed-learnings-archive-v0.9.29.md 归档含完整候选评估 + 5 行 dep 判断规则 + 「local vs prod」演进趋势 + Planner done 阶段补写时机说明。Codex 标"本批次无 framework learnings"但 Planner 重新评估认为是 framework-grade pattern（高复用窗口：B028 yfinance / B029 SEC EDGAR / B031 LLM gateway / B033 news ingest 每个都会引入新 dep 都可能撞）。-->

<!-- 2026-05-26: v0.9.30 沉淀完成（B027 + B029 二例合并沉淀：production secret 三处接线铁律）：(1) framework/harness/generator.md 新增 §12.9 "production secret 三处接线铁律（v0.9.30 — B027 + B029 二例合并沉淀）"，含 4 处接线 ASCII art (.env.example / config.py / deploy.sh / bootstrap-env.yml) + 4 条规约（spec acceptance / Generator checklist / Planner pre-impl 审计 / Evaluator L2 验证）+ 反面案例对比表（B027 TIINGO_API_KEY commits dcf1463+c46bda3 + B029 SEC_EDGAR_CONTACT_EMAIL commits ef421e9+1e21e9f）+ "deploy hygiene" 系列教训汇总表（§12.5/12.6/12.7/12.7.1/§20/12.8/12.9）。(2) CHANGELOG v0.9.30 entry。(3) 归档 framework/archive/proposed-learnings-archive-v0.9.30.md 含 anti-pattern 严格相同性证明 + 沉淀理由 + v0.9.X "deploy hygiene" 演进趋势 + 未沉淀 hold 候选记录。Generator handoff 主动建议（不只 Codex 视角）；满足"等二例再合并"原则（B026 React event edge 仍单一案例 hold；B029 sector-structural 不沉淀为 framework）。-->

<!-- 2026-05-27: v0.9.31 沉淀完成（B030 沉淀：Feature decommission 四处清理铁律 + E2E presence→absence 翻转）：Codex F004 signoff §Framework Learnings first-class 主动列入 3 同源候选（与 B027/B028/B029 Codex 标"无 learnings"模式不同）。沉淀 3 处一体：(1) framework/harness/generator.md 新增 §16 "Feature decommission ≠ env flag off — 四处清理铁律（v0.9.31 — B030 沉淀）"，含 4 处清理 ASCII art (layout JSX / i18n keys / 组件保留 + notice / 守门测试 + E2E 翻转) + 4 条规约 + 反面案例 (B030 F003→F004 fix-round 1) + 与 §12.9 secret 三处接线 同源 anti-pattern 对比表。(2) framework/harness/evaluator.md 新增 §22 "Decommission 类批次 E2E 断言必须 presence→absence 翻转（v0.9.31）"，含 3 条规约 + 反面案例 (legacy `tests/e2e/b026-synthetic-banner.spec.ts` 跑 fail)。(3) framework/templates/signoff-report.md 新增 §"Decommission Checklist（v0.9.31）" 7 行检查项 + Evaluator 强制。(4) CHANGELOG v0.9.31 entry。(5) 归档 framework/archive/proposed-learnings-archive-v0.9.31.md 含 anti-pattern 严格描述 + 与 §12.9 对比 + Phase 3 UI 重构预防价值 + Codex first-class 列入说明。预防价值：Phase 3 Home UI 重构 + Phase 4 长尾 batches 任何 decommission 操作直接受益。-->
