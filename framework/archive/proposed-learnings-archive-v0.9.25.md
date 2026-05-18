# Proposed Learnings Archive — v0.9.25

> 归档日期：2026-05-18
> 来源批次：B022-workbench-phase1 F014 fix-round 1-4
> 闭环情况：9 candidates 归并为 4 groups，全部 Accept（用户 5/18 done wrap-up 决议）。signoff 官方 §Framework Learnings 3 条（deploy.sh source env / health 不暴露 schema drift / signoff 模板加等价性规则）覆盖 Group 1 大部分 + Group 4 全部；Planner 从 fix-round commits 提的 6 条覆盖 Group 1 剩余 + Group 2/3。

---

## Group 1 — Cloud deploy hardening (v0.9.25 #1，4 items)

### 1a. deploy.sh 必须 source systemd EnvironmentFile 才跑 alembic

**类型：** 新坑（生产 ground truth 漂移）

**内容：** SSH session 跑 alembic 的环境变量集合**不等于** systemd service 启动时加载的环境变量集合。systemd unit 通过 `EnvironmentFile=/etc/workbench/workbench.env` 显式 inject 给 backend；deploy.sh 通过 SSH 调进来的 shell 没 source 该文件，Settings 回退到 `DEFAULT_DEV_DB_URL = "sqlite:///./workbench-dev.db"`，alembic 在 release 目录里建 scratch DB（每 release SHA 一个），**真正的生产 DB 从未被迁移**。Runtime backend service 看到的是正确 DB URL（因为 systemd 加了 env），但 schema 来不到。结果：B022 page 写路径 hit `no such table: snapshot_meta / backlog_entry`。

**沉淀位置（已写入）：** `framework/harness/generator.md` §12.5（含完整 `set -a; source; set +a` 代码示例）。

### 1b. deploy.sh 必须 post-alembic schema-assert

**类型：** 新规律（防 silent regression）

**内容：** 即便 1a 修了 env source，仍可能未来 env file 路径 drift / WORKBENCH_DB_URL 写错而 silent fail。加 post-alembic schema assert 在 release symlink flip 之前立即捕捉。

**沉淀位置（已写入）：** `framework/harness/generator.md` §12.6（含 SQLAlchemy inspect 完整 Python heredoc 示例）。

### 1c. Production release tarball 必须 ship 业务 page 引用的 docs 类静态资源

**类型：** 新坑（CI deploy 包不含运行时依赖）

**内容：** `workbench-deploy.yml` rsync 只含 `workbench/backend/` + `workbench/frontend/`，没含 `docs/test-reports/`。但 `/reports` 页运行时 `WORKBENCH_REPORTS_DIR` 默认指向 release dir 下的 docs 路径 → 文件不存在 → 页面空 → 通过 L1 但 L2 红。fix：rsync `docs/test-reports` + `docs/specs` 进 stage。规约层面应改 spec template：列「运行时 page 引用的非 build artifact 静态资源」，逐一 ship。

**沉淀位置（已写入）：** `framework/harness/planner.md` §"Cloud-deploy spec checklist" v0.9.25 扩展 (c)。

### 1d. L2 acceptance 必须含真实读表 + 真实写表（schema drift 不在 health 暴露）

**类型：** 新坑（L2 验收覆盖不够）

**内容：** B021 health probe 全绿，B022 reverify 才在真实业务路径发现 `no such table`。health endpoint 不查业务表，只在写路径 OperationalError 才暴露。规约：任何 SQLite/Alembic cloud 批次 L2 至少覆盖 1 个真实读表 + 1 个真实写表 endpoint，断言返回 200 + payload schema 正确。F014 类 Codex L2 checklist 必须显式列。

**沉淀位置（已写入）：** `framework/harness/planner.md` §"Cloud-deploy spec checklist" v0.9.25 扩展 (d)。

---

## Group 2 — Frontend dev/prod consistency (v0.9.25 #2，1 item)

### 2a. Next.js next.config.mjs dev rewrite 必须 1:1 mirror 生产 nginx /api/* 路由全集

**类型：** 新坑（dev/prod 配置漂移）

**内容：** B022 dev rewrite 只配 `/api/health` + `/api/protected-test` 2 个 endpoint，新加 6 个 page API 全 404。Playwright E2E 不在 API 错误上 fail，让 bug 漏到 reverify 才暴露。规约：加新 endpoint 必须同时 (1) 扩 `next.config.mjs` rewrites（或换 catch-all `/api/:path*`）+ (2) 加 E2E 断言不返 404。

**沉淀位置（已写入）：** `framework/harness/generator.md` §13 Frontend SSR vs Browser context 扩 sub-pattern #5。

---

## Group 3 — CI security gate + 运行时观测 ergonomics (v0.9.25 #3，3 items)

### 3a. npm audit --omit=dev --audit-level=high 必须进 CI gate

**类型：** 新规律（依赖安全前置）

**内容：** B022 F014 reverify 才发现 Next.js + Playwright direct deps 各有 high severity advisory。CI 早 fail 比 reverify 时截到再 fix 省一轮。

**沉淀位置（已写入）：** `framework/harness/generator.md` §10 GHA Node 24 forward-compat 节末加 sub-pattern + YAML 示例。

### 3b. FastAPI SSE long-lived 请求需独立 session lifecycle

**类型：** 新坑（FastAPI Depends 与 long-lived 流冲突）

**内容：** SSE 请求"永远不结束"直到 stream 完，期间任何 DB write 用 Depends-injected session 会 connection pool 漏。规约：SSE/WebSocket/long-polling endpoint 必须显式管理 DB session（短小事务模式：`with SessionLocal() as session:` per write），不用 FastAPI Depends。

**沉淀位置（已写入）：** `framework/harness/generator.md` 新 §14.1（含 StreamingResponse + with 块代码示例）。

### 3c. FastAPI 全局未捕获异常 logger + /api/debug/recent-errors auth-gated endpoint

**类型：** 新规律（生产可观测兜底）

**内容：** B022 生产 backend 出 `no such table` 等 OperationalError，但 frontend 只见 500，无回溯工具。/api/health 不查业务表所以全绿。Codex L2 reverify 没工具找根因。规约：FastAPI app 启动期注册全局异常 hook + 环形缓冲 + 只读 debug endpoint（auth-gated 单 allowlist）。Codex L2 用 `GET /api/debug/recent-errors` 在每个真实写路径后核 `count=0`。

**沉淀位置（已写入）：** `framework/harness/generator.md` 新 §14.2（含 ring buffer + handler + route 完整 Python 代码示例）。

---

## Group 4 — Signoff template Production/HEAD 等价性 (v0.9.25 #4，1 item，Codex 官方提)

### 4a. Signoff 模板加"deployed SHA 与 HEAD 不一致时的等价性判断规则"

**类型：** 模板修订（Codex 官方在 B022 signoff §Framework Learnings 提）

**内容：** 现有模板没指导 Evaluator 如何处理 deployed version 与 HEAD 不同步。判断规则：
- 同 SHA：直接 PASS
- 不同 SHA：检查 `git diff` 内容：
  - 仅含状态机文件（progress.json / features.json / .auto-memory / blocker reports）→ 接受不同步，标"产品代码无漂移"
  - 含产品/spec/framework 文件 → 必须重 deploy 后再签

**沉淀位置（已写入）：** `framework/templates/signoff-report.md` 新增 §"Production / HEAD 等价性"段（Harness 说明 与 Soft-watch 之间），含 3 行状态表 + 判断规则 + 适用对象（cloud-deployed 批次必填，纯本地批次可写"批次不含 cloud deploy"）。

---

## 整批回顾

B022 暴露的 9 个 learnings 中**最高优先级**是 deploy.sh source env file（1a）—— 不修复未来任何 cloud-deployed 批次都会因 systemd vs SSH env 差异在 alembic 阶段悄悄失败。Group 1 全 4 条都是 cloud deploy 安全网（防止 same class of failure 复发），Group 4 是 Evaluator 工具升级（更早抓到 deploy/HEAD drift）。Group 2 + 3 是局部 ergonomic 提升但有跨项目复用价值。

B022 沉淀价值高于 v0.9.24（B021）—— v0.9.24 是 first-time bootstrap 一次性踩坑，v0.9.25 是稳态运营的可重复事故模式。

来源：B022 signoff `docs/test-reports/B022-workbench-phase1-signoff-2026-05-18.md`，及 commits `c2f22d5` / `e64a555` / `bddf1d5` / `6c0d282` / `569b2de` / `8d9a948` / `72a3169` / `3543abf`。
