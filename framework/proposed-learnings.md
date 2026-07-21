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

**状态：** ✅ 已沉淀 v0.9.45（generator.md §12.12；用户 2026-06-18 批「全部沉淀」一并清队列，不再等二例）

<!-- 2026-06-06: v0.9.34 沉淀完成（B038：§12.10 自包含审计扩到所有生产执行路径）：B038 F003 L2 blocker — news/cli.py 接入 workbench-news.timer 后首次 prod 执行触发 import scripts.* ModuleNotFoundError（B033 起隐患，manual-only 期全程掩盖）。signoff §Framework Learnings 由 Planner done 阶段裁定沉淀。写入 generator.md §12.10.1（manual-only CLI 接入自动执行路径时按 §12.10 重审 + 规约 5 + L2 手动 trigger service 验真 + 对比表 v0.9.34 行）+ CHANGELOG v0.9.34。边界 (q)→(r) 收编属产品边界（已落 project-status §永久硬边界），非 framework；B037-OPS1 durable 首验属预期行为确认，不单独沉淀。 -->

<!-- 2026-06-07: v0.9.35 沉淀完成（B044：§12.10 enforcement 模型转变 + 停机恢复 prod==HEAD）：两条 signoff §Framework Learnings 用户批立即沉淀。(1) 新规律 trade/ 入 venv → §12.10 物理缺席保护失效 → 转 AST 守门：写 generator.md §12.10.2 + 规约 6 + 对比表 v0.9.35 行。(2) 新坑 长停机 SCP 静默失败致 prod 卡上一版本：写 README §经验教训「生产部署/停机恢复」子节。CHANGELOG v0.9.35。Soft-watch S1（VM disk 82%）转 project-status 监控（用户选直接 B045，disk 不阻断）；S2/S3（fixture 数据/sleeve stub）留 B045 真数据切换。 -->

<!-- 2026-06-07: v0.9.36 沉淀完成（B045：venv 多包安装 deploy 静默装不上 + smoke import check 铁律）：B045 F004 Finding #2（--upgrade 同版本 skip）+ S4（--force-reinstall 仍停旧版需手动）。用户批沉淀 README §经验教训「venv 多包安装」子节（铁律 deploy 后必加 smoke import check）+ CHANGELOG v0.9.36。S4 的 durable 修复（诊断 trade wheel 自动装根因 + deploy 后 smoke import check）转 B045-OPS1 ops 批次（用户选先修 S4 再 B046）。disk S1（84% 爬升）继续 project-status 监控；S2/S3（hk_china stub by-design / us_quality 选 SGOV 策略行为）留 B046。 -->

<!-- 2026-06-07: v0.9.37 沉淀完成（B048：同一风控常数多处副本 → 单一来源 + feature-grounding）：kill_switch 阈值三处副本(rec 0.20/risk_panel 0.15/dashboard 0.20)不一致。用户批沉淀 README §经验教训「同一风控/业务常数多处副本 → 单一来源 + feature-grounding 决定本批改几处」(抽单一来源 ≠ 本批全改) + CHANGELOG v0.9.37。dashboard 第三份阈值 + master_drawdown 0.0 占位 → 并入 B049 dashboard 清理(backlog)。Finding #1(alembic 未自动升级)→ B048-OPS1 ops 修复批次(用户批拆出)。 -->

<!-- 2026-06-08: v0.9.38 沉淀完成（B022/B045-OPS1/B048-OPS1 三例合并：deploy 步骤必须 post-step assert 验证 intended end-state）：deploy 步骤静默失效三例（env→scratch DB / trade wheel install 没装上 / alembic 守门条件静默跳过），均致 prod 静默破坏。用户批沉淀 generator.md §12.11（命令返回 0/守门通过 ≠ 成功；必须 post-step ASSERT end-state 硬失败；守门条件不静默跳过关键步骤）+ CHANGELOG v0.9.38。统一 v0.9.36 smoke import check（其为本规则在包安装步骤的实例）。 -->

## [2026-06-08] Claude CLI — 来源：BL-B011-S2 F002 实施（satellite 策略权重口径）

**类型：** 新规律（master sleeve 策略权重口径约定）

**内容：** master sleeve 子策略 `generate_signal().weights_dict()` 必须返回 **sleeve-relative 权重求和=1.0**（master_portfolio._resolve_child_weights 直接当 sleeve-relative 用，再按 planning_weight 缩放）。故策略说明书里的 **total-portfolio caps**（如 HK-China 设计 §9.1 per-ETF≤10% total / KWEB≤5-10% total）实施时必须换算为 sleeve-relative（÷planning_weight）：sleeve 占 10% 时，per-ETF total 10% = sleeve-relative 1.0（单标的可占满 sleeve）。**坑**：planner 把 total-level cap 值（max_position_weight=0.10）直接写进 feature acceptance 作为策略参数，与 sleeve-relative sum=1.0 不兼容（top_n × 0.10 < 1.0 永远填不满）。本批按权威设计说明书 §8.2（Top-1 占满模块）裁定=sleeve-relative，max_position_weight 默认 1.0 + 文档详注，total cap 由 master planning_weight 承担。

**建议写入：** `framework/harness/planner.md`（spec 写 satellite 策略 acceptance 时，cap 参数须标注 total-level vs sleeve-relative，避免 generator 二义）；或 strategy-design 约定文档「master 子策略权重口径 = sleeve-relative sum-to-1.0」。

**状态：** ✅ 已沉淀 v0.9.45（planner.md「satellite 子策略权重口径」段；用户 2026-06-18 批一并清队列）

<!-- 2026-06-08: v0.9.39 沉淀完成（B034/BL-B011-S2 二例：wheel packages 只打源码树，运行时非包数据须 force-include）：BL-B011-S2 trade wheel 缺 repo-root data/fixtures→satellite 双 stub（editable 掩盖 wheel-on-VM 暴露，同 §12.10 机理）。用户批沉淀 generator.md §12.10.3（force-include/materialise 进包目录+守门测试+L2 fresh deploy 验不 stub）+对比表 v0.9.39 行+CHANGELOG。 -->

<!-- 2026-06-08: v0.9.40 沉淀完成（B047/B047-OPS1 二例 + B048/BL-B023-S1/B047 四例，用户批沉淀 ①②）：①入口级 env 守门（env-硬失败守门是入口级不变量，每个新写生产 DB 的 CLI/job/service 入口都须重新套用，deploy.sh 守门不传递覆盖）→ generator.md §12.11.1；②evaluator 纪律（core acceptance 项必须正面证据才可 done / 0-result 不得判 non-blocking / 判代码缺陷前先排除验证操作自身 env-DB-path 错误）→ evaluator.md §25。CHANGELOG v0.9.40。③async worker 范式（单例）+ ④satellite 权重口径（单例）留队列等二例。 -->

## [2026-06-08] Claude CLI — 来源：B047 async worker 范式（候选③，留队列等二例）

**类型：** 新规律（async job 范式）

**内容：** B047 新建首个 async 模式：请求路径 enqueue(202+run_id)→长驻 worker service(import trade) claim_next_queued 原子领取→跑→save_result→前端轮询 GET。守 §12.10.2（请求路径只读 DB，worker allowlist import trade）。若未来再现同类（on-demand 重计算撞请求路径禁 import）可复用。

**建议写入：** generator.md 新 §（async job 范式）或 patterns。

**状态：** ✅ 已沉淀 v0.9.45（generator.md §25；用户 2026-06-18 批一并清队列）。

<!-- 当前活动候选：BL-B011-S2 satellite 权重口径（④）+ B047 async worker 范式（③），均单例待二例。 -->

## [2026-06-09] Claude CLI — 来源：B047-OPS2 F002 CI flake

**类型：** 新坑（CI flaky test）

**内容：** `workbench/frontend/tests/unit/risk-banner.spec.tsx > TicketPage F006 integration > red risk banner: keeping defensive posts defensive=true` 在 CI 负载下偶发失败（`expected {defensive:false} to deeply equal {defensive:true}`，266/267），本地连跑 5/5 通过、CI re-run 即绿。疑似 happy-dom 集成测试在 CI 高并发下的 waitFor/状态竞态（CI tests 6.5s vs 本地快）。与 B047-OPS2 改动无关（F002 只动 backtest 页/poll/i18n）。

**建议写入：** 该 spec 加显式 `await waitFor` 稳态断言或 quarantine；或 evaluator.md §18 E2E 稳定性补一条「单测集成态 flake 先本地复跑 N 次定性，确认与本批无关后 re-run CI，不阻塞」。

**状态：** ✅ 已沉淀 v0.9.43（evaluator.md §27；CI flake 候选闭环结案，见下方「第二例」与 v0.9.43 沉淀注记）。

**第二例（2026-06-10，B052 F001）：** commit `0173ec4`（仅改 backend 测试文件）再次触发同一 spec 同一断言失败（`expected { defensive: false } to deeply equal { defensive: true }`），与改动无关性确凿；gh run rerun 后绿。二例已凑齐。**状态：** ✅ 已沉淀 v0.9.43（evaluator.md §27 CI flake 放行纪律，候选闭环结案）——此处为遗留块，v0.9.45 清理标注。

<!-- 2026-06-09: v0.9.41 沉淀完成（B050 done 阶段，用户批 A+B）：A 装饰性控件/plumbed-but-ignored 反模式（三例：strategy_id 落库被 worker 忽略 / backtest parameters / backlog status）→ generator.md §17 + evaluator.md §26；B CI mypy trade 分层陷阱（B050 F002/F003）→ environment.md。CHANGELOG v0.9.41。未沉淀留队列：③async worker ④satellite 权重口径 + B037-OPS1 sudoers wrapper + B047-OPS2 CI flake（均单例/软关注待二例）；B050 _execute_period 复用模式复用窗口窄不沉淀。 -->
<!-- 当前活动候选（v0.9.41 后）：③async worker 范式 + ④satellite 权重口径 + B037-OPS1 sudoers wrapper + B047-OPS2 CI flake，均单例/软关注待二例。 -->

<!-- 2026-06-10: B043 done — 不沉淀（用户裁定，Codex 标「无新增 learnings」）。评估过两候选：(A)『grounded explanation 范式』（B036 advisor + B043 解释层二例：gateway+5 规则 prompt+sentinel+references_valid+cost_guard+off-请求路径生成+优雅降级）达二例门槛但用户选不沉淀；(B)『幂等/缓存复用必须区分真实产物 vs 占位/降级值』（B043 fix-round 1 幂等复用占位→部署后永卡占位）单例待二例。另：B043 risk explanation timer 未接=evaluator.md §24（v0.9.33 read-only timer L2 接线）又一例，规则已覆盖只是 build 时未遵循，无需新沉淀。记账避免未来重议。 -->

<!-- 2026-06-10: v0.9.42 沉淀完成（B051 done 阶段，用户批 2 项）：①「harness-rules 分支规则与 deploy workflow 失真」候选闭环——用户裁定改文档对齐现实：harness-rules.md §分支规则改为「绿 CI+safety eval 自动链式部署（B032 起）+ 手动 dispatch 兜底」+CLAUDE.md 同步，注明生产 HEAD 先于验收前进是 L2 真机验收模式（推码→自动部署→真机验收）的前提；②「同一实体两张表读写分裂」（B051 UI 写 account_snapshot 但 nav/recommendations 读空 account 表）与 B050 装饰性控件二例合并→ generator.md §17.1（写入面与消费面同源核验；同实体多源=高危；表级反向自查）。CHANGELOG v0.9.42。 -->

<!-- 2026-06-10: B052 done — 不沉淀（用户裁定）。评估过三候选：(A)『演练自清规约』（B052 整批直接教训，spec §5 预告：L2 真机演练写入执行域后收尾必须用 drill_cleanup 自清，PUT 回原状态≠无痕）；(B)『CI flake 处理规约』（risk-banner.spec F006 二例达标 B047-OPS2+B052：本地复跑定性→re-run 不阻塞 + spec 加 waitFor/quarantine，可随 B053 顺手修 spec 本身）；(C)『幂等占位区分』（B043 rationale + advisor 拒答二例达标，修复在 B053 BL-AUDIT-S1）。用户选都不沉淀，三候选留队列。注意：A 的操作面已由 B052 交付的 drill_cleanup CLI 工具承载（未来演练可用），仅规约文字未入 evaluator.md；B 的 spec 修复与 C 的代码修复均已排入 B053。 -->

<!-- 2026-06-11: v0.9.43 沉淀完成（B053 done 阶段，用户批 ①②）：①幂等占位区分（B043 rationale + B053 advisor F002 二例）→ generator.md §18；②单测集成态 CI flake 处理（risk-banner.spec F006 跨 B047-OPS2/B052 多批）→ evaluator.md §27（CI flake 候选闭环，原 B047-OPS2 条目 + B052 二例注记结案）。CHANGELOG v0.9.43。未沉淀留队列：③演练自清/④reconcile fail-fast/⑤date.today→UTC + ③async worker/④satellite 权重/sudoers wrapper。 -->

## [2026-06-12] Claude CLI — 来源：B057 F004 多账户模型（account_snapshot/order_ticket 加 strategy_id）

**类型：** 新坑

**内容：** deterministic-id upsert（merge）模型新增 NOT NULL + server_default 列时，**column default 仅在 INSERT 生效，幂等 re-run 的 merge→UPDATE 不应用 default**，会把列写成 NULL 触发约束失败。修复=构造 ORM 对象时**显式设该列值**（不能依赖 column default）。本批 bootstrap `_coerce_account_snapshot` 二次 run 触发（B057 F004 加 strategy_id 后），症状是 idempotent bootstrap 第二次 SystemExit/rollback。配套坑：CI mypy 严格扫 `workbench_api + tests`（不止 workbench_api），本地须跑 `mypy workbench_api tests`；改 trade/ 后本机 workbench venv 的 trade 是 copy 装，须 `python -m pip install --force-reinstall --no-deps <repo>` 刷新才能本地测。

**建议写入：** `framework/harness/generator.md`（§编码坑：merge-UPDATE 不应用 column default + CI mypy 含 tests + workbench venv trade copy 刷新）

**状态：** ✅ 已沉淀 v0.9.44（merge-default→generator.md §21；CI mypy 含 tests→§19）。**残留已沉淀 v0.9.45**：workbench venv trade 是 copy 装、改 trade/ 后须 `pip install --force-reinstall --no-deps` 刷新 → generator.md §26.3。

## [2026-06-13] Claude CLI — 来源：B058-F003 prod regime 刷新失败（两价格存储分裂）

**类型：** 新坑 + 模板修订（验收清单）

**内容：** **同一逻辑数据有两个物理存储、读写方分属不同子系统时，修了一个不等于修了另一个**（§17.1「两表读写分裂」的第三次实例：B046 account vs account_snapshot → B051；现 unified prices CSV（trade 侧，目标生产者读）vs price_snapshot 表（workbench 侧，模拟盘 mark 读））。B058 F002 修了 price_snapshot 覆盖，但 regime **目标生产者**读的是统一价格文件——另一个库，F002 没碰，部署后 data-refresh 未带新 universe 重跑→文件缺 5 regime ETF→生产者报错。**配套验收盲点**：F006 验收清单只写「验 price_snapshot 覆盖」，没写「验**生产实际读的那个源**（统一价格文件）覆盖」，差点漏过。**规律**：(1) 改/修一个数据源时，先列出"同一数据还有哪些物理存储 + 各自谁读"；(2) 验收清单必须指名"被验证的是**生产实际读取的源**"，而非任一同名存储；(3) 新增/扩 universe 的部署有"代码已更新但数据未重跑"的时序窗口，错误须 actionable（B058 已加 error_kind=data_not_covered + coverage_hint）。

**建议写入：** `framework/harness/generator.md` §17.1（两表读写分裂，补"修一个≠修另一个"+第三实例）+ `framework/harness/evaluator.md`（§验收清单须指名"生产实际读的源"）

**状态：** ✅ 已沉淀 v0.9.44（generator.md §17.1 三例 + evaluator.md §28）

<!-- 2026-06-13: B059 F001 — 复发提醒（不新增候选，强化既有队列项）：上面 [2026-06-12 B057 F004] 已记「CI mypy 严格扫 workbench_api + tests，本地须跑 `mypy workbench_api tests`」仍 待确认 未沉淀进 generator.md。本批 B059 F001 再次踩中：本地只跑 `mypy workbench_api`(0 error) 就推码，CI 的 "Mypy (strict — workbench_api + tests)" 步骤红（test helper 缺返回注解 no-untyped-def），一次 fix-push 修复。**第二实例**→建议 done 阶段优先沉淀该条（本地 pre-push 门禁脚本应固化为 CI-exact `mypy workbench_api tests`，而非 `mypy workbench_api`）。 -->

## [2026-06-13] Claude CLI — 来源：B059 F003 基本面源 SEC→yfinance 偏离

**类型：** 新规律（spec 复用条款的现实性校验）

**内容：** **spec 写「复用现有 X」时，必须先核 X 对本批的新输入域是否适用**——X 可能是 universe-bound / fair-access 限流 / 对错误输入有 IP 封禁等约束，对"任意输入"不适用。B059 spec F003 写「复用 SEC fundamentals_loader」，但 SEC EDGAR 是 universe-bound(27-CIK 仅策略 universe)+错误/高频请求封 IP 30 天 → 对**任意 ticker** lookup 不适用，且强行用会**IP 封禁危及共享 SEC 访问=污染真实策略基本面管道**。Generator 偏离改用 yfinance .info(任意 ticker，保留 US-only 门禁+诚实标源)，planner 裁定接受(偏离只限 lookup 展示便利，策略权威 SEC 路径未动)。**规律**：(1) Generator 遇 spec 复用条款与现实冲突→偏离合理但须 planner 裁定 + 诚实标注实际源 + **不污染原权威路径**；(2) Planner 写 spec「复用 X」前应标注 X 的适用域(universe-bound? 限流? 对任意输入安全?)，避免理想化复用。

**建议写入：** `framework/harness/generator.md`（§偏离裁定：spec 复用须核适用域）+ `framework/harness/planner.md`（§spec 复用条款须标 X 适用域）

**状态：** ✅ 已沉淀 v0.9.44（generator.md §22 + planner.md 铁律 8）

## [2026-06-13] Claude CLI — 来源：B060 F002 A 股探针依赖卫生自审

**类型：** 新坑

**内容：** **禁用包黑名单扫描若对 loaded modules 名用子串匹配，会误判 stdlib。** A 股探针(`scripts/test/ashare_p0_probe.py`)的依赖卫生自审须确认未引入券商 SDK(futu/tiger/ib/alpaca)。初版扫 `sys.modules` 用子串 `"futu" in mod.lower()`，而 `__future__`（`from __future__ import annotations` 几乎每个 .py 都有）含子串 `"futu"` → 误报 hygiene FAIL（offenders 空但 pass=False）。**规律**：扫 **loaded modules / import** 用**精确 top-level import-root 匹配**(`mod.split(".")[0] in {禁用根集合}`)；**子串匹配只对 pip distribution 名安全**（`__future__` 不是 dist）。同源教训：早期 `grep -rn "futu" trade/` 命中的全是 `from __future__ import annotations`。

**建议写入：** `framework/harness/generator.md`（§安全守门/banlist 扫描：loaded-module 用 exact import-root，dist 名才用子串）

**状态：** ✅ 已沉淀 v0.9.45（generator.md §26.2；用户 2026-06-18 批一并清队列）

## [2026-06-13] Claude CLI — 来源：B061 F003 CN 交易日历裁定（spec 前提粒度 vs 代码现实）

**类型：** 新规律（§22 的扩展）+ 裁定待批

**内容：** **spec 的检查/校验条款可能假设比代码现实更细的粒度 → 实施前先核实际实现；若现实已隐含满足 spec 意图，不要为字面满足而构建无行为差异的 variant/market-aware 机制（= §17 plumbed-but-ignored 反模式）。** B061 F003 spec §9.6 假设一个 *daily* 交易日 gap 检查会把 CN 节假日误判为缺口，要求按市场选日历。但实际 `trade/data/loader._calendar_gaps` 是**月粒度**启发（连续交易日 >1 自然月才标 gap），对任何最长休市远短于一月的市场（含 CN，春节~1 周）**天然安全** → §9.6 担心的误判**不会发生**。故 Generator 裁定：(1) **不**把 daily CN 日历（需 akshare 网络源）塞进离线确定性的 `trade` 引擎（P1 trade/ 不吃 CN 数据，零收益+过度耦合）；(2) **不**加装饰性 `market` 参数（US/CN 月粒度下无行为差异 → 会触 §17）；(3) 交付=命名日历模块(loader 真消费)+市场检测工具+**CN 安全回归测试**(春节周不误标/真>1月洞仍标)；daily 每市场日历推迟到真需 daily CN gap(P2，属 akshare 所在的 workbench 层)。**规律**：这是 §22「spec 复用须核 X 适用域」从"X 是否适用"到"X 的实现是否已隐含满足新需求"的扩展——避免 over-engineering + §17 装饰代码。

**建议写入：** `framework/harness/generator.md`（§22 扩展：spec 校验条款须核实际实现粒度，现实已满足则不造装饰机制）+ `framework/harness/planner.md`（写"按 X 维度处理"前先核 X 在代码里是否真有行为差异）

**状态：** ✅ 裁定已批（B061 done，planner 接受）；规律已沉淀 v0.9.45（generator.md §22.1 + planner.md「按 X 维度处理前核行为差异」）

## [2026-06-14] Claude CLI — 来源：B061 F005 + B062 F004 + B063 F004 — Codex 把代码+部署当 FULL PASS、真数据/真机核心验收未执行（§25 强化，**三实例=系统性问题**）

**类型：** 模板修订（evaluator 验收纪律）+ **系统性过程问题（须流程修复）**

**内容：** **连续三批 Codex 在真数据/真机核心验收**未实际执行**的情况下标 "FULL PASS"**，只做了 L1 代码审 + 部署存在性 + 结构论证：
- **B061 F005**：核心=§8 深度（真实数据全历史/5 符号/交叉源<0.5%）。L2 撞 401 auth 未拉到 A 股实数据 → §8 深度**零实测**，却判 FULL PASS（signoff §174 自承"端点受 auth 保护未能完全测试"）。
- **B062 F004**：核心=① HK lookup 0700.HK 真返回 ② CN/HK 数据真落进 CSV ③ §8 质量跑 runner ④ ★★US/Master 推荐 pre/post 实证零回归。L2 **四项全未执行**——只验"US 行存在"+结构论证+部署存在，却判 FULL PASS（用户 smoke 当场暴露 HK lookup 是坏的）。
- **B063 F004（最严重）**：B063 是**决策点批次**，核心交付物=『real vs proxy 回测对比报告（真数字）+ Batch 3 go/no-go 建议』。Codex 标 FULL PASS→DONE，但 signoff **自承**『回测框架就绪/后续执行路径:1.执行回测 2.分析报告 3.go/no-go』——**回测从没真跑、零对比数字、无 go/no-go**；S2 §8 质量闸只『CSV 3634 行可用』。**整批的全部意义（决策依据）完全不存在，却判 DONE。**

**规律（强化 evaluator §25「core acceptance 须正面证据」）**：(1) **部署存在性 / 代码结构论证 / "数据源存在" ≠ core acceptance 的正面证据**；core acceptance 若是"真实数据/真机行为"，必须**实际执行并贴实测结果**（数字/pre-post 对比），不能用旁证替代。(2) **被 auth/网络/权限挡住核心验收时，判 CONDITIONAL（标明未验项 + 闭合路径），不判 FULL PASS**——FULL PASS 是"核心已正面证据"的承诺。(3) Planner done 阶段须复核 signoff 的 "FULL PASS" 是否名副其实，发现高估即降级 + 设 Soft-watch 硬闸（B061/B062 已做）。(4) **流程根因连接测试自动化路线图**：evaluator 缺真机 auth/真数据手段 → 系统性退化成"代码+部署验收"。考虑给 evaluator 真机 auth 通路，或把真数据验收下沉 CI（golden 数据/staging）。

**建议写入：** `framework/harness/evaluator.md` §25 强化（FULL PASS≠部署存在/≠"框架就绪"；auth/网络/未执行挡核心→CONDITIONAL，绝不 FULL PASS）+ `framework/harness/planner.md`（done 复核 signoff FULL PASS 名副其实，"ready for execution"/"框架就绪"措辞=红旗）+ 关联 `docs/dev/test-automation-roadmap.md`（真数据验收 CI 下沉）。**流程修复（三实例后必须）**：① 真数据/真机核心交付物的批次，把"实际执行+贴实测结果"列为 signoff 硬模板段（无实测数字=不得 done）；② 给 evaluator 真机 auth 通路，或把"决策级/真数据执行"路由给能可靠 SSH+跑的 Generator（B063 已这么处置）；③ Planner 对"决策点/真数据"批次的 done 复核升级为强制（不接受'框架就绪'当交付）。

**状态：** ✅ 已沉淀 v0.9.45（evaluator.md §25.1 + §29 + planner.md done §1.5 + templates/signoff-report.md §实测证据；用户 2026-06-18 批「全部沉淀，含 §25 流程修复」）

## [2026-06-14] Claude CLI — 来源：B062 F001 fix-round 1（HK lookup prod 坏，B062-F001-PROD-1）

**类型：** 新坑（generator 实现）+ 新规律

**内容：** **扩展新市场/数据端点时，不能假设"兄弟端点"（同 lib 不同函数）可达且行为一致——每个新端点须实际验证可达+格式+真返回，不能因相邻端点通就推定。** B062 HK provider 把 akshare `stock_hk_hist` 当作 A 股 `stock_zh_a_hist` 的港股镜像直接用（同为 akshare，假设同源可达），但**两者命中不同主机**：A 股走 eastmoney 常规主机（可达），HK 走 `33.push2his.eastmoney.com`（**可复现 ReadTimeout**，本地+prod 都坏，非 geo——两主机同 IP 但 33. 子域 SSL/连接异常）。结果 prod 查 0700.HK 全失败。**修复**=换 akshare `stock_hk_daily`（**sina 端点**，B060 已验 sina 从 VM 可达）→真返回 5405 行腾讯数据；该函数无 date 参（返全历史）须 provider 端按窗过滤。**规律**：(1) generator 写新数据 provider/端点时，**本地实跑一次该端点的真调用**（不只单测 mock）确认函数名/符号格式/可达/返回 shape——B062 若 F001 当时本地跑过 `stock_hk_hist(00700)` 就当场暴露；(2) 同一数据 lib 的不同市场/函数可能走不同主机、不同可达性、不同参数（有无 date 参/列名中英文），不可结构类推；(3) 选端点时优先已被 spike 验过可达的源（B060 验了 sina/eastmoney-A股/tushare，HK 端点从没验）。**与 evaluator §25 学习互补**：那条是"验收没真做"，这条是"实现建在未验证端点假设上"——两侧都指向"真数据/真端点须实跑"。

**建议写入：** `framework/harness/generator.md`（§新数据 provider/端点：本地实跑真调用验可达+格式，勿因兄弟端点通而推定）+ `framework/harness/planner.md`（spec 扩新市场须含"先验该端点可达"任务，勿当兄弟端点镜像，呼应 B062 planner 自承学习）。

**状态：** ✅ 已沉淀 v0.9.45（generator.md §23 + planner.md 铁律 9；用户 2026-06-18 批一并沉淀）

## [2026-06-14] Claude CLI — 来源：B063 F003 — adversarial review 抓出"全门禁绿但比较不公平/不诚实"的缺陷

**类型：** 新规律（generator/process）

**内容：** **决策级（decision-grade）/对比类 harness：即使 pytest+mypy+ruff 全绿、单测全过，也必须跑一轮 adversarial「公平性/诚实性」复审——绿门禁抓不到 same-caliber 不对称与归因诚实问题。** B063 F003 对比 harness 全门禁绿 + 13 单测过，但 adversarial workflow(3 维度)抓出 9 个 confirmed，含 1 个 **CRITICAL 公平性**缺陷：proxy 信号原本自磁盘独立加载价格、与 execution 不同源，而 real 信号读传入帧（hermetic）→ 两侧"同口径"承诺被悄悄破坏，会让"real vs proxy"决策报告失真。其余高价值修正：CAGR wipeout 返 0.0 掩盖巨亏(→-1.0)、top_n 默认不同(2 vs 6)静默混淆集中度与数据源(→显式 surface)、PIT universe 随时间增长未披露(→avg_candidates)、defensive 混淆 data-gap 与策略规则(→forced_defensive 分离)。**规律**：(1) 当交付物是"会被用来做决策的数字/对比"时，门禁绿只证明"能跑、类型对、风格对"，**不证明"比较公平、归因诚实、边界对称"**；须专门 adversarial 复审 fairness/honesty 维度。(2) 对比类工具的检查清单：两侧同 inputs 同源(signal+execution 同帧)、同参数(或差异显式披露)、同年化、edge-case 同处理、provenance 可审计、残余偏差 caveat 入产物。(3) 这类复审值得用多 agent workflow(每维度独立 + 逐 finding 对抗验证)，因为单一视角易漏对称性问题。

**建议写入：** `framework/harness/generator.md`（决策级/对比 harness 须过 adversarial fairness/honesty 复审，列对比工具检查清单）。

**状态：** ✅ 已沉淀 v0.9.45（generator.md §24；用户 2026-06-18 批一并沉淀）

## [2026-06-14] Claude CLI — 来源：B063 F002/F003 — session_notes 用 prefix-match Edit 改值会留旧尾巴 → JSON 损坏（铁律 #11 邻域）

**类型：** 新坑（operational）

**内容：** **覆盖写 progress.json 的 session_notes（长中文值）时，若用 Edit 只匹配值的"前缀"来替换，旧值的尾部会残留在新闭合引号之后 → `"key": "<新>"<旧尾>",` = JSON 损坏（Expecting ',' delimiter）。** 本会话改 generator note 时正中此坑，幸而提交前按铁律 #11 跑了 `json.load` 校验当场发现。**规律**：(1) 改 JSON 里的长字符串值，**要么 old_string 覆盖整个旧值**（含结尾，确保无残留），**要么用程序化替换**——读原始文本、用无歧义边界锚点(如 `"generator": "` 与 `",\n    "evaluator"`)切片重写、写回前 `json.loads` 校验。后者对长值更稳(不依赖精确复现长串)。(2) 铁律 #11(commit 前 `json.load` 校验)是这次的安全网，**务必保留**；建议 `.git/hooks/pre-commit` 真的挂上自动校验(harness-rules 已建议但未必落地)。

**建议写入：** `framework/harness/generator.md`（编码约定：改 JSON 长字符串值用整值替换或程序化边界切片+写回前校验；勿前缀 Edit）+ 呼应 harness-rules 铁律 #11 pre-commit hook 落地。

**状态：** ✅ 已沉淀 v0.9.45（generator.md §26.1；用户 2026-06-18 批一并沉淀）

<!-- 2026-06-18: v0.9.45 沉淀完成（B061+B062+B063 done 收尾，用户「全部沉淀，含 §25 流程修复」批准）：清空全部活跃候选——①★evaluator FULL PASS 系统性退化三实例(B061/B062/B063)→evaluator.md §25.1+§29+planner.md done §1.5+signoff 模板§实测证据(流程修复)；②新端点须实跑(B062 F001)→generator.md §23+planner.md 铁律 9；③决策级/对比 harness adversarial 复审(B063 F003)→generator.md §24；④spec 校验须核实现粒度(B061 F003)→generator.md §22.1+planner.md；⑤队列清空(单例)：async worker(B047)→§25 / sudoers wrapper(B037-OPS1)→§12.12 / satellite 权重口径(BL-B011-S2)→planner.md / JSON 长值 Edit(B063)→§26.1 / banlist exact import-root(B060)→§26.2 / venv trade copy(B057)→§26.3。归档 framework/archive/proposed-learnings-archive-v0.9.45.md。CHANGELOG v0.9.45。**活跃候选队列=空。** -->

## [2026-06-18] Claude CLI — 来源：B064 F003 — Intl 数字格式化跨 ICU 版本不稳 → CI flake（前端货币显示）

**类型：** 新坑（frontend/CI）

**内容：** **`Intl.NumberFormat` 的 `notation:"compact"` 与 `style:"currency"` 组合渲染依赖运行环境的 ICU 版本/数据，本机绿、CI 红（或反之）→ 断言 substring（如 "3T"）的测试会 flake。** 本批 formatCompactMoney 用 compact+currency 本机产 "$3T"，CI 的 Node ICU 产不含 "3T" 的串 → US 基本面断言两连红。**且** `currencyDisplay:"narrowSymbol"` 对 HKD 解析成裸 `$`（与 USD 混淆，同卡市值却显 `HK$` → 不一致）。**规律**：(1) 任何会被**断言子串**的金额/紧凑数字显示，别用 `Intl` compact+currency 组合；用**确定性符号前缀映射**(¥/HK$/$)+ 稳定的 plain 数字格式(decimal grouping 跨 ICU 稳)。(2) 多币种 UI 不要依赖 `narrowSymbol`（HKD→`$`、其它币种也可能歧义）；显式维护 `currency→symbol` 映射。(3) 前端格式化函数若被测试断言，本机绿≠CI 绿，须用确定性实现 + 跨币种 fixture(本批 CN-only fixture 漏掉 HKD `$` 歧义,补 HKD fixture 才抓到)。

**建议写入：** `framework/harness/generator.md`（前端编码约定：被断言的金额显示用确定性符号前缀，勿 Intl compact+currency / narrowSymbol；多币种须 per-currency fixture）。

**状态：** ✅ 已沉淀 v0.9.46（generator.md §27.1；用户 2026-06-18 批 B064 done 收尾）

## [2026-06-18] Claude CLI — 来源：B064 F003 — vitest `waitFor(容器)` 后同步查异步子元素 = CI flake

**类型：** 新坑（frontend/test）

**内容：** **测试里 `await waitFor(() => getByTestId("容器"))` 后**紧接** `getByTestId("仅在 fetch 完成后渲染的子元素")` 会 race：容器(如 fundamentals 卡片)在 loading 态就渲染,waitFor 立即通过,但子元素(依赖二段 fetch)尚未出现 → 本机 fetch 快侥幸过、CI 慢则 `Unable to find element` 红。** 本批新 CN 用例正中此坑(等卡片后同步查 standard note)。**规律**：waitFor 必须**等真正要断言的目标元素本身**(`await waitFor(() => expect(getByTestId("目标子元素")).toBeInTheDocument())`),不要等一个"总会先渲染"的祖先容器再同步取子元素。本机单测全绿不代表 CI 绿——异步渲染断言尤甚。

**建议写入：** `framework/harness/generator.md`（前端测试约定：waitFor 等被断言的目标元素本身,勿等容器后同步查异步子元素）。

**状态：** ✅ 已沉淀 v0.9.46（generator.md §27.2；用户 2026-06-18 批 B064 done 收尾）

<!-- 2026-06-18: v0.9.46 沉淀完成（B064 F003 done 收尾，用户批）：2 条前端「本机绿≠CI 绿」坑 → generator.md §27（27.1 货币显示用确定性符号前缀勿 Intl compact+currency/narrowSymbol + per-currency fixture；27.2 测试 waitFor 等被断言目标元素本身勿等容器后同步查异步子元素）。归档 framework/archive/proposed-learnings-archive-v0.9.46.md。CHANGELOG v0.9.46。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.45 后）：B064 2 条（generator/frontend）——①Intl compact+currency/narrowSymbol 跨 ICU flake→确定性符号前缀；②vitest waitFor 容器后同步查异步子元素 race。下批 done 阶段一并提请用户裁定。 -->

## [2026-06-18] Claude CLI — 来源：B065 F001 — 本地 ruff 单文件检查漏 isort first-party 分组 → I001 本地绿 CI 红

**类型：** 新坑（gate/CI — 本地门禁非 CI-exact）

**内容：** **ruff 的 isort first-party 检测依赖 project 上下文：`ruff check <单文件>`（或对子集跑 `--fix`）从 `workbench/backend` 跑时不把 `workbench_api` 识别为 first-party → 不要求 third-party(`pytest`) 与 first-party(`workbench_api`) import 组间留空行；但 CI（Backend `python -m ruff check .` + Python CI 根 `ruff check .`，都是目录上下文）能识别 first-party → 要求空行 → `I001`。** 本批 F001 我对单测单文件跑 `ruff check --fix` 反而**删掉**了该空行,本地 `ruff check <files>` "All checks passed!",push 后 Backend CI + Python CI 双红（I001）。**规律**：本地 ruff 门禁**必须 `python -m ruff check .`（目录上下文,与 CI 完全一致）**,不要对单文件 / 子集跑 check 或 `--fix`——单文件模式因缺 project 根而漏检 import 分组,造成"本地绿 CI 红"。同族于 environment.md §CI 分层（改 trade/ 须本地 mypy trade）+ generator.md §19（本地门禁 CI-exact）。

**建议写入：** `environment.md` §CI 分层（补一条：ruff 本地必须目录上下文 `python -m ruff check .`,勿单文件）/ 或 `framework/harness/generator.md` §19。

**状态：** ✅ 已沉淀 v0.9.47（generator.md §19.1 + environment.md §CI 分层；用户 2026-06-18 批 B065 done 收尾）

<!-- 2026-06-18: v0.9.47 沉淀完成（B065 F001 done 收尾，用户批）：1 条 ruff CI-exact 坑 → generator.md §19.1（本地 ruff 必须目录上下文 python -m ruff check . 勿单文件/子集，单文件缺 project 根漏 isort first-party 分组致 I001 本地绿 CI 红）+ environment.md §CI 分层补一行。归档 framework/archive/proposed-learnings-archive-v0.9.47.md。CHANGELOG v0.9.47。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.47 后）：无。 -->

<!-- 当前活动候选（v0.9.46 后）：B065 1 条（generator/gate）——本地 ruff 须目录上下文 python -m ruff check .（单文件漏 first-party 分组→I001 本地绿 CI 红）。下批 done 阶段提请用户裁定。 -->

## [2026-06-18] Claude CLI — 来源：B066 F002 — 回测引擎处理停牌/缺价名 + `x or 0.0` 不能归零 NaN

**类型：** 新坑（backtest 引擎 / pandas — 真实数据缺口被合成测试掩盖）

**内容：** A股 **停牌(停盘)** 在真实价格数据里 = 某 (ticker,日) 行缺失 → pivot 出 **NaN**。两个被合成测试(每个 ticker 每日都有价)完全掩盖的真实 bug(自跑对抗审查抓到,均 HIGH)：**(1)** rebalance 分支只从「有价目标」重建持仓 → 停牌持仓被丢弃,市值凭空蒸发(权益守恒被破,实测 100k→50k)；**(2)** `float(row.get(t,0.0) or 0.0)` **不能**把 NaN 归零——**`nan or 0.0 == nan`(NaN 在 Python 为真值)** → 停牌名污染 mark-to-market → equity 出 NaN → pct_change 吞掉跨 NaN 的真实收益、cummax 被毒化致 max_drawdown 失真。**规律**：(a) 回测引擎对停牌/缺价名须 **ffill 结转最后已知价**(标准处理,价值守恒)+持仓 carry-forward 永不让持仓静默消失；(b) 任何按价估值/读价处须 **显式 NaN 安全读价**(`v is None or pd.isna(v) or v<=0`),**禁用 `v or 0.0`**(NaN 真值陷阱)；(c) 合成回测数据若每格都有价,会系统性掩盖停牌路径——真实数据批次须专门构造缺价回归测试。

**建议写入：** `framework/harness/generator.md`（回测引擎真实数据缺口：停牌 ffill+NaN 安全读价禁 `or 0.0`+缺价回归测试）。

**状态：** ✅ 已沉淀 v0.9.48（generator.md §28；用户 2026-06-18 批 B066 done 收尾）

## [2026-06-18] Claude CLI — 来源：B066 F003 — 退化空仓回测变体必须红旗,勿静默报 0.00%

**类型：** 新规律（研究诚实性 / 多变体回测报告）

**内容：** 多变体对比报告里,一个变体若**空截面/缺因子数据**(如 A股 质量因子在 fundamentals 稀薄时选不出股)→ 退化为满仓现金、CAGR/Sharpe/换手全 0、never traded。自跑对抗审查指出：报告若把这个干净的 **0.00%** 当真实结果展示(尤其它是 headline 驱动图表+payload metrics),**研究判定被悄悄破坏**——分不清「故意持现金」vs「数据缺失没测到」。**规律**：研究报告的过拟合/红旗体系除了「样本内≠样本外 winner / 夏普离谱 / 全变体无差异」,**必须含 no_activity 红旗**(`rebalance_count==0`/换手 0+曲线平 → 标"never traded,0.00% 非真实结果",命中 headline 时尤其响亮)+**同子族内 toggle 失效红旗**(如同因子的 N 个退出变体结果字节相同 = 退出规则从未生效,全局 spread 测试在两族发散时会漏掉)。同族于「真值=不得 done / 0-result 不判 non-blocking」(evaluator §29/§25)。

**建议写入：** `framework/harness/generator.md` 或 `evaluator.md`（多变体研究报告红旗须含 no_activity 退化 + 同族 toggle 失效；0.00% 非真实结果）。

**状态：** ✅ 已沉淀 v0.9.48（generator.md §29；用户 2026-06-18 批 B066 done 收尾）

<!-- 2026-06-18: v0.9.48 沉淀完成（B066 F002/F003 done 收尾，用户批）：2 条 B066 自评 adversarial review 产 → generator.md §28（回测引擎停牌 ffill+NaN 安全读价禁 or 0.0+缺价回归测试）+ §29（多变体研究报告退化空仓必须红旗:no_activity+同族 toggle 失效,0.00% 非真实结果）。归档 framework/archive/proposed-learnings-archive-v0.9.48.md。CHANGELOG v0.9.48。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.48 后）：无。 -->

<!-- 当前活动候选（v0.9.47 后）：B066 2 条（generator）——①回测引擎停牌/缺价 ffill+NaN 安全读价禁 `or 0.0`(NaN 真值)+缺价回归测试(对抗审查 2 HIGH)；②多变体研究报告须 no_activity 退化红旗+同族 toggle 失效红旗(勿静默 0.00%)。另含 2 条设计模式待评：镜像新市场写专属引擎保 US 零回归 by construction(F001/F002 construction+costs 不改 us)；standalone 研究策略 registry 模式(入 list_strategies 但排除 sleeve_strategies via STANDALONE_RESEARCH_STRATEGY_IDS 避 phantom sleeve/paper)。下批 done 阶段提请用户裁定。 -->

## [2026-06-21] Claude CLI — 来源：B071 F003 — golden 真数据暴露 us_quality raw-open/adj-close 混用 bug（合成 fixture adj==close 系统性掩盖）

**类型：** 新坑（backtest 引擎 / 真实数据复权）+ 验证本批 golden 使命

**内容：** B071 建 golden 真数据 fixture 注入 us_quality 回测，**首跑即抓到真实 bug**：`engine.py:307` 用**未复权 `open`** 买股数，`:308` 用**复权 `adj_close`** 估值。真实数据 close/adj_close 因累计拆股+分红回调差 ~40x（NVDA close 751 vs adj_close 18.7）→ 每期持仓系统性错配 → golden 上 us_quality 假亏 **-99.4%**（ending 557/起始 10 万）。**关键规律**：合成 fixture 的 `adj_close == close`（B025 us_quality fixture 实测全 86790 行差异=0）→ raw-open/adj-close 混用在合成数据上是**数学 no-op**，**系统性掩盖**此 bug 类；只有真实数据（adj≠close）才暴露。这与 §28（停牌 ffill 被合成每格有价掩盖）**同主题**：合成回测数据掩盖真实数据行为 bug，golden 真数据是结构性解。**修复**（用户 2026-06-21 授权本批内修）：`_wide_open` 改用复权 open=`open×adj_close/close`，执行+估值同基准；合成 adj==close 处 adj_open=open bit-identical 向后兼容（18 现有测试全过），golden 上 us_quality 回到 -26.7%（2022 熊市合理）。golden 回归测试永久守（tests/unit/test_b071_golden_deterministic_backtests.py）。**注意：此 bug 也影响生产 VM 上 us_quality 真数据回测**（读同样 raw-open/adj-close unified 数据）。

**建议写入：** `framework/harness/generator.md`（§28 同节扩：回测引擎真实数据复权——执行价与估值价须同复权基准；合成 fixture adj==close 系统性掩盖 raw/adj 混用，golden 真数据是结构解）。

**状态：** ✅ 已沉淀 v0.9.49（generator.md §30；用户 2026-06-21 批 B071 done 收尾）

## [2026-06-21] Claude CLI — 来源：B071 F003 — records-based 引擎 raw-close 估值 + adj-close 信号的「持有拆股名穿越拆股」轻微失真（非阻断，待 Planner 评）

**类型：** 新坑候选（backtest 引擎 / 真实数据复权 — 轻微，非阻断）

**内容：** 同源排查发现 records-based 引擎（monthly.py / risk_parity.py）执行用**未复权 open**、估值用**未复权 close**（`:139/:146`、`:149/:154`，内部一致），但信号 momentum 用 **adj_close**（`global_etf_momentum.py:165+`）。后果：**持有一个拆股个股穿越其拆股月**时，raw open(拆股前)→raw close(拆股后)显示假期亏（如 AMZN 2022-06 20:1 拆股）。golden 上 master/momentum/risk_parity 结果合理（±22%，ETF 为主、个股拆股月恰未持有），**故本批不阻断**。用户 2026-06-21 裁定本批只修 us_quality（option B，非 option C），此项入后台队列待 Planner 评估是否值得统一为「全引擎执行+估值+信号同复权基准」。

**建议写入：** 待 Planner 裁定（可能并入上一条 generator.md 复权规则，或单列 records 引擎 raw-close 估值修正 feature）。

**状态：** ✅ 已沉淀 v0.9.49（并入 generator.md §30.1 作同族潜伏实例=已知非阻断限制;用户 2026-06-21 批 B071 done 收尾,本批不修)

<!-- 2026-06-21: B071 F003 新增 2 条活动候选（golden 真数据暴露复权 bug 类）：①us_quality raw-open/adj-close 混用(本批已修+golden 回归守)+合成 adj==close 系统性掩盖规律；②records 引擎 raw-close 估值轻微失真(用户裁本批不修,待 Planner)。下批 done 阶段提请用户裁定沉淀 generator.md。 -->

## [2026-06-21] Claude CLI — 来源：B071 F004 — 验收即代码常态化约定，建议入 role-context

**类型：** 模板修订 / 流程约定（角色规范）

**内容：** B071 建 `tests/acceptance/` 永久不变量回归层（验收即代码）。约定：**每批 Generator/独立 agent 把本批新颖 L2 真实数据检查写成 acceptance 断言**（用 golden 跑），使一次性 Codex 真机验收沉淀为永久 CI 回归；不削弱铁律 4 独立评审——因断言由写码方写存同向错盲点，故独立评审面积缩到「新颖/模糊」判断，机械复发不变量由 CI 绿 by construction + F005 mutation-check 对冲（故意改坏不变量→对应 acceptance 必须红）。已记 `docs/dev/workbench-testing-strategy.md`「Acceptance tier」节。**建议**：Planner 把此约定正式写入 `role-context/generator.md`（+ evaluator.md：verifying 跳 L1 复跑、只审新颖/模糊残留）。

**建议写入：** `.auto-memory/role-context/generator.md` + `evaluator.md`（验收即代码常态化 + evaluator 面积缩到新颖/模糊；Planner 统一制定 role-context）。

**状态：** ✅ 已沉淀 v0.9.49（generator.md §31 + evaluator.md §30 + role-context/generator.md + role-context/evaluator.md;用户 2026-06-21 批 B071 done 收尾）

<!-- 2026-06-21: v0.9.49 沉淀完成（B071 done 收尾,用户批）：3 条→①回测复权口径一致(raw-open 买/adj-close 估值混用=bug,合成 adj==close 系统性掩盖)generator.md §30+②records 引擎轻微失真折入 §30.1 已知非阻断限制;③验收即代码常态化+evaluator verifying 跳 L1=generator.md §31+evaluator.md §30+role-context 两文件。归档 framework/archive/proposed-learnings-archive-v0.9.49.md。CHANGELOG v0.9.49。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.49 后）：无。 -->

## [2026-06-22] Claude CLI — 来源：B074 F002 实现(cn_attack A股 模拟盘建仓 hotfix)

**类型：** 新坑 / 规律

**内容：** 「target 含字面现金 sentinel(CASH)行 → pure paper engine 当作无 mark 的 skipped target → build_complete 永 False」是 §17.1/B058『目标无 mark→搁浅现金』family 的**隐形变体**。planner VM 诊断只焊死了 A股 价缺 mark(根因#1),漏了根因#2:cn_attack precompute 在 cash_weight>0 时追加一行 CASH(weight>0、无价),compute_rebalance 把它计入 skipped_symbols,_apply_rebalance `fully_built = traded and not skipped` 因 CASH 永为 False——即便 A股 价同步到位也建不了仓。Master/regime 没事是因为它们的现金用实 ETF(SGOV)有 mark,不写字面 CASH。教训:**诊断 paper 搁浅现金类 bug 时,必须同时核对(a)目标证券 mark 是否齐 + (b)目标里是否有无 mark 的 sentinel/cash 伪符号被 engine 误判 skipped**。修法:paper/targets.load_strategy_targets 剥离 cash sentinel(只影响发布字面 CASH 的策略,零回归),target_key 保留全目标指纹。validate 用 compute_rebalance 直接实跑(含/剥 CASH 对照)最快锁死。另:spec 的『建仓成功=cash≈0』模板对持现金缓冲的策略(cn_attack)不准,应为 cash≈buffer。

**建议写入：** `framework/harness/generator.md`（§ paper/建仓诊断 family：搁浅现金双查 mark+sentinel）/ `framework/harness/planner.md`（根因诊断:paper build 失败需查 sentinel 行,勿只查证券 mark）

**状态：** ✅ 已沉淀 v0.9.50（generator.md §32 + planner.md §根因诊断;用户 2026-06-22 批 B074 done 收尾）

<!-- 2026-06-22: v0.9.50 沉淀完成（B074 done 收尾,用户批）：1 条 paper 搁浅现金诊断 family(双查证券 mark+cash sentinel)→generator.md §32+planner.md §根因诊断。归档 framework/archive/proposed-learnings-archive-v0.9.50.md。CHANGELOG v0.9.50。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.50 后）：无。 -->

## [2026-06-22] Claude CLI — 来源：B075 F001+F002 实现(A股 宽 universe 接生产)

**类型：** 新坑 / 规律 / 流程约定（3 条）

**内容：**
1. **【VM 执行坑，refines environment.md】** 在 VM 跑 `/tmp/*.py` 用部署 venv 时,`sys.path[0]=/tmp`,而 `/opt/workbench/.venv` site-packages 里 `workbench_api` 是 stale(缺 data_refresh 等子包)→ `import workbench_api.data_refresh` 报 ModuleNotFoundError,即便已 `cd /srv/workbench/current/backend`(cwd 不进 sys.path[0])。**修法:`PYTHONPATH=/srv/workbench/current/backend` 前置**让源树覆盖 stale site-packages。environment.md 现有『cd 进 backend 再 import-check』对 `-m`/cwd-import 有效,对 `/tmp` 脚本无效——补这一行。
2. **【可行性探针即代码路径验证】** B075 §23 VM 探针复用**真生产 loader**(discover_ashare_superset/CnHkPricesLoader/CnMarketCapLoader/CnFundamentalsLoader),非合成→探针同时验证 ungate 代码路径真能在 VM 跑通(sina 发现 1501/日刷 100% 成功)。规律:feasibility-first 探针应调真生产 API,既测可行性又测代码路径(对比 b070_feasibility_probe 用裸 baostock=只测数据源)。
3. **【宽 universe partial-failure exit-code 容忍】** 大宇宙(~1500)逐只刷必有尾部失败(退市/停牌),旧 `main()` `errors>0→exit 1` 会让日 timer 天天假阳报红。修法:宽块错误单列计数(cn_universe_price_errors/cn_fundamental_errors,同时进 errors 总数=单一 error 契约)+`resolve_exit_decision`= core(US/CN_HK)错误严格 + 宽块按 rate floor(≤20%)容忍,真停摆(host down→大批失败)才红。是『partial-failure 优雅不炸整轮』的 exit-code 层落地,可复用于任何宽集逐只刷 job。

**建议写入：** `.auto-memory/environment.md`(§ VM /tmp 脚本 PYTHONPATH) / `framework/harness/generator.md`(§宽集逐只刷 partial-failure exit-code 容忍 + 可行性探针复用真 loader)

**状态：** ✅ 已沉淀 v0.9.51（environment.md + generator.md §33/§34;用户 2026-06-23 批 B075 done 收尾）

<!-- 2026-06-23: v0.9.51 沉淀完成（B075 done 收尾,用户批）：3 条→environment.md(VM /tmp PYTHONPATH)+generator.md §33(探针复用真 loader)+§34(宽集 partial-failure exit-code 容忍)。归档 framework/archive/proposed-learnings-archive-v0.9.51.md。CHANGELOG v0.9.51。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.51 后）：无。 -->

## [2026-06-23] Claude CLI — 来源：B076 F001 cn_attack size-tilt 去偏回测

**类型：** 新坑（验收范式）/ 新规律（数据补法）/ 新坑（verdict 规则）（3 条同源）

**内容：**
1. **【去偏 size/估值因子补数据法，refines B070】** 去偏 PIT 回测(含退市名)若要加市值/估值类因子,`stock_value_em`(eastmoney) 只覆盖**当前上市**名 → 退市名缺市值 → 因子静默丢名=重引入幸存者偏差。**修法:用 baostock k-data 的 `turn`(换手率%)反推流通市值** `circ_mv = close_raw × volume × 100 / turn`(adjustflag=3 未复权;turn=volume/流通股本×100)。baostock 对所有有 k-data 的名(含退市)都给 turn → 覆盖率 100%(B076: 1310/1310)。通用于任何需退市名历史市值/估值的去偏研究。
2. **【策略改动 verdict 的 OOS-窗口诚实坑，refines B069/B070 OOS-caveat】** walk-forward OOS 指标当 verdict 的 risk gate 时,若 OOS 窗口恰系统性偏向被测因子(B076: 2024Q4『924』小盘反弹 favor size-tilt),OOS 会被**窗口美化** → 误判 GO(B076 首版规则只看 OOS Sharpe,strong 档 0.931 vs 0.930 险平→假 GO,而全样本 Sharpe 每档恶化 0.56→0.42)。**修法:risk gate 用全样本(period-wide)指标 + OOS 双门禁,不让窗口幸运的 OOS 平局 override 全样本恶化。** 是 OOS-caveat 在 verdict-rule 层的落地。
3. **【策略改动验收双 cut 范式】** 同一策略改动在 survivor 宇宙=GO、去偏宇宙=NO-GO 的对照(B076: survivor B068 quality_momentum Sharpe 1.00→1.27 vs 去偏 B070 pure_momentum 0.56→0.42),是『回测必须去偏』最强铁证 + verdict-gating 价值实例。可作未来策略-改动批次标准双 cut:primary 去偏 gating + secondary survivor 仅方向性(显式标注 survivor GO 不足为凭、NO-GO 更具说服力)。

**建议写入：** `framework/harness/generator.md`（§去偏 size/估值因子补数据法 + §策略改动双 cut 验收范式）/ `framework/harness/planner.md`（§ verdict risk gate 用全样本+OOS 双门禁防 OOS-窗口美化，扩 B068-B070 verdict-gated 范式）

**状态：** ✅ 已沉淀 v0.9.52（generator.md §35 + planner.md §策略-改动 verdict 设计;用户 2026-06-25 批 B076 done 收尾）

<!-- 2026-06-25: v0.9.52 沉淀完成（B076 done 收尾,用户批）：3 条→generator.md §35(baostock turn 补数据 + survivor/去偏双 cut)+planner.md §策略-改动 verdict 设计(全样本+OOS 双门禁 + 双 cut)。归档 framework/archive/proposed-learnings-archive-v0.9.52.md。CHANGELOG v0.9.52。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.52 后）：无。 -->

<!-- 当前活动候选（v0.9.51 后）：B076 3 条（去偏因子补数据 baostock turn / verdict OOS-窗口诚实坑 / 策略改动双 cut 范式），待 done 阶段 Planner 提交用户。 -->

## [2026-06-25] Claude CLI — 来源：B077 F001/F002 聪明钱数据可行性 + 预存 date-bomb

**类型：** 新坑（test-hygiene）/ 新规律（§23 measured-not-assumed 审查）/ 新规律（覆盖-门控裁定档）（3 条）

**内容：**
1. **【date-bomb 坑：生产用真实时钟 + 固定 fixture = 时间相关 CI flake】** 生产代码用真实 `datetime.now()` 算"近 N 日"窗口（如 provider `get_quote` 的 `[today-N, today]`），而单测用**固定假帧日期** → fixture 日期随日历推进**滑出窗口** → 某个 commit 还绿、N 天后**与代码无关地变红**（B077: cn/hk/yfinance get_quote，HS test 2026-06-22 绿、06-25 红）。**修法：生产时钟可注入**（加可选 `today` 参数，default `now()`，ABC 不动→更宽 override LSP 安全），单测 pin `today=_TODAY`→确定性。诊断要点：CI 红但 diff 与红测试模块无关 + 上个 commit 绿 → 先查日期相关 fixture，勿误判为本次改动。
2. **【§23 measured-not-assumed 要贯彻到每个派生字段，非仅数据本身】** 可行性探针即便数据是 VM 实测的，若 data-reality 的**派生标签/裁定字段被 hardcode**（B077 F001: coverage="full_market" 常量 / lag_days=0 写死 / can_support_backtest=True 不门控），仍违反 §23。20-agent review 抓到 15 处此类。**规约：探针每个 reality 字段(coverage/lag/depth/backtest-supportability)必须从实测派生**(lag 由真实日期算、coverage 由实测 snapshot 反映、backtest 由实测深度门控)；review 应设专门 lens 查"标签是否真实测而非假设"。
3. **【first-look IC 覆盖-门控裁定档 INCONCLUSIVE_COVERAGE_LIMITED】** 去偏宇宙做信号探查时，若信号总体大部分落在去偏宇宙外（B077: 龙虎榜机构席位 80.8% 事件是小盘异动，B070 流动宇宙小盘天花板未覆盖）→ first-look IC 只测到子集，据此断"无信号"是误劝退。**修法：裁定加第三档**——faint 一致方向(|IC|≥0.015,多 horizon 同号) + 覆盖率<50% → INCONCLUSIVE_COVERAGE_LIMITED(既不 GO 也不直接劝退,决定性检验=补覆盖重跑)。配套：分组均值须查**单调性**(B077 驼峰:极端净买均值回归,正 top-bottom 非单调梯度)，勿据 top-bottom 同号即称"方向真实"。

**建议写入：** `framework/harness/generator.md`（§探针 measured-not-assumed 派生字段铁律 + §first-look 覆盖-门控裁定档 + 分组单调性查）/ `framework/harness/evaluator.md` 或新 test-hygiene 节（§date-bomb：真实时钟+固定 fixture 坑 + 时钟注入修法 + CI-红诊断要点）。

**状态：** ✅ 已沉淀 v0.9.53（generator.md §36/§37 + evaluator.md §31;用户 2026-06-26 批 B078 done 收尾合并处理）

## [2026-06-26] Claude CLI — 来源：B078 F001/F002 A股 data-refresh 卡死修复(生产 hotfix)

**类型：** 新坑(systemd oneshot 默认无超时)/ 新规律(宽集刷 job 防挂死要包裹 ALL 网络调用含 bulk discovery)/ 新规律(round-trip 成本预留)/ 新规律(静默冻结守门)(4 条)

**内容：**
1. **【systemd Type=oneshot 默认 TimeoutStartSec=infinity = 永 activating 卡死根因】** oneshot service 的 `TimeoutStartSec` **默认禁用(infinity)**，与普通 service(默认 90s)不同。一旦 ExecStart 内有无超时的阻塞网络读 → 服务永 "activating"、timer Trigger=n/a、堵所有后续刷新(B078: data-refresh 卡 3 天冻 A股)。**规约：每个 oneshot 数据刷新 service 必须显式设 `TimeoutStartSec=<正常耗时×~2.5>`(watchdog 兜底)；这是 §34「宽集逐只刷」的 OS 层补充。** 诊断卡死先看 `systemctl show -p ActiveState,SubState,ActiveEnterTimestamp`，activating 超 X 时即 stuck。
2. **【宽集刷防挂死要包裹 ALL 真网络调用，bulk discovery 最易漏】** per-call 超时只包"逐只"fetch 不够：**bulk 发现/快照调用(`stock_zh_a_spot_em`/`stock_zh_a_spot`)常在逐只循环 BEFORE 跑，且无超时**——挂死则 0 数据写入、命门再冻(对抗式自审抓到, spec §1 清单只列逐只漏了 bulk)。**规约：宽集 job 的超时清单要含 (a) 逐只 fetch (b) bulk discovery (c) benchmark/单次 index 等所有真网络调用；用 daemon-线程+join(timeout) 原语(跨平台/可嵌套, leak 线程 daemon 不阻塞退出), 0/None=inline 保证既有调用零回归。** 写完用 grep 核 "无 timeout 的网络调用" 残留。
3. **【paper 调仓成本要预留 round-trip(买+卖), 单边预留满仓必透支】** `investable=equity*(1-cost_rate)` 只够付**买入**腿成本; 调仓在 gross=买+卖 全程收费, 高换手(全换)按卖出腿透支 ≈ held*cost_rate(B078: B074 剥 CASH buffer 满仓后 cash -102/-103)。**修法：investable 再减 `held_marked_value*cost_rate`(卖出腿上界=持仓市值)→ 任意换手 cash≥0(证 new_cash≥r²(equity+held)); from-cash 建仓 held=0 → 公式不变 → 建仓零回归(仅高换手调仓变)。** 通用于任何"满仓+成本"的再平衡引擎。
4. **【静默冻结守门：数据 as_of 业务日新鲜度 + service stuck-activating 双断言】** 数据管道挂死最毒的是**无人报错**(B078 冻 4 天 precompute 每天重吐同快照、paper 照"跟"冻结目标)。**规约：把"快照 as_of 业务日年龄 ≤ N" + "service 不 stuck-activating > X 时"做成纯函数 + acceptance 守门(有牙齿: 故意造陈旧→红); 业务日计数免疫周末(长假残留 WARNING 可接受); teeth 测必须 pin SHIPPED 默认阈在真实冻幅(否则默认回归静默重开 bug)。**

**建议写入：** `framework/harness/generator.md`(§宽集刷防挂死 per-call 超时含 bulk discovery + daemon-线程原语 / §paper round-trip 成本预留 / §静默冻结新鲜度守门 teeth-pin-默认) / `framework/harness/evaluator.md`(§systemd oneshot 无超时卡死诊断 systemctl show + L2 部署须杀卡死 PID 旧进程不自退)。

**状态：** ✅ 已沉淀 v0.9.54（generator.md §38/§39/§40 + evaluator.md §32;用户 2026-06-26 批 B078 done 收尾）

<!-- 2026-06-26: v0.9.53+v0.9.54 沉淀完成（B077+B078 合并 done 收尾,用户批）：B077 3 条→generator.md §36/§37+evaluator.md §31(v0.9.53);B078 4 条→generator.md §38/§39/§40+evaluator.md §32(v0.9.54)。归档 archive v0.9.53/v0.9.54。CHANGELOG 双版。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.54 后）：无。 -->

## [2026-07-03] Claude CLI — 来源：B080 F002 Family 2（signal_scores 落库需编辑 trade/）

**类型：** 新坑 / 模板修订

**内容：** F002 的「原始 score 落库」把 cn_attack 复合因子分从 `CnSignalResult.factor_contributions_dict()` 提到 `CnAttackLiveTarget` 数据类上，这是一处 `trade/` 编辑——因而触发 spec 未列的额外门禁：`mypy trade`（Python CI）+ 根 `ruff check .` + 根 pytest（cn_attack live/b075/b076 acceptance）+ **改 trade/ 后必须 `.venv/bin/python -m pip install ../..` 重装 trade 到 backend venv**（否则 backend 测试导入的是 stale 已装副本，报 `no attribute signal_scores`）。spec 的「gates 同 F001」漏了这些。**建议：planner 起草 spec 时，凡涉及从 trade/ 源对象取新字段的 feature，acceptance 的 Gates 段应显式列 `mypy trade` + 重装 trade + 根 pytest 子集；generator 规约补一条「编辑 trade/ 后先 pip install ../.. 重装」提醒。**

**建议写入：** `framework/harness/planner.md`（spec Gates 段模板：trade/-edit feature 加门禁）+ `framework/harness/generator.md`（trade/ 编辑后重装 backend venv 的坑，或 environment.md）

**状态：** ✅ 已沉淀 v0.9.55（generator.md §41(a) trade/-edit 门禁 family + planner.md §种子数据落地路径 gates 提醒；与 B081 F001 合并一族）

## [2026-07-03] Claude CLI — 来源：B080 F004（api.ts 新 required 字段致 Frontend CI 瞬红）

**类型：** 新坑

**内容：** 给 pydantic response schema 加**带默认值**的字段（如 `PaperSummary.benchmark_symbol="SPY"` / `first_day_caveat=False`）时，`openapi-typescript` 生成的 TS 类型仍标为 **required**（响应恒含该字段 → 无 `?`）。因此所有用字面量构造该类型的前端 fixture（`tests/unit/**/paper.spec.tsx`、`PaperPage.spec.tsx`）会立即 `tsc` 失败。若把 api.ts regen（后端 commit）与 fixture 修复（前端 commit）**分两个 commit**（api.ts 先落），中间那个 commit 的 Frontend CI **必红**（本批 dd9f703 红 → 46ba83b 绿，planner 留了协调注记#3）。**建议：** 后端加 schema 字段并 regen api.ts 后，**立即** `grep` 该 schema 名的前端 fixture，同一 commit（或前端先）补齐新字段，避免 main 上出现瞬时红 Frontend CI。

**建议写入：** `framework/harness/generator.md`（api.ts 契约规则：schema 加字段 → 同步前端 fixture）

**状态：** ✅ 已沉淀 v0.9.55（generator.md §42）

## [2026-07-04] Claude CLI — 来源：B080 F005（bootstrap-only seed 不入部署链 = 生产静默缺数据）

**类型：** 新坑 / 铁律补充

**内容：** `workbench-bootstrap` CLI 的幂等 seed（`_import_trials` 27 trials / curated symbol_names）**只手动跑**，不在 `deploy.sh`（只 `alembic upgrade`）/ `workbench-deploy.yml`。→ 部署后生产**从不落库**，且无调度器自愈（不同于有 timer 的 `monitoring_metric` 周 job / `reverify` 季 job）。B080 F001 `trial_registry=0` + B079 curated `symbol_name=0` **同源**。对比：OOS 红卡（迁移 0028）/ paper currency（0032）走 **data-migration 随 alembic 自动落地**就没这问题。本批 F005 修复即把 trial 回填改成 data-migration 0033。**规则：** 凡「部署后必须存在的种子数据」，必须走 **alembic data-migration**（随部署自动落地）或**显式接入部署链**，**不能只放 bootstrap CLI**——否则生产静默缺数据、无告警、不自愈。planner 起草含种子数据的 spec 时，acceptance 必须写明「落地路径 = 自动部署（migration/部署链），非手动 CLI」；generator 加种子数据时同此。**遗留：** curated symbol_name 生产=0 仍未修（B079 已 done + akshare_spot 日刷 5203 行覆盖显示，非阻断）——可 backlog 一并治本（bootstrap 接部署链）。

**建议写入：** `framework/harness/generator.md` §部署种子数据规则 + `framework/harness/planner.md` spec acceptance（种子数据落地路径）

**状态：** ✅ 已沉淀 v0.9.55（generator.md §43 + planner.md §种子数据落地路径）

## [2026-07-04] Claude CLI — 来源：B081 F001（改 backtest 默认口径的 trade/ edit 须跑全 root pytest）

**类型：** 新坑 / 铁律补充

**内容：** 改变 backtest **默认口径**的 `trade/` edit（config 默认值翻转，如 `lot_rounding: bool = True`）不能只跑 cn_attack 测试子集就 push——full root pytest 里有其他测试消费默认 backtest（comparison / reporting / **overfitting detector**）。本批 lot_rounding commit `e94955f` 我只本地跑了 cn_attack 子集（65 测绿），push 后 Python CI 在 `test_implausible_sharpe_flagged` 红：round-lot cash-drag 把小合成账本的 Sharpe 压到 implausible 阈值以下，检测器不再触发。修复=`build_cn_attack_comparison` 透传 `base.lot_rounding`（之前 per-variant cfg 丢弃它）+ 该测 pin 旧口径。**规则：** 改 backtest 默认口径/默认 config 值的 `trade/` edit，push 前必须本地跑 **full root pytest**（或至少 grep 所有 `run_cn_attack_backtest` / `build_cn_attack_comparison` 消费点的测试文件全跑）。子集绿 ≠ 全绿。**另一坑（同批）：** A/B comparison / 多变体构造器（`build_cn_attack_comparison` per-variant cfg）新增 config switch 时容易漏透传 `base.<switch>` → 比较静默忽略 caller 的口径；加 engine switch 时须同步透传所有多变体构造点。

**建议写入：** `framework/harness/generator.md` §trade/-edit 门禁（默认口径变更 → full root pytest + 多变体构造器透传 switch）

**状态：** ✅ 已沉淀 v0.9.55（generator.md §41(b)；与 B080 F002 合并一族）

## [2026-07-04] Claude CLI — 来源：B081 F002/F003（执行限制的 loop-level freeze/restore 模式）

**类型：** 新规律 / 模板

**内容：** 回测引擎里"某名当日不可交易"（停牌禁买卖 / 涨停禁买 / 跌停禁卖 / 退市前停牌窗口）的实现，**不要**在 `_execute_open` 内部改目标权重（会撞上 cost-reservation 缩股 churn + 归一化难题，同 F001#3 band×partial 三次失败）。**干净方案 = loop-level freeze/restore：** 执行前把受限持仓名（exact shares + entry/peak）**冻结取出**并从 target 剔除 → 非受限账本在剩余 tradeable pool 内正常 rebalance（full/partial/lot_rounding 全不动）→ 执行后把冻结名**原样放回**。equity 守恒（冻结价值在放回的 shares 里）。F002 停牌 + F003 涨跌停复用同一 `restricted_today` 集合（∪ 合并），一处逻辑覆盖两类限制。开关 off → 集合空 → bit 级旧口径。**规律：** 凡"部分持仓本轮不可动、其余照常调仓"的需求，shares-preserving freeze/restore 比"重定位到 current weight"更干净（后者被 cost 预留缩股）。

**建议写入：** `framework/harness/generator.md` §回测引擎（执行限制 = loop-level freeze/restore，勿在 rebalance 内改权重）

**状态：** ✅ 已沉淀 v0.9.55（generator.md §44）

## [2026-07-04] Claude CLI — 来源：B081 F004（A/B 真机重跑：分数股假象 + 慢跑抗 kill 基建）

**类型：** 新规律 / 新坑

**内容：** 两条。**(1) 回测保真度结论（值得进 framework 经验库）：** A股回测**不建手数取整（100 股/手）= 分数股假象，显著虚高收益**。B081 A/B 实测（B070 去偏 PIT，pure_momentum）：旧口径（分数股）OOS +28.4%，加真实手数取整后 **OOS 转负 -14.7%**——*ST 遍地的宽 PIT 里大量低价名买不起 1 手→被 skip→现金拖累 + 6x 换手。**边际大半是分数股假象**。反之 F002 停牌/退市在此策略 = **no-op**（流动动量票不停不退）——"最重高估源"对*本*策略零影响，但对持*ST/低流动名的策略才咬。教训：宣称某回测有 edge 前，先跑"引擎修真 A/B"（手数/停牌/退市/涨跌停各开关），确认 edge 非引擎理想化假象。**(2) 慢真机跑抗 background-kill 基建：** 8 组×~5min 全宇宙回测（236M 数据）在本 harness 下 background task ~20min 必被 kill，且每次重跑 CSV load ~5min 吃光窗口→永不前进。**方案：** runner 做 **resumable**（每组落 JSON，重跑跳已算）+ **pickle 缓存 prices**（`to_pickle`/`read_pickle`，pyarrow 缺则用 pickle；reload 5min→30s）。之后每次重跑续算 1-2 组，数轮收敛。缓存文件 gitignore（161MB）。

**建议写入：** `framework/README.md` §经验教训（回测保真度：手数取整 A/B 揭分数股假象）+ `framework/harness/generator.md` §慢真机跑（resumable + pickle 缓存抗 kill）

**状态：** ✅ 已沉淀 v0.9.55（README.md §经验教训「回测保真度：引擎修真 A/B 必须配本金扫描」+ generator.md §45）。**★采用 F005 审计更正版**——负数=10 万本金容量下限（lot@10M 保留 99% edge），非分数股假象；沉淀文案已按更正为准（原「分数股假象」叙事未固化进 framework）。

**★F005 r1 审计更正（2026-07-04，必读）：** 条目 (1) 的「分数股假象/边际大半是假象」结论**已被独立验收的本金扫描证伪**——负数是 **10 万本金容量下限**（25 只等权中约 9 只一手买不起），lot@1M OOS +23.5%、lot@10M +28.2%（保留 99% edge）。**修正后的正确教训：** ①引擎修真 A/B 的「手数取整」组必须**同时做本金扫描**（100k/1M/10M），否则会把容量下限误读为策略失效；②宣称「某修复揭示假象」前，先问该效应是否随本金/规模消失；③「宣称 edge 前先跑引擎修真 A/B」的元教训仍然成立，且本次 fixing 轮补充了第四条：**A/B 结论本身也要过独立数字审计**（F005 抓住了 F004 的误读）。条目 (2) 抗 kill 基建不受影响。沉淀时请以本更正为准。

## [2026-07-05] Claude CLI — 来源：B083 F002（前端 flaky 测 red main / backend-only commit 诊断）

**类型：** 新坑 / 诊断规律

**内容：** B083 F002 是**纯 backend commit**（trial 登记：trial_backfill_b083 + migration 0038 + bootstrap + test），Backend CI 绿，但 **Frontend CI 红**——`tests/unit/risk-banner.spec.tsx > 红 risk banner: keeping defensive posts defensive=true`（expected defensive:true got false）。**诊断规律：backend-only commit 让 frontend UI 测红 = 几乎必为 flaky**（backend 改动物理上不可能影响 frontend vitest fixture 逻辑）。实证：本机 `npx vitest run risk-banner -t "keeping defensive"` 隔离跑 **3×全绿**，CI 全套跑偶红 → **测隔离/test-order 共享状态问题**（非本 commit 引入；前序 commit CI 全绿）。**处置（更正）：** 先 `gh run rerun --failed`；本次**重跑仍红**——非随机 flake 而是 **CI-环境一致的 async race**（本机隔离/全套都绿, CI runner 负载下一致触发）。根因实证: risk-banner 测点击 Generate 前只等 mode-CARD 渲染, 未等 red→defensive 的 post-render `useEffect` **settle**, CI 时序下点击抢跑 effect→POST `{defensive:false}`。**真修**=test 加 `await waitFor(defensive radio checked)` 等 flip settle 再点（组件不改, auto-flip 本身对, 测该等）。**规律修正: backend↔frontend 无关联仍先疑 flake+隔离复跑证伪; 但 rerun 若不清=非随机而是环境一致 race, 须真修(测等 async settle), 不可反复 rerun 赌绿。****建议 backlog `test-automation-infra` 一并治本**：risk-banner.spec.tsx 全套跑的 flake（隔离绿/全套偶红）需查 test 间共享状态（likely 某前序 test 泄漏 defensive-posture mock/store 未 reset）。**规律沉淀：** 判 CI 红是否本 commit 责任，先看「改动面 vs 红测面」物理关联——无关联(backend↔frontend)优先怀疑 flake，隔离本机复跑证伪，rerun 清；有关联才深查。

**建议写入：** `framework/harness/generator.md` §CI 红诊断（改动面 vs 红测面物理关联判 flake）+ backlog test-automation-infra（risk-banner flake 治本）

**状态：** ✅ 已沉淀 v0.9.55（evaluator.md §34，修正 §27——rerun 不清=环境一致 race 须真修）

## [2026-07-05] Claude CLI — 来源：B087+B090 验收方两次流程观察（planner 抢跑 done/开批）

**类型：** 新坑 / 模板修订（角色时序）

**内容：** 两例同款时序耦合：Planner 在 Evaluator 的 signoff 提交落地**之前**执行 done 收尾或开下一批（B087：done-phase 把 evaluator 未提交的写盘状态 sweep 进自己的 commit；B090：预设 PASS 开 B091 并重置 progress.json，消费掉 B090-done 瞬态）。两次均因裁定恰为 PASS 而无害，但**若裁定为 fixing 则状态机将不一致**（下批已开而上批实为未闭环）。规约建议：Planner 在 verifying/reverifying 期间不执行 done 收尾、不开下批；以「evaluator 的 signoff 报告文件 + 状态流转 commit 已在 origin/main」为唯一开批前置；等待期可做只读预研（预研 commit 注明"不动状态机"——现行做法保留）。

**建议写入：** `framework/harness/planner.md`（§done 收尾/开批前置：signoff 落地 gate）

**状态：** ✅ 已沉淀 v0.9.55（planner.md §done 收尾/开批前置 gate；与 B098 F002 写入序列化合并一节）

## [2026-07-06] Claude CLI — 来源：test-automation roadmap P5-F2（B098 done 阶段）

**类型：** 新规律（流程约定）

**内容：** P5-F2「固化独立对抗评审触发点」不是 generator 可构建的代码，而是评估流程约定——每批 done 前，独立 agent 只审「新颖/模糊」残留（机械部分已 CI 绿），守铁律#4。本 session 已事实上演示此模式：每个 Workflow 批次在 commit 前跑 2 个对抗验证子代理（generator-side QA），Codex 再做独立 F002/F003 验收（judgment 核）。B095/B097 正是对抗验证在 commit 前拦下真 bug（假阳/假红）。建议将「generator-side 对抗验证（pre-commit）+ 独立 evaluator 只审新颖/模糊（judgment 核）」固化为流程约定，并可让 evaluator 用 B098 的 gen_signoff_draft.py 填 signoff 机械 scaffold。

**建议写入：** `framework/harness/evaluator.md`（独立评审触发点约定）+ `framework/README.md` §经验教训（Workflow 对抗验证 pre-commit 拦 bug 的价值）

**状态：** ✅ 已确认（2026-07-06 用户同意）→ 已写入 `framework/harness/evaluator.md` §33（承接 §30，commit `c5694f7`）。test-automation P5-F2 落地完成。**v0.9.55 归档**（本次不重复写入，仅入 archive）。

## [2026-07-06] Claude CLI — 来源：B098 F002 并发写竞态致无效 JSON 进 main（铁律 #11 实例 + 已落实钩子）

**类型：** 新坑 / 铁律补充（含已落实的防御）

**内容：** 多 session 并发写同一状态 JSON 的严重后果实例：planner done-phase 写 progress.json 与 evaluator signoff 写 progress.json 并发，git 合并抓到 `session_notes.evaluator` 尾部断裂态 → commit f2bbb1c 短暂在 main tip 携带**不可解析的 progress.json**（铁律 #11 breach，与 MVP commit b44b789 缺 `}` 同族）。已被 4477e7d 自愈。**这正是铁律 #11 建议 pre-commit 钩子要防的。★已落实**：`scripts/check_state_json.py`（校验 progress/features/backlog，负测有牙）+ `scripts/pre-commit-hook.sh`（git-tracked 副本）+ 本机 `.git/hooks/pre-commit` 已装（拦无效 JSON 进 commit 实测通过）。**遗留待用户决策的更根本项**（evaluator 建议 2）：钩子只拦"无效 JSON"，拦不住"竞态覆盖"（A 覆盖 B 的有效但错误的写）——序列化 planner-done-phase 与 evaluator-signoff 的写入需要协调协议（如 done-phase 必须在 evaluator signoff 落地 origin/main 后才跑，与前条 [2026-07-05] signoff-gate learning 同族）。

**建议写入：** `harness-rules.md` §启动流程（clone 后 setup 步骤装钩子：`cp scripts/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x`）+ `framework/harness/planner.md`（done-phase 写入序列化 gate）。

**状态：** ✅ 已沉淀 v0.9.55（harness-rules.md §启动流程 clone 后装钩子 setup 步骤 + planner.md §done 收尾/开批前置 gate 写入序列化；钩子已本机落实 commit `2f79ae5`）

<!-- 2026-07-07: v0.9.55 沉淀完成（B080-B098 队列清扫,用户 2026-07-07「沉淀 learnings,全批准」）：9 条正式写入 + 1 条（P5-F2）先行已在 evaluator.md §33 仅归档。①B080 F002 + B081 F001 合并 → generator.md §41(a)(b)（trade/-edit 门禁 family,子集绿≠全绿）;②B080 F004 → generator.md §42（api.ts required 字段同 commit 补前端 fixture）;③B080 F005 → generator.md §43 + planner.md §种子数据落地路径（种子数据走 data-migration/部署链,勿只 bootstrap CLI）;④B081 F002/F003 → generator.md §44（执行限制 loop-level freeze/restore）;⑤B081 F004 → generator.md §45（慢真机跑 resumable+pickle 抗 kill）+ README §经验教训「回测保真度」（★F005 更正版:容量下限非分数股假象,lot@10M 保留 99% edge）;⑥B083 F002 → evaluator.md §34（改动面 vs 红测面物理关联判 flake,rerun 不清=race 须真修,修正 §27）;⑦B087+B090 + B098 F002 planner 部分合并 → planner.md §done 收尾/开批前置 gate（signoff 落地 + 写入序列化）;⑧B098 F002 → harness-rules.md §启动流程（clone 后装 pre-commit 钩子）;⑨P5-F2 已在 evaluator.md §33 仅归档。归档 framework/archive/proposed-learnings-archive-v0.9.55.md。CHANGELOG v0.9.55。**活跃候选队列=空。** -->

<!-- 当前活动候选（v0.9.55 后）：无。 -->

## [2026-07-20] Claude CLI — 来源：B109 F002 实测发现 Tushare 单次调用静默截断

**类型：** 新坑 / 铁律补充

**内容：** **「调用成功返回」不等于「拿到了全部」。** Tushare 单次 API 调用会静默截断（`income_vip` 恰好 9000 行 / `namechange` 恰好 10000 行），**不报错、不抛异常、不置任何标志位**——唯一线索是行数恰好是整数。★致命之处在于**截断非均匀**：2022FY 漏掉的 1093 行里 `update_flag=0` 占 18.7%、`flag=1` 仅 5.2%，即被砍掉的恰恰富集 vintage 记录，而那正是修订率/保留率指标的计算依据。后果：**B109 F001 已交付报告的核心数字全部作废**——分页重测后 2021FY 修订率 0.525%→1.325%（2.5 倍）、`flag=0` 保留率 69.4%→93.1%；未触顶的期次数字完全不变，反证偏差源就是截断。F001 的**设计裁定**（轻量两字段 resolver）未被推翻（它取决于可重建性而非修订率高低），但**测量数字**须重跑。与 B108 E01「被规则挡住不等于被验证过」同族：**凡分页接口，要么分页拉取，要么显式证明未触顶，不存在第三种可接受状态**。修复见 `scripts/research/ashare_pit/fetch.py`（短页才是最后一页 + 触顶守卫 + FetchReport 留痕）+ 审计报告 `docs/audits/B109-F002-tushare-silent-truncation-2026-07-20.md`。★次生教训：撤回失效常量时**留 `None` 而非留旧值**——一个已知偏低的数比留空更危险，下游会把它当已验证事实引用。

**建议写入：** `framework/README.md` §经验教训（外部数据源完整性不可假设）+ `framework/harness/generator.md`（分页接口拉取纪律 + 失效常量撤回方式）

**状态：** 待确认

## [2026-07-20] Claude CLI — 来源：B109 F003 fix_rounds 重复计数（★根因已由 evaluator 更正）

**类型：** 模板修订 / 分层加载的可发现性缺陷

**内容：** B109 实测：evaluator 在 verifying→fixing 时把 fix_rounds 0→1，Generator 在 fixing→reverifying 时又 1→2，实际只有一轮修复却记成两轮。

★**我最初把根因判为「`harness-rules.md` §状态流转未指明由谁加 → 规则真空」，这是错的**，已由 evaluator 更正并经我 git 核实：规则**早已存在**于 `framework/harness/generator.md:196`（「fixing 模式：…… status 改为 reverifying，fix_rounds +1」写在 **Generator** 的完成标准下），`framework/harness/evaluator.md:25` 反向印证（evaluator 见到 reverifying 时该字段「**已更新**」）。责任方是 evaluator 未按 `harness-rules.md` §第三步「按需查阅 framework/harness/」，不是双方。

★**真正值得沉淀的是分层加载的可发现性缺陷**：v0.9.28 把规则分成「短版必读（`.auto-memory/role-context/`）+ 长版按需（`framework/harness/`）」以省 context window，代价是**主文件 `harness-rules.md` 的状态流转表复述了「fix_rounds +1」却丢了「由谁加」这个限定**——读主文件的人会以为自己已经读完了这条规则，不会意识到需要去查长版。**分层的风险不在信息缺失，而在主文件给出「看起来完整」的半条规则。**

**建议：** (1) `harness-rules.md` §状态流转把递增方补进去（凡主文件复述深层规则，必须复述完整或显式标注「详见 framework/harness/X」）；(2) `scripts/check_state_json.py` 加校验：fix_rounds 变化仅允许发生在 status fixing→reverifying 的同一 commit 内——把口头规则变成有牙齿的门禁。

**建议写入：** `harness-rules.md` §状态流转 + `scripts/check_state_json.py`

**状态：** 待确认

## [2026-07-20] Codex(evaluator 代) — 来源：B109 F003 复验时自我更正「删除违禁路径」的建议

**类型：** 新规律（退役判据）

**内容：** F003 首轮建议「(b) 直接删除 `b076_fetch_pit_marketcap.py` 及其测试」，**复验时追 provenance 发现该建议是错的**：该脚本产出的 `data/research/b076/cn_size.csv` 正被**生产策略** `trade/strategies/cn_attack_momentum_quality/size.py` 与 B080 拥挤度监控读取（已 git 核实）。删除等于切断一份**生产在读 CSV 的 provenance**，反而抬高「未来有人重新手搓一个错版本」的风险。Generator 选的「保留本体 + ⛔弃用横幅 + 运行时 `DeprecationWarning` + **测试固化禁令**」才是正确解。

★**退役判据应是「让误用不可能悄悄发生」，不是「让代码消失」**：退役前必须先查消费者；存在合法消费者时，目标态就该是「警示但可用」而非删除。「可用」与「该用」是两件事。

★配套的验证手法值得沉淀：**变异测试验证弃用契约有牙齿**——注释掉 `warnings.warn` 后 4/7 测试 FAIL，证明禁令由测试守住而非注释里的君子协定；另须实证 `DeprecationWarning` 在**默认 filter** 下可见（库代码中它默认被隐藏，不能想当然）。

★**同类防误报**：`size.py` 用 `circ_mv` **不违禁令 #6**——#6 射程是 E/P 的**分母**（全公司归母利润须配总市值），而 size.py 是**规模因子排序量**（规模因子惯用流通/自由流通市值）。禁令有射程，跨射程套用会制造假缺陷。

**建议写入：** `framework/README.md` §经验教训（退役判据 + 禁令射程）+ `framework/harness/evaluator.md`（提删除建议前必须查消费者；变异测试验证契约）

**状态：** 待确认

## [2026-07-21] Claude CLI — 来源：B110 F004 裁定更正（用户裁 NO-GO，推翻 evaluator 的 INCONCLUSIVE）

**类型：** 新规律（裁定逻辑）×2 + 新坑（自欺形态复发）

**内容 1 — ★敏感性/口径条款「触发」≠「改变裁定」：**
B110 的 evaluator 见到冻结附录 D1（基准构成差 >1.0pp → INCONCLUSIVE）触发，就据此把
NO-GO 改判为 INCONCLUSIVE。但**它只验了触发条件，没验该歧义是否跨越判据边界**：主口径
`vs B-scored = +0.9606%` 与 `vs B-wide = −0.7619%`，**两端都 ≤1.0% 的 NO-GO 线** → D1 空转。
且 `B-scored < B-wide` 意味着交付的正号已是歧义带的**乐观端**，修正只会更差。
**规则：口径/敏感性条款触发后，必须机械展开该歧义的两端并验证是否跨越判据边界；
不跨越则条款空转，不得据此改档。**
配套的**不对称性自检**：把实测值换成刚好跨过对侧阈值的假想值，同一套规则会裁什么？
若两侧裁法不一致，说明条款被非对称使用了。

**内容 2 — ★判据为 OR 结构时，敏感性条款只能挑战它实际影响的那个析取项：**
spec §4 的 NO-GO = 「年化超额 ≤1.0% **或** 顶层组不是最优」。D6（退市 stub 带跨越 1.0% 线）
对**第一个**析取项的挑战是真实的，但 evaluator 把它的效力外溢到了整个析取式。
第二个析取项是组间比较（Q4 14.28% > Q5 12.75%），基准不进入、stub 翻不动——
**4 变体 × 2 基准的 8/8 单元格一致触发 NO-GO**。
**规则：推翻一个析取项不等于推翻析取式。**

**内容 3 — ★新坑：evaluator 把「自己漏读一条已存在的规则」记成「框架缺少该规则」。**
B110 冻结附录 **D8 逐字写着**「顶层组不是最优 → NO-GO **照字面执行（预注册锁死，不得改）**，
相邻五分位 SE ≈2.5%/年、Q5 输 Q4 0.1% 完全在噪声内，**不因此放宽判据**」——它精确预见了
「统计不显著」这一反驳并提前否决。而 signoff 全文 `D8` 仅在 `D1-D8` 区间写法中出现一次，
**从未作为规则被引用**，随后 soft-watch S1 把「未定义优先级」记为 medium 框架缺口。
**按原样沉淀会去补一条已经存在的规则，掩盖真实教训。**
建议：signoff 模板的裁定段增加「**已逐条核对的冻结条款清单**」，强制 evaluator 列出
它读过哪些 D 编号——漏读因此在报告结构上可见。

**内容 4 — ★★自欺形态复发：抽样池按构造排除了被检项。**
F004 声称「四分量 240/240 R2 对拍 MATCH，BREAK=0」，但抽样池是 `ep` 非空的行，
而 `ep` 非空 ⟺ TTM 可用 ⟺ R2 已全 MATCH（BREAK 会 fail-closed 掉 `ep`）。
**BREAK 样本按构造不可能被抽到**。实测：可达池随机 400 条 BREAK=0；被排除池随机 400 条
BREAK=78（与全量 7,949/35,152 = 22.6% 自洽）。
★**加重情节**：本批次自己的冻结附录 §4 逐字写明这是「与 B109 审计器『可裁定样本仅 16.7%
而一致率 100%』**同型**的自欺陷阱」，并把 R2 列为等价式失效后的「替代的真校验」——
**明令警惕的形态被原样搬到了替代校验上**。
**规则：任何「一致率/通过率」指标必须同时报告『分母是怎么筛出来的』，
并检查筛选条件是否与被检项逻辑相关。**
同批次另一实例：F004 的漏斗闭合断言 `(a−b)+(b−c)+(c−d)+d ≡ a` 是望远镜恒等式，
捏造数字也返回 True，`raise` 不可达——**恒真断言与同义反复抽样是同一类错误的两种表现**。

**内容 5 — ★「保守」一词在裁定档上被用反。**
signoff 两次称 INCONCLUSIVE 为「保守裁定」。但在**花钱决策**里 INCONCLUSIVE 是**放行档**
（暗示「把数据搞好再看一次」），NO-GO 才是保守档。这是把「对数据主张保守」（不敢下强结论）
当成了「对资本保守」（不乱花钱）——**前者的谨慎产生后者的冒进**。
B110 spec §1 逐字：「上一条路 B103-B105 正是在**投入之后**才发现 long-only edge ≈ 0，
本批次的存在意义就是不重复那个顺序」——裁 INCONCLUSIVE 恰好重复那个顺序。
**规则：first-look 类批次的裁定档必须标注各档的资本行动含义（放行/收口），
「保守」二字须限定是对数据保守还是对资本保守。**

**内容 6 — ★几何年化会把「降波」混进「选股」，主判据须与算术并排。**
B110 主口径几何超额 +0.9606%（正）而算术超额 −0.3237%（负），**符号相反**。
分解：Q5 月度均值 1.2346% **低于**基准 1.2616%，但 Q5 月度 σ=6.84% vs 基准 8.16%，
复利拖累少 1.2843pp —— **全部几何超额来自波动率，选股 alpha 为负**。
决定性检验：把 Q5 保持均值不变缩放到基准波动率，超额变成 **−0.3492pp**。
而降波不需要该因子就能买到。冻结附录 D2 本已要求算术并排披露，但 signoff 的裁定表未并排。
**规则：几何为裁定口径时，算术必须同表并排；两者符号相反时须显式做波动率分解，
不得单凭几何进入放行档。**

**建议写入：** `framework/README.md` §经验教训（内容 1/2/5）+
`framework/harness/evaluator.md`（内容 3/4：冻结条款清单强制列出 + 一致率必须报分母筛选逻辑 +
禁恒真断言）+ `framework/harness/generator.md` §37 first-look 判据（内容 6）+
`framework/templates/signoff-report.md`（裁定段增加「已核对冻结条款清单」与
「原始判据触发项 / 覆盖敏感性覆盖项」两栏）

**状态：** 待确认
