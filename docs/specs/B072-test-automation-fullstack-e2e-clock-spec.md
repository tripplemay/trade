# B072 — 测试自动化基建 Phase 2(核心）：golden 全栈 CI + e2e 交易闭环 + 可注入时钟 Spec

**批次定位：** 测试自动化路线图 Phase 2（接 B071 golden 地基）。把"端到端真机行为"下沉 CI——golden 数据播进 DB 的**全栈 CI** + 自动化**交易闭环 e2e**（推荐→diff→ticket→fills→reconcile→journal，= BL-B023-S1 Codex 手动冒烟）+ **可注入时钟**（CI 快进验证 timer 定时行为，不等真实时间）。

**来源：** 2026-06-21 用户 B071 done 后选「测试基建 Phase 2」。

**★范围裁定（Explore 现实校正，焊死）：** 全仓 **0 docker（无 compose/Dockerfile）+ DB=SQLite（Postgres 明确排除）+ 生产=systemd**。roadmap "docker-compose 全栈" 是理想化;引入 docker+Postgres = 与既有 sqlite/systemd 架构冲突的大 scope creep。**本批走务实路线:复用现有 sqlite + 进程编排半栈**(`workbench-frontend.yml` 已在 CI 起 uvicorn sqlite backend + Playwright)**扩成全栈,不引 docker/Postgres**。docker-compose 仅作可选本地 dev 便利(非本批硬性)。**VCR 录放(P2-F3)ROI 最低(golden 已给确定性),延后 Phase 2.1。**

---

## 1. 现状 + 缺口（Explore 已核）

- **全栈 boot**:`scripts/start_workbench.sh`(只起 backend+frontend,无 worker/独立 DB);`workbench-frontend.yml:100-153` CI 已起"半栈"(uvicorn sqlite + alembic + seed + Playwright)。**缺**:worker daemon 入栈 + golden→DB 播种。
- **时钟**:服务层 `now=`/`today=`/`as_of=`/`computed_at=` seam **全齐**;**缺**:timer CLI 顶层硬 `datetime.now(UTC)`(~10 处:`prices/cli.py:180`、`recommendations/precompute.py:248`、`worker.py:231` 等)未贯穿 → CI 无法快进。
- **e2e 闭环**:execution 6 页 + 13 后端 API **全齐**,但 **0 闭环 e2e**(13 spec 全是研究页/shell 冒烟);`protected-routes.spec.ts:91` 只断 execution shell+disclaimer。**缺**:串 recommend→diff→ticket→fills→reconcile→journal 的 e2e + 闭环 DB 种子。
- **golden 衔接**:B071 `data/fixtures/golden/`(纯引擎 `fixture_dir=` 注入)+ 根 conftest `build_golden_strategy_results` harness。**缺**:golden→DB seed(全栈/e2e 用)。

---

## 2. 复用清单（Explore 已核源码）

| 资产 | 位置 | 用法 |
|---|---|---|
| 半栈 CI 模板 | `workbench-frontend.yml:100-164`（uvicorn sqlite + alembic + seed + start-server-and-test + Playwright）| 扩成全栈(加 worker + golden DB seed) |
| boot 脚本 | `scripts/start_workbench.sh:49-60`（backend+frontend 进程编排）| 参考 + 加 worker daemon |
| worker daemon | `backtests/worker.py:190`（`python -m workbench_api.backtests.worker` 排空队列）| 全栈起一个 |
| golden 数据 + harness | `data/fixtures/golden/` + 根 `tests/conftest.py build_golden_strategy_results` | golden→DB seed 源 |
| DB seed 范式 | `workbench/backend/scripts/seed_e2e_reports.py`（CI 灌 1 report）+ `precompute.py:259 run_precompute(score_fn=)` | 扩成 golden 全套 seed（account+recommendation+report）|
| 时钟服务层 seam | `tickets.py:355`/`fills.py:219`/`reconcile.py:238`/`execution.py:125`/`*precompute.py computed_at` 全有 `now=`/`as_of=`/`computed_at=` | timer CLI 加旗标贯穿 |
| 执行链 API | `routes/execution.py:90-243`（position-diff/account/tickets/fills/reconcile/journal）+ `routes/recommendations.py:38,80` | e2e 闭环串这些 |
| execution 6 页 | `(protected)/execution/{position-diff,account,ticket,fills,journal-history}/page.tsx` | e2e 走这些页 |
| Playwright | `frontend/playwright.config.ts` 3-project + `auth-setup.ts`（HS256 cookie）| 加闭环 spec |
| acceptance CI step | `workbench-backend.yml:81`（已跑 `pytest tests/acceptance`，B071）| 全栈/确定性断言挂这 |
| no-execution 守门 | `tests/safety/no-execution-buttons.spec.ts` | 闭环 e2e 测 checklist+fills CSV+reconcile（非下单），合规避禁词 |

---

## 3. Feature 拆解（4 features：3 generator + 1 codex）

### F001 — golden 全栈 CI 编排 + golden→DB 播种（executor: generator）

1. **golden→DB seed 脚本**:`WORKBENCH_DATA_ROOT=data/fixtures/golden` + 跑 precompute/recommendations CLI（或扩 `seed_e2e_*.py`）把 golden 推进 DB——recommendation_snapshot（确定性目标）+ account_snapshot（闭环账户）+ investment_report。确定性（同 golden → 同 DB 内容）。
2. **全栈编排（sqlite + 进程，无 docker）**:扩 `workbench-frontend.yml`（或新建 `workbench-fullstack-e2e.yml`）起 backend(uvicorn sqlite) + **worker daemon** + frontend + golden DB seed,CI 一键起。
3. **golden 确定性全栈断言**:全栈起来后打关键端点（/recommendations/current、/strategies、/home）断数据形状/golden 值合理（acceptance 层）。
4. **不引 docker/Postgres**（范围裁定）;docker-compose 可选本地 dev（非硬性）。

**Acceptance：** golden→DB seed 脚本确定性（同 golden→同 DB）;全栈 CI 起得来（backend+worker+frontend+seed）;关键端点返 golden 数据。Gates：backend pytest/ruff 目录上下文/mypy + CI 全栈 step 绿。

### F002 — e2e 交易闭环（推荐→diff→ticket→fills→reconcile→journal）（executor: generator）

1. **闭环 e2e spec**:在全栈（F001 golden seed）上串：`/recommendations`（看目标）→ `/execution/position-diff`（看买卖差异）→ 生成 `/execution/ticket`（Markdown checklist）→ 上传 `/execution/fills`（CSV）→ `/execution/reconcile/{id}` → `/execution/journal-history`（看记录）。**= BL-B023-S1 手动冒烟自动化**。
2. **合规**:测 checklist 生成 + fills CSV 上传 + reconcile + journal（**非下单**），避 `no-execution-buttons` 禁词。
3. 闭环 DB 种子（account_snapshot + recommendation_snapshot，F001 seed 复用）;HS256 auth cookie（现成 auth-setup）。
4. 接 CI（扩 `workbench-frontend.yml` e2e 或全栈 workflow）;失败上传 Playwright trace。

**Acceptance：** e2e 跑通完整闭环（6 步全绿，journal 见记录）;合规守门过;CI 接入。Gates：Playwright e2e 绿 + no-execution/disclaimer safety 守门过 + vitest/tsc/eslint。

### F003 — 可注入时钟（timer CLI --as-of 贯穿 + CI 快进验证定时）（executor: generator）

1. **贯穿注入**:给各 timer CLI 入口加 `--as-of`/`--now` 旗标，贯穿到**现有服务层 seam**（`now=`/`today=`/`computed_at=`/`as_of=`）——替顶层硬 `datetime.now(UTC)`（~10 处：prices/data-refresh/recommendations/advisor/news/regime/cn_attack/paper-mtm/canonical/worker）。默认仍 `datetime.now(UTC)`（生产零回归）。
2. **CI 快进验证定时行为**:用 `--as-of <golden 日期>` 跑 precompute/MTM/news 等，断**按注入日期产出正确结果**（如 paper MTM 按指定日 mark、precompute 按指定 as-of 评分）—— 不等真实时间，定时逻辑可测。
3. acceptance 断言（用 golden + 注入时钟）。

**Acceptance：** timer CLI 全支持 `--as-of` 贯穿现有 seam（默认 now 生产零回归）;CI 用注入日期快进验证 ≥3 个 timer 定时行为正确。Gates：backend pytest/ruff 目录上下文/mypy + acceptance。

### F004 — Codex 验收 + signoff（executor: codex）

**真机/全栈批次——signoff 含实测证据（§29）：**
- L1 全门禁（B071 起 verifying 可跳 L1 复跑，确认 CI 绿即可，§evaluator §30）。
- **L2 实测（贴真返回）：** ① golden 全栈 CI 起得来 + golden→DB seed 确定性（同 golden→同 DB）;② **★e2e 交易闭环 6 步全绿**（trace/截图 + journal 真记录）= BL-B023-S1 自动化达成;③ 时钟快进真验（`--as-of` 跑 timer → 按注入日期产出正确，贴对比）;④ 零回归（生产 timer 默认 now 不变 / B067/B071 不破）。
- **★mutation 核（沿 B071 §31）**:故意破坏闭环一环（如 fills 数量错）→ e2e 红（有牙齿）。
- research-only / no-execution / no-broker 边界守;HEAD≡prod。signoff 实测证据逐条。

---

## 4. 状态流转 + 不变量 + 边界

- 混合批次：`planning → building(F001→F002→F003) → verifying(F004) → done`。
- **不变量**:① 生产 timer/job 行为零回归（`--as-of` 默认 `datetime.now(UTC)`，CI-only 注入）;② B067/B071 + Master/A股 进攻 + golden acceptance 零回归;③ research-only / no-execution（e2e 测 checklist+fills+reconcile 非下单）/ no-broker;④ §12.10.2 / ruff 目录上下文 / mypy CI-exact;⑤ 不引 docker/Postgres（sqlite+进程编排）。
- **诚实边界（roadmap §4 + B071 §31）**:e2e/全栈/时钟断言由写码方写存同向错盲点 → F004 mutation-check 对冲 + 独立评审仍审新颖/模糊;VCR(P2-F3)延后 Phase 2.1;真金生产判断不自动化。
- **后续**:Phase 2.1（VCR 录放）/ Phase 3（prod synthetic+canary）/ Phase 4（LLM-judge）/ Phase 5（瘦身评审）待按需。
