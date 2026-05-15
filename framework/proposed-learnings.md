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

---

## [2026-05-15] Claude CLI — 来源：B020-F001 Playwright 本机 boot

**类型：** 新坑

**内容：** WSL/Ubuntu 24.04 上跑 Playwright 必须先装 `libnss3 libnspr4 libasound2t64`，但常见用户配置 `http_proxy=127.0.0.1:10808`（Clash/v2rayN 之类）会因 sudo 默认 sanitize env 导致 `sudo apt-get install` 直连超时卡死；解决方式 `sudo -E apt-get ...` 或写 `/etc/apt/apt.conf.d/95proxies`。本机 dev environment 模板若引入 Playwright，需在 README prerequisites 显式标注此点，否则首次安装卡死会被误判为环境损坏。

**建议写入：** `.auto-memory/role-context/generator.md` §"Playwright 本机 dev prerequisites" 或 `framework/harness/environment-patterns.md`（如果存在）。也可作为 frontend 类项目 template README 标准段。

**状态：** 待确认

## [2026-05-15] Claude CLI — 来源：B020-F002 CI workflow

**类型：** 新坑

**内容：** GitHub Actions `actions/checkout@v4` / `actions/setup-node@v4` / `actions/setup-python@v5` / `actions/cache@v4` 仍跑 Node.js 20。2026-06-02 起 GHA 默认强制 Node 24，2026-09-16 完全移除 Node 20。每条 workflow 添加 `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` 或等待官方升级版本。框架级 checklist：任何新 workflow 模板都应预置 Node 24 兼容性配置，免得 6 月后突然集体红屏。

**建议写入：** `framework/harness/ci-patterns.md` §"GitHub Actions Node runtime forward-compat"（或类似），或 `framework/README.md` §经验教训。

**状态：** 待确认

## [2026-05-15] Claude CLI — 来源：B020-F003 backend safety test ruff SIM300

**类型：** 新坑

**内容：** Ruff 规则 `SIM300`（Yoda condition detection）会把 `UPPERCASE_CONSTANT == frozenset()` 视为 Yoda（uppercase + frozenset() 调用 → ruff 推断常量在左），suggest 反着写。对 `frozenset()` / `set()` / `dict()` 这种构造函数右值场景，改用 `len(...) == 0` 或 `not ...` 更稳健。Generator 在 strict ruff (SIM 选中) 项目里写 assertion 时应该默认避开 `const == Constructor()` 形式。

**建议写入：** `.auto-memory/role-context/generator.md` §"编码约定"（或类似），追加一条 "ruff SIM300 + uppercase const 陷阱"。

**状态：** 待确认
