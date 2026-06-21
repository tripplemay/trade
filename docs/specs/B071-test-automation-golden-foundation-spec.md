# B071 — 测试自动化基建 Phase 0+1：门禁确权 + golden 真数据 + 验收即代码 Spec

**批次定位：** 测试自动化路线图(`docs/dev/test-automation-roadmap.md`)的**地基批**(Phase 0 + Phase 1，★最高 ROI)。把 Codex L2 真机验收里"**真实数据回归行为**"这桶(桶 A)下沉 CI：冻结真实数据为 committed golden fixture → 回测/推荐变**确定性可断言** → 复发不变量变**永久 acceptance 回归**(做一次永远守)。**目标不是干掉 evaluator,是把它从"复跑机械门禁"解放出来,只做机器做不了的判断。**

**来源：** 2026-06-19 用户 B070(A股 进攻调查收官)后选「测试自动化基建」。**触发动机**:B061/B062/B063 evaluator 空洞 FULL PASS + B065/B067 SSH 误诊 + B066-B070 这串策略批反复靠手动/agent 真机回测把幻觉与真信号分开——证明 §25 真机验收退化是系统性问题,且确定性回测基建是结构性解法。

---

## 0. 现状(Explore 已核)+ 本批攻什么

- **L1 全门禁(pytest/mypy/ruff 后端+trade、vitest/tsc/eslint 前端)+ safety 守门(tests/safety 29 个)+ ai-safety-eval(红队 15 样本)+ 部署后 healthcheck 已全自动 CI**(7 workflow)。Codex 在 verifying 复跑 L1 = 冗余。
- **缺口**:① branch protection 只有 advisory doc(无机读 ruleset),`AI Safety Eval` 未列入 required-checks 清单;② **没有 golden 真数据**——真数据回测只能 Codex 真机跑一次(`testing-strategy §1 fixture-first` + v0.9.21 lesson);③ **acceptance 层不存在**(`tests/integration/` 空壳);④ **"N 策略同时段两两不同"(B050 反例)无 CI 永久回归**——其余 5 条复发不变量已有单元覆盖但散落、未上提 acceptance。
- **本批攻**:Phase 0 确权(把"L1 复跑冗余"坐实 + 补 required 缺口)+ Phase 1 golden 真数据 + 验收即代码(确定性断言 + 复发不变量永久回归)。

---

## 1. 复用清单（Explore 已核源码）

| 资产 | 位置 | 用法 |
|---|---|---|
| 数据注入 seam（us_quality）| `trade/data/us_quality_universe.py`（`fixture_dir` 参数 L177 最高优先;`PRICES_REQUIRED_COLUMNS` L96 / `FUNDAMENTALS_REQUIRED_COLUMNS` L106）| golden 数据走 `fixture_dir=golden_dir`，schema 匹配即零改 loader |
| 数据注入 seam（推荐）| `recommendations/precompute.py`（`run_precompute(score_fn=...)` L259 可注入;`test_recommendations_precompute.py:183` 已用 fixture 跑真 master scoring）| golden 替换该 fixture → 确定性推荐断言 |
| PIT loader（master 用）| `trade/data/loader.py`（`load_prices`/`load_fundamentals`，**无 fixture_dir**）+ `engine.py:run_backtest` L230（内部直调 load_*，无 fixture_dir 透传）| **P1 真改造点**:补 `fixture_dir` 透传对齐 us_quality_universe |
| data_root override | `trade/data/data_root.py`（`WORKBENCH_DATA_ROOT` 只影响 unified 真数据，不碰 fixture）| golden 用 fixture seam 非 data_root |
| 现有 fixture 模板 | `data/fixtures/us_quality_momentum/`（4.8MB committed，synthetic，含 `_generate.py`）| golden 同结构同 schema，但**真实数据**子集 |
| 复发不变量现有单元覆盖 | 权重和=1 `test_recommendations_precompute.py:71` / 无负现金 `test_execution_multi_account.py:254` / 账户源单一 `test_account_source_unification.py` / Master 兼容 `test_regime_adaptive_b015_backwards_compat.py` / 防守 shares×市价 `test_defensive_ticket_fidelity.py:22` | **上提到 acceptance 层**（用 golden 跑）|
| backend DB fixture | `workbench/backend/tests/conftest.py`（`initialised_db` L57，SQLite+alembic）| backend acceptance 复用 |
| CI 接入 | `python-ci.yml`（trade `testpaths=["tests"]`）+ `workbench-backend.yml`（`pytest tests/unit`+`tests/safety` 分 step）| 加 `tests/acceptance` 显式 CI step |
| branch protection doc | `docs/dev/branch-protection-guidance.md`（advisory，缺 AI Safety Eval）| Phase 0 更新 + 标 required 缺口 |

---

## 2. Feature 拆解（5 features：4 generator + 1 codex）

### F001 — Phase 0 门禁确权（executor: generator）

1. 审计 7 workflow，**坐实** L1 全门禁(pytest/mypy/ruff 后端+trade、vitest/tsc/eslint)+ safety(tests/safety)+ ai-safety-eval 都在 CI/PR 跑 → 产「确权报告」(`docs/dev/` 或更新 roadmap §1)，结论=**Codex verifying 复跑 L1 冗余,可跳 L1 直入 L2**。
2. **补缺口**:`branch-protection-guidance.md` required-checks 清单加 `AI Safety Eval`;点明 path-scoped workflow 下 "required" 语义(无关 PR 该 check 不出现)。
3. **★用户动作交接**(agent 不改仓库设置):明确列出"用户需在 GitHub branch protection ruleset 里把哪些 checks 设 required"(python-ci / workbench-backend / workbench-frontend / ai-safety-eval)。

**Acceptance：** 确权报告入 git（7 workflow 各跑什么 + required 缺口 + 用户待设清单）;branch-protection-guidance.md 补 AI Safety Eval。Gates：门禁绿（纯 doc+审计，无代码）。

### F002 — golden 真数据集（committed fixture）（executor: generator）

1. 冻结**真实** Tiingo 价格 + SEC 基本面**子集**为 committed fixture：`data/fixtures/golden/`（**必须 `data/fixtures/**` 下**才 commit;`data/snapshots/` 被 ignore）。
2. 体量裁到 **<5MB**（~10-30 ticker × **2019-2023**，覆盖 **2020 COVID + 2022 熊市**危机窗，供 regime/危机断言）;schema **严格匹配** `PRICES_REQUIRED_COLUMNS` + `FUNDAMENTALS_REQUIRED_COLUMNS`（零改 loader）。
3. README 标**真实来源 + 冻结日期 + 用途 + 不可重生成性**（区别于 synthetic `_generate.py` fixture）;若可，附冻结脚本（从真 snapshot 裁，非生成）。
4. 更新 `workbench-testing-strategy.md`：golden 真数据是 fixture-first 的**正式补充**（CI 可跑确定性真数据断言，不碰真线）。

**Acceptance：** `data/fixtures/golden/` committed（<5MB，真实数据，含 2020/2022 窗，schema 匹配）;README 诚实标源。Gates：门禁绿;golden 文件 git-tracked 可验。

### F003 — 数据源注入 + CI 确定性回测/推荐（executor: generator，触 trade/）

1. **补注入 seam**:`trade/data/loader.py` + `engine.py:run_backtest` 加 `fixture_dir` 透传（对齐 us_quality_universe）;master/per-strategy 回测 + precompute 评分能吃 golden。
2. **确定性断言**:CI 用 golden 跑 Master 回测 + ≥2 per-strategy 回测 + 推荐评分 → **同输入同输出**（committed 数值快照/范围断言）。
3. **★核心反例**（B050，现 CI 无覆盖）:N 策略同时段 golden 数据跑 → **结果两两不同且各非退化**（pairwise-distinct 永久断言）。
4. mypy trade（环境.md）+ ruff 目录上下文。

**Acceptance：** golden 数据经 fixture_dir 注入 master/per-strategy/precompute 跑出**确定性结果**（重跑 bit-identical）;★N 策略 pairwise-distinct 断言通过。Gates：backend+trade pytest/ruff 目录上下文/mypy CI-exact 0。

### F004 — 验收即代码（tests/acceptance/ + 复发不变量永久回归 + CI step）（executor: generator）

1. **建 acceptance 层**:trade `tests/acceptance/`（纯引擎，无 DB，用 golden）+ backend `workbench/backend/tests/acceptance/`（DB/推荐链，复用 `initialised_db`）。
2. **复发不变量上提为永久 acceptance**（用 golden 跑）:① ★N 策略两两不同(F003 核心) ② 权重和=1（含 cash buffer）③ 无负现金 ④ 账户源单一 ⑤ Master 向后兼容 ⑥ 防守 shares×市价≈equity。
3. **显式 CI step**:`python-ci.yml` 加 `pytest tests/acceptance`;`workbench-backend.yml` 加 `pytest tests/acceptance -q`（trade/** 改动触发）。
4. **流程约定**:`testing-strategy.md` / 角色规范记「每批 Generator/独立 agent 写本批新颖 L2 检查为 acceptance 断言」（验收即代码常态化）。

**Acceptance：** `tests/acceptance/` 两处建成 + 6 复发不变量永久断言（用 golden）;CI step 显式接入;故意破坏任一不变量 → 对应 acceptance 红（有牙齿）。Gates：CI step 绿 + acceptance 全过。

### F005 — Codex 验收 + signoff（executor: codex）

**元批次验收（确认基建真能减负 evaluator）：**
- L1 全门禁。
- **★mutation-style 核「acceptance 有牙齿」**:故意改坏每条不变量（如权重和改 1.1 / N 策略喂同数据 / 防守 shares=equity）→ 对应 acceptance **必须红**（证明测试真抓回归，对冲桶 D 盲点 roadmap §4.1）。
- **golden 确定性**:CI 同输入同输出（重跑 bit-identical，无随机/无真网络）。
- **门禁确权**:确认 F001 报告属实（L1 复跑冗余）+ required 缺口已标。
- 零回归;research-only 边界不破;CI step 真接入(PR 触发可见)。
- signoff 含「本批起,evaluator verifying 可跳 L1 复跑、复发不变量由 acceptance CI 守、只审新颖/模糊残留」的流程确认（守铁律 4 独立性）。

---

## 3. 状态流转 + 不变量 + 诚实边界

- 混合批次：`planning → building(F001→F002→F003→F004) → verifying(F005) → done`。
- **诚实边界（roadmap §4，不该全自动化的）**:① **铁律 4 独立性 ≠ 测试执行**——acceptance 断言由 Generator 写又在 CI 跑会放回"测试与 bug 同向错"盲点 → 故 F005 mutation-check + 保留独立对抗评审(面积缩到新颖/模糊);② 新颖验收的"设计"无法自动化(CI 跑检查非发明检查);③ 真金生产判断、裁定、框架沉淀仍是人/独立 agent 判断。**本批只下沉"复发不变量 + 确定性真数据回归",不碰这些。**
- **不变量**:① 生产/B067/Master/A股 进攻 零回归(golden 只进测试,不碰生产数据路径);② golden 数据**只在 fixture seam**(data_root/unified 真数据路径不变);③ research-only / no 真网络 in CI;④ §12.10.2 / ruff 目录上下文 / mypy CI-exact;⑤ 现有 fixture-first 测试不破(golden 是补充非替换)。
