# B071 F001 — 门禁确权报告（Gate Authority Audit）

> **作者：** Generator（B071 F001，2026-06-21）。
> **目的：** 审计仓库全部 7 个 GitHub Actions workflow，**坐实**「L1 全门禁 + safety 守门 + AI 红队 eval 都已在 CI/PR 自动跑」，从而得出结论 —
> **Codex 在 `verifying` 复跑 L1 是冗余的，可跳过 L1 直入 L2（真实数据行为验收 + 裁定）。**
> **关系：** 这是 `docs/dev/test-automation-roadmap.md` §1（现状核实）+ Phase 0（P0-F1 门禁确权）的**落地证据**。本报告把 roadmap §1 的概括表升级为**逐 workflow 实测**，并补出两处确权缺口 + 用户待设清单。

---

## 0. 一句话结论

仓库 7 个 workflow 中，**4 个是 CI 门禁**（`python-ci` / `workbench-backend` / `workbench-frontend` / `ai-safety-eval`），**1 个是部署链 + 部署门禁**（`workbench-deploy`，跑在三 CI 全绿之后并复核 `conclusion`），**2 个是纯手动运维工具**（`bootstrap-env` / `nginx-sync`，非门禁）。**4 个 CI 门禁覆盖了 L1 全门禁（pytest / mypy / ruff 后端+trade、vitest / tsc / eslint / Playwright 前端）+ safety 边界守门 + AI 红队 eval**，且**每次 push 到 `main` 和每个触及相关路径的 PR 都自动跑**。**∴ Codex `verifying` 复跑 L1 完全冗余，可跳 L1 直入 L2。**

**两处确权缺口（本报告补）：** ① `branch-protection-guidance.md` 的 required-checks 清单**漏列 `AI Safety Eval`**（它是部署门禁 boundary (n)，且在 PR 上跑）；② path-scoped workflow 的 "required" 语义未点明（required + 路径过滤 = 未触发的 PR 会卡在「等待状态上报」）。**用户待设清单见 §4。**

---

## 1. 7 Workflow 逐一审计（2026-06-21 实测，逐 YAML 读 + `pytest --collect-only` 取真实用例数）

| # | Workflow（文件） | 触发 | 跑什么（步骤） | 实测用例数 | 性质 |
|---|---|---|---|---|---|
| 1 | **Python CI**（`python-ci.yml`） | `push: main` + `pull_request`，`paths-ignore` 排除 `workbench/**`、`docs/**`、`.auto-memory/**`、状态 JSON | `pytest`（根 `testpaths=["tests"]`）→ `ruff check .` → `compileall trade` → `mypy --install-types trade` | **1014** 根 pytest | **CI 门禁** |
| 2 | **Workbench Backend CI**（`workbench-backend.yml`） | `push: main` + `pull_request`，`paths` = `workbench/backend/**`、`trade/**`、`scripts/**`、`pyproject.toml`、本 yml | `ruff check .` → `mypy`（strict，`workbench_api`+tests）→ `pytest tests/unit -q` → `pytest tests/safety -q`；含 `pip install ../..`（装 trade 包） | **unit 1308 / safety 179** | **CI 门禁** |
| 3 | **Workbench Frontend CI**（`workbench-frontend.yml`） | `push: main` + `pull_request`，`paths` = `workbench/frontend/**`、`workbench/backend/**`、本 yml | OpenAPI→TS drift（`git diff --exit-code api.ts`）→ `eslint`（`--max-warnings=0`）→ `tsc --noEmit` → `vitest run` → 启 FastAPI 后端 → `playwright test`（chromium） | **vitest 53 spec / e2e 12 spec** | **CI 门禁** |
| 4 | **AI Safety Eval**（`ai-safety-eval.yml`） | `push: main` + `pull_request`，`paths` = `workbench_api/llm/**`、`advisor/**`、红队测试文件、`data/safety-evals/**`、本 yml | 跑迁移建 `llm_budget_log` 表 → `pytest test_ai_advisor_red_team.py`（红队 15 样本）→ `pytest test_safety_eval_workflow.py`（workflow 接线不变量） | **24**（两文件合计） | **CI 门禁 + 部署门禁 (n)** |
| 5 | **Workbench Deploy**（`workbench-deploy.yml`） | `workflow_run`（`Workbench Backend CI` / `Workbench Frontend CI` / `AI Safety Eval` 三者任一 `completed`，限 `main`）+ 手动 `workflow_dispatch` | `if: conclusion=='success' && head_branch=='main'` 门禁 → placeholder 预检 → build backend/trade/frontend → SCP → alembic → symlink flip → restart → **post-deploy healthcheck** → 失败 `rollback.sh` → GC | — | **部署链 + 部署门禁** |
| 6 | **Bootstrap env**（`bootstrap-env.yml`） | **仅** `workflow_dispatch`（需输入 `confirm='bootstrap-env'`） | 从 Secrets 组装 `/etc/workbench/workbench.env` → SCP 到 VM 暂存区（admin 手动 install） | — | **手动运维，非门禁** |
| 7 | **Sync nginx vhost**（`nginx-sync.yml`） | **仅** `workflow_dispatch`（需输入 `confirm='nginx-sync'`） | nginx 配置静态预检 → SCP 到 VM 暂存区（admin 手动 install + `nginx -t` + reload） | — | **手动运维，非门禁** |

> 用例数口径：`*.venv/bin/python -m pytest <path> --collect-only -q`（2026-06-21 本机 Python 3.11.15）。前端 vitest 53 spec = 45 `tests/unit/**` + 8 `tests/safety/*`（`vitest.config` `include` 显式列，含 `no-broker-sdk-imports.spec.ts`；其余 `tests/safety/*.spec.ts` 是 Playwright 而非 vitest）；e2e 12 = `tests/e2e/*.spec.ts`。

---

## 2. L1 全门禁坐实（roadmap §1 的逐项证据）

roadmap §1 声称「L1 全门禁 + safety 守门 + AI 红队 + 部署后 healthcheck 已经是全自动 CI」。本审计逐项坐实：

| roadmap §1 声称 | 实测落点 | 触发面 | 状态 |
|---|---|---|---|
| L1 后端 ruff / mypy(strict) / pytest unit / safety 守门 | `workbench-backend.yml` 4 步（Ruff / Mypy / Pytest unit 1308 / Pytest safety 179） | push main + PR（backend/trade/scripts/pyproject） | ✅ 坐实 |
| L1 前端 vitest / tsc / lint / api.ts drift / Playwright | `workbench-frontend.yml`（drift / eslint / tsc / vitest 53 / playwright 12） | push main + PR（frontend/backend） | ✅ 坐实 |
| trade 包 mypy trade（比 backend 更严） | `python-ci.yml`（pytest 1014 / ruff / compileall / mypy trade） | push main + PR（非 workbench/docs/状态文件） | ✅ 坐实 |
| AI 边界 红队 eval（15 样本 + 接线断言） | `ai-safety-eval.yml`（红队 15 + workflow wiring） | push main + PR（llm/advisor/红队数据集） | ✅ 坐实 |
| 部署后 healthcheck（回显 SHA） | `workbench-deploy.yml`（healthcheck.sh + 失败 rollback） | workflow_run（三 CI 绿后）+ 手动 | ✅ 坐实 |

**关键认知（确证）：** Codex 在 `verifying` 阶段跑的 L1（ruff/mypy/pytest/vitest/tsc/eslint/safety）**本质是复跑一遍 CI 在 push/PR 上已经跑过、且对 `main` 是 push 触发必跑的东西**。这些门禁是确定性的、机读的、无需人判断。

> **∴ 结论：本批起，Codex `verifying` 可跳过 L1 复跑，直入 L2** —— 真实数据行为验收（桶 A，本批 F002/F003/F004 下沉）、裁定、signoff（桶 D，仍人/独立 agent）。这不削弱铁律 4 独立性：L1 本就由 CI 机读门禁守，evaluator 的独立价值在 L2 的**新颖/模糊**判断，不在复跑机械门禁（详见 roadmap §4.1）。

### 2.1 覆盖完整性 + 诚实边界（独立对抗复核已核，2026-06-21）

对「L1 全门禁已在 push-to-main 跑、复跑冗余」这个承重结论，做过独立对抗复核（专门找洞），**未能证伪**，确认成立。同时记录三条诚实边界：

- **无 PR-only-vs-push 不对称：** 4 个门禁的 `push.paths` 与 `pull_request.paths` 完全一致，故 push-to-`main` 的覆盖面 = PR 覆盖面，不存在「push 跳过某 PR 才跑的 check」的洞。
- **ai-safety-eval 的窄路径不是洞（红队双门禁）：** `ai-safety-eval.yml` 只在 `llm/**`、`advisor/**`、红队数据集等路径触发，**但同一个红队测试 `tests/safety/test_ai_advisor_red_team.py` 也被 `workbench-backend.yml` 的 `pytest tests/safety -q` 兜底**——后者在**任何** `workbench/backend/**` push 都跑。所以即便 advisor 回归经一个不在 `advisor/**` 路径的文件（如 `services/market_context.py`，被 `advisor/grounding.py` import）落地，红队门禁仍会触发。**窄路径只是「额外早跑一道」，不是唯一一道。**
- **业务码路径全覆盖，措辞收敛到实际范围：** 主业务面（`trade/`、`scripts/`、`workbench/backend/`、`workbench/frontend/`）由 3 个门禁的路径并集**完整覆盖**；空脚手架 `src/`、`configs/`、`notebooks/` 只有 `.gitkeep`。**唯一 nit（在本报告 scope 之外，但诚实记下）：** `data/fixtures/*.py` 这类生成脚本只被 `python-ci` 的 `ruff check .` lint，**不被 mypy（`files=['trade']`）和 pytest（`testpaths=['tests']`）覆盖**——这不影响 L1 复跑冗余的结论，但 F002 在 `data/fixtures/golden/` 落数据（非 `.py`）时应知此门禁边界。
- **docs-only / chore-only push 触发零 CI（关系到本批）：** `python-ci` 的 `paths-ignore` 含 `docs/**`、`.auto-memory/**`、状态 JSON；其余三门禁用 `paths` include 也不含 `docs/`。**故 F001 自身这种纯 doc 改动 push 到 `main` 不触发任何 CI/部署**——「Gates 门禁绿」对纯 doc 批是 vacuously green（无 CI 可红）。这正是 `workbench-deploy` 需要手动 `workflow_dispatch` 兜底的原因（chore-only commit 上生产）。

---

## 3. 确权缺口（本报告补出）

### 缺口 ① — `AI Safety Eval` 未列入 branch-protection required-checks 清单

`docs/dev/branch-protection-guidance.md`（B022 refresh 时定稿）的 required-checks 清单只列了 `python-ci` / `workbench-backend` / `workbench-frontend` / `workbench-deploy(候选)`，**漏掉 safety eval 这一道门禁**。但 `ai-safety-eval` 既是 **PR/push 上跑的 CI 门禁**，又是 **`workbench-deploy.yml` 的第三个上游门禁**（永久边界 (n)：红 safety eval 必须阻断生产部署，被 `tests/safety/test_safety_eval_workflow.py` 钉死）。**本报告同时更新 guidance.md 补上该 check。**

> **★ 两套命名空间，勿混（实测）：** 同一道 safety eval 门禁，在两个机制里用**不同的名字**——
> - **部署链**（`workbench-deploy.yml` 的 `workflow_run.workflows` 列表）按 **workflow 名** `AI Safety Eval` 匹配 —— 这是**对的**，且被 `test_safety_eval_workflow.py` 的 `assert workflow.get('name') == 'AI Safety Eval'` 钉死，**不要改**。
> - **branch-protection required check** 按 **job/check-run 名** `safety-eval` 匹配（§4）。
>
> 即：guidance.md 的部署门禁说明里写 `AI Safety Eval`（workflow 名）正确；但用户在 required-checks 选择器里**必须选 `safety-eval`（job 名）**，**不要把 `AI Safety Eval` 填进 required-checks picker**。

### 缺口 ② — path-scoped workflow 的 "required" 语义未点明（required + 路径过滤的卡死陷阱）

全部 4 个 CI 门禁都是 **path-scoped**（`python-ci` 用 `paths-ignore`；其余三个用 `paths` include）。GitHub branch-protection「required status checks」与路径过滤组合有一个经典陷阱：

- **若把一个 path-scoped check 标为 required**，当某 PR **不触及**该 workflow 的匹配路径时，该 workflow **不会触发**，于是该 required check **永远不上报**，PR 卡在「Expected — Waiting for status to be reported」**无法合并**。
- 例：一个只改 `workbench/frontend/**` 的 PR 不会触发 `python-ci`（被 `paths-ignore` 之外…实为 `workbench/**` 被 ignore）也不触发 `workbench-backend`；若这两者被设为 required，该纯前端 PR 会卡死。

**缓解口径（写入 guidance.md）：** 本项目**常态流程是直接 push 到 `main`**（见 `harness-rules.md` §分支规则：「代码提交推 main，CI 全绿后自动链式部署」），**不走 PR-merge 门禁**。因此：
- **真正的、已自动化的强制门禁 = push-to-main CI + `workbench-deploy` 的 `conclusion=='success'` 复核**（红 CI / 红 safety eval → deploy 的 `if` 短路，不部署）。这条**已经在跑、无需用户动作**。
- branch-protection ruleset 是**第二层、当前仅 advisory 的 PR-merge 门禁**，仅当用户启用 PR 工作流时才生效。要避免上述卡死，**path-scoped check 设 required 时应配合**：要么用「always-run 汇总 job」做单一 required gate，要么接受「未触发=不阻断」（GitHub 较新行为对 skipped 的处理），**不要把 4 个 path-scoped CI 全部裸设 required**。

---

## 4. ★用户动作交接（agent 不改仓库设置）

以下动作**需要用户在 GitHub 仓库 Settings → Branches / Rulesets 手动设置**，agent（Generator/Codex）**不改仓库设置**，本报告只列清单：

**若用户启用 PR-merge 门禁（branch protection ruleset for `main`），建议把下列 checks 设为 required。**

> **★ 选哪个字符串（实测精度点）：** GitHub branch-protection 的「require status checks」选择器列出的是 **check-run 名 = job 名**（这些 workflow 的 job 都没写 `name:`，故 check 名 = job key），**不是 workflow 的 `name:`**。下表「实际 required 字符串」列即用户应在 UI 里搜索/勾选的精确值；其中 `python-ci.yml` 的 job 名是 `python-checks`、`ai-safety-eval.yml` 的 job 名是 `safety-eval`，**与 workflow 显示名不同，勿用错**。

| 来源 workflow（显示名） | **实际 required 字符串（job/check-run 名）** | 备注 |
|---|---|---|
| `python-ci.yml`（Python CI） | **`python-checks`** | 保护 `trade/` stdlib 路径；注意 ≠ `python-ci` |
| `workbench-backend.yml`（Workbench Backend CI） | **`workbench-backend`** | 后端 type/lint/unit/safety |
| `workbench-frontend.yml`（Workbench Frontend CI） | **`workbench-frontend`** | 前端 lint/tsc/vitest/Playwright/OpenAPI drift |
| `ai-safety-eval.yml`（AI Safety Eval） | **`safety-eval`** | **本次补列**；红队 eval + 部署门禁 (n)；注意 ≠ `AI Safety Eval` |

**设置时注意（缺口 ② 的实操约束）：**
- **名字以 UI 实显为准（兜底）：** 上表给的是 job/check-run 名（这些 job 无 `name:`，故 = job key）。若你的 GitHub 版本在选择器里显示的是 composite 形式 `<Workflow Name> / <job>`（如 `Python CI / python-checks`），则**按你在 checks UI 里实际看到的那个完整字符串勾选**——核心铁律是「选 check-run 名，不选 workflow 顶层 `name:`」。
- 这 4 个都是 path-scoped，**裸设 required 会让不触及对应路径的 PR 卡在「等待上报」**。如果用户确实要 PR 门禁，推荐先加一个「always-run 汇总 gate job」作为唯一 required check，由它在内部等待路径相关的 workflow，或确认当前 GitHub 版本对「未触发的 required check」按 skipped 放行后再裸设。
- `workbench-deploy` 跑在 `workflow_run` 而非 `push`/`pull_request`，GitHub 常把这类 check 列为 advisory 而非可强制；设 required 前需在仓库设置里确认它出现在「required status checks」可选列表中（详见 guidance.md「Notes」）。

> **不需要用户动作的部分（已自动）：** push-to-main 的 4 个 CI 门禁 + `workbench-deploy` 的 conclusion 复核 + 部署后 healthcheck + 失败 rollback —— 这条链是当前实际生效的强制门禁，红 CI / 红 safety eval 自动阻断部署，**无需 ruleset 配置即生效**。

---

## 5. 对 evaluator 流程的影响（本批 F005 将复核）

- **本批起，evaluator（Codex）在 `verifying` 可跳过 L1 复跑**（ruff/mypy/pytest/vitest/tsc/eslint/safety）——这些已由 4 个 CI 门禁在 push/PR 上确定性守住。
- evaluator 的独立验收面积缩到：① L2 真实数据行为验收里**本批新颖**的部分（机械的复发不变量由 F004 acceptance CI 永久守）；② 裁定 / signoff / 框架沉淀（桶 D，机器判断不了，守铁律 4 独立性）。
- **诚实边界（roadmap §4.1）：** 复发不变量的 acceptance 断言**由 Generator 写又在 CI 跑**，会放回「测试与 bug 同向错」盲点 → 故 F005 用 **mutation-style 核「acceptance 有牙齿」**（故意改坏不变量→对应 acceptance 必须红）+ 保留独立对抗评审（面积缩到新颖/模糊）来对冲。

---

_Disclaimer: research-only；本报告只审计 CI 门禁现状与 branch-protection advisory 配置，不改仓库设置、不碰生产数据路径。_
