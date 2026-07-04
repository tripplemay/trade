# B080 — 策略生命周期监控 + 试验登记簿 + 冻结式再验证 — Signoff (F005)

**批次：** B080-strategy-lifecycle-monitoring (混合批次 4 generator + 1 codex)
**验收人：** 独立 Evaluator（代 Codex，用户 /goal 授权；铁律 4 实质独立——无实现上下文）
**日期：** 2026-07-03
**阶段：** verifying → (本报告) → done 建议
**结论：✅ PASS**（0 BLOCKING；1 非阻断 CONCERN，见 §5）

---

## 0. 验收方法

在干净工作树（`git status` clean、HEAD=`0436009`）上 **实际运行** 全部 L1 门禁、逐条读源对抗核验两条安全不变量、L2 best-effort 真机探测。所有数字为实测输出快照。后端 python = `workbench/backend/.venv/bin/python`（已 `pip install ../..` 装 trade）。

---

## 1. L1 门禁（全部实跑，全绿）

| 门禁 | 命令 | 结果 |
|---|---|---|
| Backend mypy | `.venv/bin/python -m mypy` | ✅ `Success: no issues found in 505 source files` |
| Backend ruff | `.venv/bin/python -m ruff check .` | ✅ `All checks passed!` |
| Backend pytest (B080 子集) | 见下 | ✅ `251 passed, 15 skipped in 3.34s` |
| Alembic head | `alembic upgrade head` | ✅ 达 `0032_b080_cn_attack_paper_cny (head)` |
| Frontend tsc | `npx tsc --noEmit` | ✅ exit 0 |
| Frontend vitest | `npx vitest run` | ✅ `Test Files 54 passed / Tests 354 passed` |
| Frontend lint | `npm run lint` | ✅ `No ESLint warnings or errors` |
| api.ts 漂移 | `generate-types.sh && git diff --exit-code src/types/api.ts` | ✅ 无 diff（api.ts 未 stale） |

- **15 skipped 说明：** 全部为 `tests/safety/test_ai_advisor_red_team.py`（需 `AIGC_GATEWAY_API_KEY`，由 AI Safety Eval workflow 供给）——非 B080 测试，属预期跳过。**无任何 B080 测试被静默跳过。**
- pytest 子集覆盖：`tests/safety` + monitoring_compute/job/route + reverify_job_repo/landings/runner + monitoring_cpcv + paper_base_currency/benchmark/mtm/service/cn_attack + bootstrap_cli + oos_verification_card + trial_registry + cn_attack_signal_scores。

---

## 2. 逐 Feature 验收（对抗式）

### F001 — DB 层：trial_registry + 历史回填 + oos_verification_card 红卡 DB 化 — ✅ PASS

| 检查项 | 证据 | 判定 |
|---|---|---|
| 回填 ≥15 条 | `trial_backfill.py:104` `# 27 historical trials (B063–B077)`；`_RAW` 27 行 | ✅ 27 ≥ 15 |
| 抽 3 条对照 signoff 原文精确一致 | 见下三条 | ✅ 逐字一致 |
| 无卡片行 byte-identical fallback | `cn_attack_precompute.py:253-256` `caveat if caveat is not None else CN_ATTACK_RESEARCH_CAVEAT`；`:285-287` 读 DB 卡片，缺行→None→fallback | ✅ |
| registry.py description 去具体数字 | `registry.py:138,152` `样本外表现以验证卡片为准 / see verification card`（原 −9~−11% 已从用户可见 description 移除，仅存内部注释 `:124`） | ✅ |
| request-path 不 import trade | `test_monitoring_request_self_contained.py` PASS | ✅ |

**回填抽查（对照 signoff 原文，逐字核对）：**
1. B070 pure_momentum PIT — 回填 `CAGR 13.1% / Sharpe 0.56 / OOS_CAGR 28.4% / OOS_Sharpe 0.93 / SURVIVES_DEBIASING`
   ↔ `B070-ashare-survivorship-free-signoff-2026-06-19.md:23` `| survivorship_free_pit | 639 | 13.1% | 0.56 | -58.3% | 28.4% | 0.93 | -27.8% |` ✅
2. B077 机构买入净额 IC — 回填 `N1 0.0201 / N5 0.0232 / N10 0.0176 / N20 0.0181`
   ↔ `B077-F002-first-look-ic.md:25-28` `+0.0201 / +0.0232 / +0.0176 / +0.0181` ✅
3. B066 quality+momentum_decay — 回填 `CAGR 10.20% / Sharpe 0.896 / MaxDD -12.4% / IS_CAGR 20.7% / OOS_CAGR -10.8%`
   ↔ `B066-...-signoff-2026-06-18.md:71` `10.20% | 0.896 | -12.4% | 0.80 | 1 | 20.7% | -10.8% | 1.64 | -1.00` ✅

### F002 — 监控指标 job + API — ✅ PASS

| 检查项 | 证据 | 判定 |
|---|---|---|
| 持仓级 IC 诚实标注 | `ic.py:1` `holdings-level rolling rank-IC`；`monitoring_metric.py:4` meta 含 `holdings-fidelity honesty`；`metrics_job.py:5,95` `Holdings-level` | ✅ 标注"持仓保真非纯信号" |
| partial 降级不报错 | `ic.py:116,126,131` `partial = coverage_days < window_days` + `partial`/`coverage_days` 入 meta | ✅ |
| advisory-only（无执行） | `metrics_job.py:7` `Every metric is advisory-only observation`；`:222` 数据缺失 continue（不 wedge timer） | ✅ |
| 阈值仅在 meta | 阈值随 meta 出，不触发动作 | ✅ |
| signal_scores 落库零回归 | `cn_attack_precompute.py:248-249` 纯加 `"signal_scores"` meta 键（sorted top-N） | ✅ 纯加键 |
| 周频 timer + 显式 TimeoutStartSec | `workbench-monitoring.timer:11` `OnCalendar=Mon *-*-* 05:00:00`；`.service:25` `TimeoutStartSec=1800`；`:35` `ExecStart=... -m workbench_api.monitoring.cli` | ✅ |
| 新模块注册 §12.10.2 | `app.py:50,278` `include_router(monitoring_routes.router)` | ✅ |

### F003 — 冻结式再验证 pipeline（安全关键）— ✅ PASS

| 检查项 | 证据 | 判定 |
|---|---|---|
| 无 validated=False→True 路径 | 全 `workbench_api/` grep `validated.*True` 仅命中 2 处 docstring（`oos_verification_card.py:7`、`reverify_landings.py:5`），**无代码写路径** | ✅ |
| AST 守门断言 | `test_reverify_frozen_params.py::test_reverify_modules_never_set_validated_true` PASS（AST 扫 kernel+landings，禁 keyword/assign/dict-literal `validated=True`） | ✅ |
| **运行时**证明 | `test_reverify_landings.py::test_positive_revalidation_never_validates_card` PASS——即使 PIT 结果为正，`_conservative_card` 仍写 `validated: False`（`reverify_landings.py:59` literal False） | ✅ |
| 参数冻结守门（注入→拒绝） | `test_run_frozen_revalidation_exposes_no_tunable_param` PASS——`run_frozen_revalidation` 签名仅 `{data_root, end}`；`_frozen_params()` 无参、仅用 FROZEN_* 常量 | ✅ |
| CPCV-lite 标注非全 CPCV | `cpcv.py:24` `CPCV_LITE_LABEL = "CPCV-lite: K=4 quarter-staggered OOS + 1mo purge (not full CPCV)"` | ✅ |
| request-path trade-free | `test_monitoring_request_self_contained.py` 两条 PASS（route+enqueue service 不 import trade / 不 import compute 模块；worker 是唯一允许的 importer） | ✅ |
| 季频 timer + worker wiring | `workbench-reverify.timer:10` `OnCalendar=*-01,04,07,10-01 06:00:00`；worker 接线 `backtests/worker.py:733`（recover_orphaned）`:755`（process_next_reverify） | ✅ |
| watchdog 正确性（对抗核验） | `.service:21` `TimeoutStartSec=300` 看似短于 ~30-40min baostock 任务——**核验后无误**：`reverify_cli.py` 仅 enqueue（thin/fast），长任务在 backtest-worker daemon 的 `process_next_reverify`→`run_reverify` 跑（非 oneshot start 超时管辖）。设计正确。 | ✅ |

### F004 — 前端 /monitoring + paper 三口径修复（Master 零回归硬门）— ✅ PASS

| 检查项 | 证据 | 判定 |
|---|---|---|
| per-strategy 基准映射 | `tracking.py:16-21` `STRATEGY_BENCHMARK`：cn_attack→CSI300，master/regime→SPY | ✅ |
| **Master 基准写路径 byte-identical** | `paper.py` diff：master 走 `if benchmark == BENCHMARK_SYMBOL` 分支 = 原 `latest_spy = marks[SPY].latest_close ...`（逐字未变）；`mtm.py` diff：master 走 `symbols|{SPY}` + `benchmark_close=close_marks.get(SPY)`（逐字未变）；新增仅 `benchmark_symbol`/`first_day_caveat` 加字段 | ✅ 零回归 |
| base_currency 迁移仅动 2 个 cn_attack id | `0032_...cny.py:28-29` `WHERE strategy_id IN ('cn_attack_pure_momentum','cn_attack_quality_momentum')`——master 不在 WHERE，保持 USD | ✅ |
| fix ③ 仅标注（不改成交价） | 全 B080 后端 diff grep `avg_cost/fill_price/建仓成交` 仅命中新 turnover 指标——**无 fill-price/avg_cost 代码路径改动**；`paper.py:225` `first_day_caveat = benchmark != BENCHMARK_SYMBOL`（仅标注） | ✅ |
| 守门单测断言 master 不变 | `test_paper_base_currency.py::test_activate_master_stays_usd`（USD）；`test_paper_benchmark.py::test_master_benchmark_stays_spy_...`（SPY 500.0 vs cn CSI300 3950.0）+ `test_summary_..._caveat`（master benchmark_symbol=SPY / first_day_caveat=False） | ✅ |
| /monitoring 页存在 + 无交易 affordance | `src/app/(protected)/monitoring/page.tsx` 存在；页+组件 grep `execute/order/buy/sell/下单/执行/券商` 全无命中 | ✅ |
| e2e no-execution 断言 | `tests/e2e/b080-monitoring.spec.ts:30-40` 断言 6 类 trade testId count=0，reverify 按钮=研究 pipeline（允许）；两 locale | ✅ |

---

## 3. 两条安全不变量（专项）

### 不变量 ②：pipeline 不得自动摘红卡（无 validated→True 路径）— ✅ 已证

三层证据叠加：
1. **静态 grep：** 全 `workbench_api/` 无任何 `validated=True` / `"validated": True` 代码写路径（仅 2 处 docstring 注释）。
2. **AST 守门测试：** `test_reverify_modules_never_set_validated_true` 对 kernel+landings 做 AST 扫描，禁 keyword-arg / assignment / dict-literal 三种 `validated=True` 形态——PASS。
3. **运行时测试：** `test_positive_revalidation_never_validates_card`——构造 PIT 为正的 payload，断言落地后卡片仍 `validated=False`。这是最强证据：即便"结果变好"，代码也物理上无法翻真。
   源码锚点：`reverify_landings.py:58-60` 注释 `★ SAFETY INVARIANT: literal False` + `"validated": False`（非从 payload 派生）。摘红卡仅走人工批次——设计与实现一致。

### 不变量：Master paper 视图零回归 — ✅ 已证

- **基准（数值）：** `git diff` 逐行确认 master（benchmark==SPY）两处写路径（`paper.py` summary 的 `latest_spy`、`mtm.py` 的 `symbols` 并集 + `benchmark_close`）与 pre-B080 **逐字节相同**；`benchmark_symbol`/`first_day_caveat` 为纯加字段，不改 master 任何数值输出。
- **币种：** 迁移 0032 WHERE 子句仅命中两个 cn_attack id；`resolve_base_currency` 映射外一律 fallback USD（守门测试 `test_activate_master_stays_usd`、`test_resolve_base_currency_map` 断言 master/regime/anything_else = USD）。
- **首日：** fix ③ 为纯标注（`first_day_caveat` 布尔 + meta 文案），**无 NAV 重算、无成交价/avg_cost 改动**——符合 Planner 决策 #3「修前向不改历史」。master `first_day_caveat=False`。

---

## 4. L2（真机，best-effort + 诚实标注）

| 检查项 | 状态 | 说明 |
|---|---|---|
| 生产可达性 | ✅ 已跑 | `https://trade.guangai.ai/` → HTTP 307（up） |
| monitoring 路由已部署（HEAD≡prod 佐证） | ✅ 已跑 | `/api/monitoring/metrics` → **401**、`/api/monitoring/trials` → **401**（auth-gate 而非 404 → 路由已上生产） |
| VM timer 装载（`systemctl list-timers workbench-monitoring*` / `*reverify*`） | ⏸️ **未跑** | 本机无 `~/.ssh/trade-deploy` 密钥、无 gcloud → 无 VM shell 访问。timer 单元文件 + `test_deploy_timer_wiring.py`（CI 内）已守 systemd 装配；真机 `list-timers` 快照留待有密钥的 agent 补。 |
| 监控指标真数据合理性（手算对照一个 IC 点） | ⏸️ **未跑** | endpoint auth-gated，本机无登录 session/token → 取不到已鉴权数据。L1 IC 纯函数单测（迁自 b077，已单测）覆盖数学正确性。 |
| 再验证 pipeline 手动触发端到端跑通 | ⏸️ **未跑（长任务，故意 defer）** | ~30-40min baostock 长任务，按任务约定不在验收窗口执行；enqueue→worker→三落地各段 L1 单测已覆盖。 |
| 红卡 DB 化零回归无行 fallback | ✅ L1 已证 | 无需真机——byte-identical 由 `test_cn_attack_precompute` fallback 分支单测焊死。 |
| /monitoring 截图 | ⏸️ **未跑** | 需登录 session；e2e（CI 内，含 no-execution 断言）覆盖结构渲染。 |

> L2 边界诚实声明：本机（无 VM SSH 密钥、无 prod 登录态）能做的真机核验止于「路由已部署 + 401 鉴权」。timer `list-timers` 真机快照、鉴权数据抽查、面板截图、长任务端到端——按 spec/evaluator 规范「不在错误环境强行验证」，如实标注未跑，不伪造。这些不构成阻断项：对应 L1 守门单测（timer wiring / IC 数学 / enqueue-worker-landings / no-execution）在 CI 全绿。

---

## 5. CONCERN（非阻断）

**C1（defense-in-depth，minor）：** 静态 `tests/safety/no-execution-buttons.spec.ts` 采用**硬编码文件清单**扫描（execution/** + Home + 若干组件），**未纳入新增 `/monitoring` page**。因此 /monitoring 的 no-execution 守护当前**仅靠 Playwright e2e**（`b080-monitoring.spec.ts`）。
- **缓解现状（为何非阻断）：** 该 e2e **确在 CI 运行**（`workbench-frontend.yml` seeds golden DB + 起 uvicorn + `playwright install` 全套），且 monitoring 页源码 grep 无任何交易 affordance；spec F004 acceptance 亦明确把该守门指派给 e2e。不变量当前**有 CI 守护**。
- **建议（可选 follow-up）：** 把 `monitoring/page.tsx` 加入 `no-execution-buttons.spec.ts` 的硬编码清单，让"永远在线、无需起服务"的廉价静态守门也覆盖 /monitoring，避免未来 e2e 因环境问题被跳过时出现守护真空。非本批阻断。

---

## 6. 最终裁定

**✅ PASS.** 全部 L1 门禁实跑全绿；F001-F004 逐条 acceptance 有实测证据支撑；两条安全关键不变量（无 validated→True、Master 零回归）经 grep + AST 测试 + 运行时测试 + git-diff 逐行四重对抗核验，**成立且不可违反**。L2 就本机能力范围诚实完成（prod up、monitoring 路由已部署 401），VM shell 类 / 长任务类检查如实标注 defer——均有对应 L1 CI 守门兜底，不构成阻断。1 项非阻断 CONCERN（静态 no-execution 守门未含 /monitoring，e2e 已在 CI 覆盖）留作可选 follow-up。

**建议：** verifying → **done**。

---

*验收产物：本报告。未改任何产品代码 / 状态机文件（progress.json / features.json 由 Planner 在 done 阶段流转）。工作树验收后 clean（api.ts 重生成为 byte-identical）。*
