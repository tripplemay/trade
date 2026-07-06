# B097 生产 synthetic 监控 + rollback 接线 + 定时 canary — Signoff 2026-07-06

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：F003 = Codex 独立验收（代 Codex，用户 /goal 授权，与实现完全隔离，最高怀疑度）。**触生产部署链敏感批次，从严验收。**

---

## 变更背景

test-automation roadmap **P3（部署后 synthetic 监控）**。用户 2026-07-05 授权生产操作解锁。三部分：
1. **F001 (P3-F1)**：只读 synthetic 套件 `synthetic_check.sh` — 扩单端点 healthcheck 为 4 类检查（health 200+db、recent-errors、HEAD≡prod、关键端点形状/鉴权）。
2. **F002 (P3-F2/F3)**：synthetic 套件接入 deploy workflow 作 **额外 rollback 触发门**（additive，与既有 healthcheck 并列 both-must-pass）+ 定时（每 6h）只读 **prod canary** workflow（告警非 rollback）。
3. **F003**：本报告——独立验收。

**★命门（生产安全，goal 焊死）：** synthetic 绝不 mutate prod / 对活 prod 实测零假红（假红触发不必要 rollback）/ rollback 接线安全（非任意可触发的生产回滚）/ 无凭证泄露 / additive 零回归。

---

## 验收方法（独立，非信任实现自证）

Evaluator 未信任 generator 的"零假红"声明，而是**独立对活生产只读实测 + 拉真机 CI run 日志 + 逐行 trace 触发逻辑**：

1. 逐行读 `synthetic_check.sh` / `workbench-prod-canary.yml` / `workbench-deploy.yml` diff。
2. 独立读 `/api/health` 源（`app.py:_resolve_version`）确认 version 字段语义。
3. **独立 curl 活生产**（read-only GET）解析域名歧义 + 确认零假红。
4. **独立本地跑 `synthetic_check.sh` 打活 prod** + armed check[3] 双向 teeth 测试（match→PASS / mismatch→FAIL）。
5. **拉真机 GitHub canary run 日志**（run 28776985789）确认 CI 环境零假红。
6. grep 全 git 历史扫凭证泄露；actionlint 前后对比证 SC2087 pre-existing。

---

## ★命门裁定（BLOCKING 项逐条）

### 命门 1 — synthetic 只读绝不 mutate 生产 · **PASS（BLOCKING 清除）**

- `synthetic_check.sh` 4 处 `curl` **全部 GET**（65/71/144/146 行；无 `-X`/`--request`/`--data`/`-d`/`-T`/`--upload`）。唯一 POST/PUT/DELETE/PATCH 字样在**契约注释**里（第 15 行文档），非代码。
- recent-errors 检查用 `--cookie` GET（读取），非 mutate。auth 端点检查用 GET。
- canary：GET-only，**无 SSH、无 secret、不触 VM**（`permissions: contents: read`）。
- **结论：不可能改动任何生产状态。**

### 命门 2 — rollback 接线安全性 + 假红稳健 · **PASS（BLOCKING 清除，最危险项已核）**

**(a) 触发边界逻辑逐条 trace（deploy.yml:301-302）：**

新条件：`if: failure() && steps.deploy.outcome == 'success' && (steps.healthcheck.outcome != 'success' || steps.synthetic.outcome != 'success')`

| 场景 | failure() | deploy.outcome | healthcheck | synthetic | rollback 触发? | 正确? |
|---|---|---|---|---|---|---|
| 双门全过 | false | success | success | success | **否**（failure() 假）| ✓ 好部署不回滚 |
| healthcheck 红 | true | success | ≠success | skipped(≠success) | **是** | ✓ |
| healthcheck 过·synthetic 红 | true | success | success | ≠success | **是** | ✓ 新增覆盖 |
| deploy 本身红 | true | ≠success | — | — | **否**（deploy.outcome 守门）| ✓ 未 flip symlink 不回滚 |

- **additive**：既有 `healthcheck.outcome != 'success'` 保留，仅 **OR 扩展**加 synthetic。既有触发条件是新条件的**子集**——既有绿部署行为不变，synthetic 只加覆盖不削弱。
- **blast radius 有界**：rollback 仅在 deploy job 的 `failure()` 上下文 **且** `deploy.outcome==success` 守门下触发 → **非任意可触发的生产回滚**（无 workflow_dispatch/schedule 能单独触发 rollback）。`rollback.sh` **B097 未改**（symlink flip 到上一 release by mtime + `systemctl restart`，不删数据、不碰 DB、不级联）。
- **无死锁部署链**：rollback 是 deploy job 内一步，失败不阻断未来部署（下次 push 走全新 job）。

**(b) 假红稳健（生产命门，独立实测）：**

- **活 prod 独立实测（本地）**：`synthetic_check.sh` 打 `https://trade.guangai.ai` → **EXIT 0，零假红**。[1]✓ [4a]✓ [3]SKIP(未武装) [2]SKIP(public) [4b] /api/market-context→401·/api/home→401·/api/reports→401 全✓。
- **真机 CI canary run 28776985789 日志**：base=trade.guangai.ai，同样 [1]✓[4a]✓[3]SKIP[2]SKIP[4b]✓✓✓，run success 12s。**CI 环境同样零假红。**
- **armed check[3] 双向 teeth**：EXPECTED_SHA==活 prod SHA(`4ff104d…`) → **PASS**（证部署时不假红）；EXPECTED_SHA==错 SHA → **FAIL+exit1**（证真 mismatch 有牙）。
- **只断可靠为真的条件**：脚本只断 HTTP 状态 / JSON 形状 / SHA 40-hex 格式，**从不断易变值**（uptime/counts/backup age）。不可评估的检查 **SKIP 而非 FAIL**（cookie 被拒→SKIP、recent-errors 不可读→SKIP）——结构性防假红。
- **重试容瞬时抖动**：health 5×2s 重试；auth 端点见 401 即 break 容瞬时 blip。
- **armed 部署自洽**：prod `/api/health.version` 读 `/srv/workbench/current/RELEASE_SHA`（deploy 写 `git rev-parse HEAD` 全 40-hex），deploy 传 `EXPECTED_SHA=${RELEASE_SHA}`（同一 `git rev-parse HEAD`）→ 二者同源必等 → PASS。healthcheck-first（20s 重试待服务起）作 settling gate，缓解 restart race。

### 命门 3 — 无凭证泄露 · **PASS（BLOCKING 清除，独立扫描）**

- 新文件**无硬编码 secret**（`sk-`/`Bearer`/`password`/`token=`/`api_key` 仅出现在契约注释）。
- synthetic 唯一可用 secret = 可选 `WORKBENCH_SYNTHETIC_SESSION_COOKIE`，**仅从 env 读，绝不落盘/硬编码**；未设时 public-only 跑。
- canary **不设任何 secret**（public-only，无 SSH）；deploy synthetic 步**仅设 EXPECTED_SHA**（不设 cookie）。
- **全 git 历史扫描** `synthetic_check.sh` + `workbench-prod-canary.yml` = **无明文凭证**。
- deploy.yml 的 `echo "${{ secrets.DEPLOY_SSH_* }}" > file` 为 **B097 未触碰的既有 SSH 配置步**（重定向到文件非 stdout、GitHub 自动 mask、`if: always()` 拆除），非本批引入、非泄露。

---

## 命门 4 — additive 零回归 · **PASS**

| 事项 | 说明 |
|---|---|
| healthcheck 步 | **未改**，仍是 baseline gate |
| synthetic 步 | **新增**于 healthcheck 与 rollback 之间，作额外门（EXPECTED_SHA armed） |
| rollback `if:` | **OR 扩展**非替换（既有触发是子集，未削弱） |
| GC / teardown 步 | 未改 |
| 绿部署行为 | 全过→failure() 假→不回滚，**不变** |
| canary | 独立 standalone workflow（`name: Workbench Prod Canary`），**不干扰** deploy/backend/frontend/safety 三门 |
| 部署链三门 | deploy 仍由 Backend CI + Frontend CI + AI Safety Eval 的 workflow_run arm，B097 未动 |
| **产品可部署代码** | `git diff 4ff104d..HEAD -- workbench/backend workbench/frontend trade` = **空**（prod 与 HEAD 产品代码逐字节相同） |

---

## 命门 5 — 生产落地 · **PASS**

- **canary 注册且跑过**：`gh workflow list` → `Workbench Prod Canary  active  307860088`；workflow_dispatch run **success 12s**（真机日志确认真跑 synthetic 套件、非 no-op、绿）。
- **HEAD≡prod（可部署等价义）**：活 prod version=`4ff104d643e17e1b3e3dc98349d47581c956f38f`（= B096-F001，最后一次触碰产品代码的 commit）。prod↔HEAD 产品树逐字节相同；SHA gap 纯 = deploy-infra(`.github/workflows`) + harness-state(progress/features) + docs(signoff) + `workbench/deploy/scripts`（这些不进 runtime 服务路径）——**标准 chore/infra-commit gap**，正是手动 dispatch（Trigger #2）设计弥合的场景。
- **B097 提交为何未部署（预期非异常）**：Backend CI 触发路径 = `workbench/backend/**` + `trade/**` + `workbench-backend.yml`；Frontend CI = `workbench/frontend/**` + `workbench/backend/**` + `workbench-frontend.yml`。**均不含** `workbench/deploy/**` / `workbench-deploy.yml` / `workbench-prod-canary.yml` → B097 提交不触发产品 CI → 不触发部署链 → prod 合法停在 4ff104d。
- **CI 状态**：最后一次产品部署（B096-F001）Backend CI ✓ + AI Safety Eval ✓（**部署 gate 二门绿**）→ Workbench Deploy success；Frontend CI failure = **B096 已裁定的既有 Playwright E2E smoke flake**（B097 触碰 0 前端文件，产品树 diff 为空佐证），**非门禁、非本批回归**。

---

## 类型检查 / CI / Lint

```
bash -n synthetic_check.sh            → OK（无语法错）
synthetic_check.sh vs 活 prod（本地） → EXIT 0，零假红
armed check[3] match / mismatch       → PASS / FAIL+exit1（双向 teeth）
actionlint workbench-prod-canary.yml  → exit 0（clean）
actionlint workbench-deploy.yml       → exit 1，5×SC2087（见 soft-watch S1）
真机 canary run 28776985789           → success 12s，synthetic 套件全绿
gh workflow list                      → Workbench Prod Canary  active  307860088
git diff 4ff104d..HEAD -- 产品路径     → 空（HEAD≡prod 可部署等价）
```

---

## 软观察（非阻断 soft-watch）

- **S1（actionlint 精度）**：`actionlint workbench-deploy.yml` exit 1，因 5 处 **SC2087 warning**（非 error）——SSH heredoc `<<EOF` 未加引号。这是**故意的 client-side 展开**（`${RELEASE_SHA}`/`${CURRENT_LINK}` 须在 runner 端展开，VM 上无这些 env）。**pre-B097 已有 4 处**（deploy/healthcheck/GC 步），本批新 synthetic 步只加第 5 处、复用同一既有惯用法。GitHub 成功解析并运行两 workflow（canary 绿、B096 deploy 绿）。generator handoff 称"actionlint exit0"略欠精确（实际 exit1 于既有 shellcheck warning），但 canary.yml 确实 clean、deploy.yml warning 全 pre-existing 且意图正确——**非回归、非 bug**。
- **S2（集成路径尚未真机跑）**：修改后的 deploy.yml synthetic→rollback 接线**尚未在真实 CI 部署中执行**（B097 提交路径不触发产品 CI，无触发性产品 commit）。部署路径证据 = (a) synthetic 脚本本地 + 真机 canary 双证零假红；(b) armed check[3] 行为直接验证（match→PASS/mismatch→FAIL）；(c) additive 边界逻辑静态验证。这是 read-only 授权下不强制部署所能取得的最强证据；**下次产品部署即会 exercise**，各组件已单独证实。
- **S3（环境文档过期，交 Planner）**：`.auto-memory/environment.md` 记生产为 `astock.guangai.ai`，但**本项目活生产 API = `trade.guangai.ai`**（astock 返回 nginx 401 basic-auth，非本项目 API 面）。healthcheck.sh / synthetic_check.sh / deploy NEXTAUTH_URL 均正确用 trade.guangai.ai。此为 environment.md 陈旧（Planner 维护域），非 B097 问题；建议 Planner 修正。

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| `rollback.sh` | B097 未改（symlink flip + restart，无数据/DB 触碰） |
| `healthcheck.sh` | B097 未改（仍 baseline gate） |
| 部署三门（Backend/Frontend/Safety CI） | 触发与 gate 逻辑未动 |
| workbench/backend·frontend·trade 产品代码 | 逐字节未动（prod≡HEAD） |

---

## 裁定

**全 PASS（3/3 features；F001+F002 实现 + F003 独立验收）。5 命门无一失守，BLOCKING 项（只读/rollback 安全/无凭证泄露）全清，活生产 + 真机 CI 双实测零假红。→ status=done。**

3 项 soft-watch 非阻断（S1 actionlint 精度/S2 集成路径待下次产品部署 exercise/S3 environment.md 域名过期交 Planner）。

---

_Evaluator 独立验收（代 Codex，用户 /goal 授权，与实现完全隔离）。证据：活 prod read-only 实测 + 真机 canary run 28776985789 日志 + 全历史凭证扫描 + 触发逻辑逐条 trace。不编造，触生产核实均以只读 GET 执行。_
