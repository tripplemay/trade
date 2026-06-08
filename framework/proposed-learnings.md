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

<!-- 2026-05-27: B031 done — 第三方 API spec invented endpoint 现象观察记账（不沉淀为正式 v0.9.32 规约，等二例再合并）。本批次 F003 fix-round 1 commit f31c302 修真实 aigc-gateway OpenAI-compatible API: spec §4 invented JSON envelope (/chat + /embed + /balance + top-level content/cost_usd_est/log_id) 不匹配真 API；真 API 是 OpenAI-compatible /v1/chat/completions + /v1/embeddings + /v1/models with choices[0].message.content envelope；placeholder host aigc-gateway.example.com DNS fail。Generator 修复后 BASE_URL = https://aigc.guangai.ai + OpenAI envelope 解析 + dotted model IDs (claude-haiku-4.5 等验证自 /v1/models) + prod URL guard + endpoint path 守门测试。Codex signoff §Framework Learnings first-class 列入 1 候选 (建议位置 generator.md)。用户暂不沉淀决议：参考 v0.9.20 BL-060 / B026 React event edge 单一案例不入沉淀原则。复用窗口（B033 News API / B034 Cohere embedding / B035 FRED+Alpha Vantage / Phase 3+）—— 后续若再撞同样"spec invented 第三方 API endpoint"问题，由当时 Planner 合并 B031 + 新案例沉淀为 v0.9.32（建议位置：framework/harness/planner.md 铁律 1 扩展 "第三方 API 接入 spec 必须 live-validate" + framework/harness/generator.md §17 "F001 实施时必须 live hit 真 API 验证"）。-->

<!-- 2026-06-04: v0.9.32 沉淀完成（B034 二例合并：请求路径 deploy-artifact 自包含铁律）：两条候选（2026-06-01 B034 F003 import scripts/pandas → frontend-CI 500 + 2026-06-04 B034 F004 L2 open repo-root data/fixtures → production VM 500）同根合并沉淀。(1) framework/harness/generator.md 新增 §12.10 "请求路径 deploy-artifact 自包含铁律"（二例 + deploy artifact 边界 ASCII art + 4 条规约 + 与 §12.8/§12.9 关系 + local vs prod 系列补一行）。(2) framework/harness/evaluator.md 新增 §23 "新增 user-facing 路由 L2 必测真 VM authenticated 200"。(3) framework/templates/signoff-report.md §L2 实测记录 加勾选行。(4) CHANGELOG v0.9.32。(5) 归档 framework/archive/proposed-learnings-archive-v0.9.32.md（含两条原候选全文 + 二例合并评估 + 仍 hold 候选记录）。仍 hold：B031 第三方 API live-validate（不同模式，单例，等二例）+ B026 React event edge（单例）。-->

<!-- 2026-06-06: v0.9.33 沉淀完成（B035/B036/B037 三例合并：read-only timer L2 接线检查）：B037 signoff §Framework Learnings 新坑「新 timer endpoint/DB 绿 ≠ 运维接线完成」+ §Soft-watch S1（同根三批重复手装 timer），过「等二例再合并」门槛。写入 framework/harness/evaluator.md §24（4 条规约 + 反面案例 B037 F004 首轮 L2 + 与 generator.md §12/§12.9 ops-wiring 同族）+ CHANGELOG v0.9.33。Soft-watch S1 的 durable fix（扩 deploy sudoers + deploy.sh 自动 install/enable timer）未沉淀进文档而是转为下一批次立项跟踪。 -->

## [2026-06-06] Claude CLI — 来源：B037-OPS1 F001 security-reviewer 裁决

**类型：** 新规律（ops-security 设计模式）

**内容：** sudoers 通配符授权 `install` / 文件落盘类命令时，`fnmatch(3)` 不带 `FNM_PATHNAME`，`*` 匹配 `/` → 目标参数 `.../prefix-x/../escape.suffix` 能字面匹配 `.../prefix-*.suffix` pattern 却经内核 `..` 解析逃逸目标目录（root 写任意文件）。**通用缓解：把受限文件落盘交给一个根属、调用方不可写的 wrapper 脚本**（接受裸名 / 拒绝 `/` / 正则锁前缀+后缀 / 固定目标目录与模式），sudoers 只授权该 wrapper —— 既保留通配符的零手工耐久性，又把路径穿越类彻底关在 shell 层。B037-OPS1 落地 `workbench/deploy/sudoers/workbench-install-unit`。

**建议写入：** `framework/harness/generator.md` §12.x（与 §12.9 production secret 三处接线 / §12.10 deploy-artifact 自包含 同属 "deploy/ops hardening" 系列）；或 security 专章。复用窗口：未来任何 deploy 用户 narrow-sudoers 扩权（新增需 root 落盘的运维动作）。

**状态：** 待确认（单例；可与未来同类 sudoers/ops-privilege 案例二例合并，遵循"等二例再沉淀"原则）

<!-- 2026-06-06: v0.9.34 沉淀完成（B038：§12.10 自包含审计扩到所有生产执行路径）：B038 F003 L2 blocker — news/cli.py 接入 workbench-news.timer 后首次 prod 执行触发 import scripts.* ModuleNotFoundError（B033 起隐患，manual-only 期全程掩盖）。signoff §Framework Learnings 由 Planner done 阶段裁定沉淀。写入 generator.md §12.10.1（manual-only CLI 接入自动执行路径时按 §12.10 重审 + 规约 5 + L2 手动 trigger service 验真 + 对比表 v0.9.34 行）+ CHANGELOG v0.9.34。边界 (q)→(r) 收编属产品边界（已落 project-status §永久硬边界），非 framework；B037-OPS1 durable 首验属预期行为确认，不单独沉淀。 -->

<!-- 2026-06-07: v0.9.35 沉淀完成（B044：§12.10 enforcement 模型转变 + 停机恢复 prod==HEAD）：两条 signoff §Framework Learnings 用户批立即沉淀。(1) 新规律 trade/ 入 venv → §12.10 物理缺席保护失效 → 转 AST 守门：写 generator.md §12.10.2 + 规约 6 + 对比表 v0.9.35 行。(2) 新坑 长停机 SCP 静默失败致 prod 卡上一版本：写 README §经验教训「生产部署/停机恢复」子节。CHANGELOG v0.9.35。Soft-watch S1（VM disk 82%）转 project-status 监控（用户选直接 B045，disk 不阻断）；S2/S3（fixture 数据/sleeve stub）留 B045 真数据切换。 -->

<!-- 2026-06-07: v0.9.36 沉淀完成（B045：venv 多包安装 deploy 静默装不上 + smoke import check 铁律）：B045 F004 Finding #2（--upgrade 同版本 skip）+ S4（--force-reinstall 仍停旧版需手动）。用户批沉淀 README §经验教训「venv 多包安装」子节（铁律 deploy 后必加 smoke import check）+ CHANGELOG v0.9.36。S4 的 durable 修复（诊断 trade wheel 自动装根因 + deploy 后 smoke import check）转 B045-OPS1 ops 批次（用户选先修 S4 再 B046）。disk S1（84% 爬升）继续 project-status 监控；S2/S3（hk_china stub by-design / us_quality 选 SGOV 策略行为）留 B046。 -->

<!-- 2026-06-07: v0.9.37 沉淀完成（B048：同一风控常数多处副本 → 单一来源 + feature-grounding）：kill_switch 阈值三处副本(rec 0.20/risk_panel 0.15/dashboard 0.20)不一致。用户批沉淀 README §经验教训「同一风控/业务常数多处副本 → 单一来源 + feature-grounding 决定本批改几处」(抽单一来源 ≠ 本批全改) + CHANGELOG v0.9.37。dashboard 第三份阈值 + master_drawdown 0.0 占位 → 并入 B049 dashboard 清理(backlog)。Finding #1(alembic 未自动升级)→ B048-OPS1 ops 修复批次(用户批拆出)。 -->

<!-- 2026-06-08: v0.9.38 沉淀完成（B022/B045-OPS1/B048-OPS1 三例合并：deploy 步骤必须 post-step assert 验证 intended end-state）：deploy 步骤静默失效三例（env→scratch DB / trade wheel install 没装上 / alembic 守门条件静默跳过），均致 prod 静默破坏。用户批沉淀 generator.md §12.11（命令返回 0/守门通过 ≠ 成功；必须 post-step ASSERT end-state 硬失败；守门条件不静默跳过关键步骤）+ CHANGELOG v0.9.38。统一 v0.9.36 smoke import check（其为本规则在包安装步骤的实例）。 -->

## [2026-06-08] Claude CLI — 来源：BL-B011-S2 F002 实施（satellite 策略权重口径）

**类型：** 新规律（master sleeve 策略权重口径约定）

**内容：** master sleeve 子策略 `generate_signal().weights_dict()` 必须返回 **sleeve-relative 权重求和=1.0**（master_portfolio._resolve_child_weights 直接当 sleeve-relative 用，再按 planning_weight 缩放）。故策略说明书里的 **total-portfolio caps**（如 HK-China 设计 §9.1 per-ETF≤10% total / KWEB≤5-10% total）实施时必须换算为 sleeve-relative（÷planning_weight）：sleeve 占 10% 时，per-ETF total 10% = sleeve-relative 1.0（单标的可占满 sleeve）。**坑**：planner 把 total-level cap 值（max_position_weight=0.10）直接写进 feature acceptance 作为策略参数，与 sleeve-relative sum=1.0 不兼容（top_n × 0.10 < 1.0 永远填不满）。本批按权威设计说明书 §8.2（Top-1 占满模块）裁定=sleeve-relative，max_position_weight 默认 1.0 + 文档详注，total cap 由 master planning_weight 承担。

**建议写入：** `framework/harness/planner.md`（spec 写 satellite 策略 acceptance 时，cap 参数须标注 total-level vs sleeve-relative，避免 generator 二义）；或 strategy-design 约定文档「master 子策略权重口径 = sleeve-relative sum-to-1.0」。

**状态：** 待确认（BL-B011-S2 done 阶段一并提出；evaluator F004 可复核口径是否正确）

<!-- 2026-06-08: v0.9.39 沉淀完成（B034/BL-B011-S2 二例：wheel packages 只打源码树，运行时非包数据须 force-include）：BL-B011-S2 trade wheel 缺 repo-root data/fixtures→satellite 双 stub（editable 掩盖 wheel-on-VM 暴露，同 §12.10 机理）。用户批沉淀 generator.md §12.10.3（force-include/materialise 进包目录+守门测试+L2 fresh deploy 验不 stub）+对比表 v0.9.39 行+CHANGELOG。 -->

<!-- 当前无活动候选（待确认条目）。 -->
