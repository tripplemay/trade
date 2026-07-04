# B080 — 策略生命周期监控 + 试验登记簿 + 冻结式再验证 — Verifying 首轮报告（F005）

**批次：** B080-strategy-lifecycle-monitoring（混合批次 4 generator + 1 codex）
**验收人：** 独立 Evaluator（代 Codex，用户 /goal 授权；铁律 4 实质独立——无实现上下文，一切以仓库现状 + 真机为准）
**日期：** 2026-07-04
**阶段：** verifying（首轮）→ **裁定 FIXING**
**结论：⚠️ 1 项实质阻断（BLOCKING）+ 其余全部 PASS**

> **与前一份报告（`...signoff-2026-07-03.md`，提交 `8507e32`）的关系：** 前轮 evaluator 因**无 VM SSH 密钥**，把**全部 L2 真机检查显式 defer**（该报告 §4 自陈「timer list-timers / 鉴权数据抽查 / 面板截图 / 长任务端到端——未跑」），仅凭 L1 + 代码走查给出 PASS 建议。本轮我具备 VM 访问权，**实际执行了被 defer 的真机检查**，据此发现前轮盲区里的一个生产落地缺口。前轮 L1 + 代码走查结论我独立复核后仍成立；本报告在其基础上补齐 L2 真机证据并修正裁定。

---

## 0. 裁定摘要

**FIXING（1 BLOCKING）。** B080 的代码实现（F001–F004）L1 全绿、安全不变量三重守门成立、绝大多数交付在生产真机实测通过。**唯一阻断项：F001 的 trial_registry 历史回填（≥27 条，spec 与团队 L2 清单均硬性要求）在生产为 0 行，且无任何自动路径会填充它**——因为回填仅由手动 `workbench-bootstrap` CLI 落库、未接入自动部署链，B080 部署后从未在生产执行。这不是代码 bug（回填常量 27 条本地已证正确），而是**部署完整性缺口**：功能"已部署"的声明与生产现实不符，且该缺口不会自愈。

---

## 1. L1 门禁（本地抽查，全绿）

后端 python = `workbench/backend/.venv/bin/python`（3.11.15，已 `pip install ../..` 装 trade）。

| 门禁 | 结果 |
|---|---|
| safety + B080 单测子集 | ✅ `223 passed, 15 skipped`（15 skip = `test_ai_advisor_red_team` 需 `AIGC_GATEWAY_API_KEY`，非 B080）|

子集覆盖：`tests/safety/`（含 `test_reverify_frozen_params` / `test_monitoring_request_self_contained` / `test_market_scheduler_scope`）+ `test_trial_registry` / `test_oos_verification_card` / `test_monitoring_compute` / `test_monitoring_cpcv` / `test_monitoring_job` / `test_monitoring_route` / `test_reverify_landings` / `test_reverify_runner` / `test_reverify_job_repo` / `test_paper_base_currency` / `test_paper_benchmark` / `test_cn_attack_signal_scores` / `test_bootstrap_cli`。CI 全绿由前置流程确认；本轮聚焦新颖 L2 真机面 + 独立对抗复核（evaluator §30）。

---

## 2. L2 真机（VM 严格只读实测，`ssh tripplezhou@34.180.93.185`）

真库 = `/var/lib/workbench/db/workbench.db`（19MB，deploy:deploy，07-04 04:34 更新；`trade.db` 为 0 字节空壳）。sqlite 全程 `file:...?mode=ro`。

| # | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | **HEAD≡prod** | ✅ PASS | 生产 release symlink → `releases/46ba83b…`（= 最后一个产品代码提交 F004）。其后 3 提交 `799075f`/`0436009`/`8507e32` 仅动 features/progress/docs/framework/.auto-memory（paths-ignore，不部署）。等价成立。|
| 2 | **timer 装载 + 显式 TimeoutStartSec** | ✅ PASS | `systemctl list-timers` 见 `workbench-monitoring.timer`（NEXT Mon 2026-07-06 05:00 UTC，周频）+ `workbench-reverify.timer`（NEXT Thu 2026-10-01 06:00 UTC，季频 Jan/Apr/Jul/Oct-01）均已装载，07-04 06:15 部署。`monitoring.service` `Type=oneshot`+`TimeoutStartSec=1800`+`ExecStart=… -m workbench_api.monitoring.cli`；`reverify.service` `TimeoutStartSec=300`+`ExecStart=… -m workbench_api.monitoring.reverify_cli`。两 service 均 systemd 硬化（NoNewPrivileges/ProtectSystem=strict/ReadWritePaths 限定）+ 引用 `test_market_scheduler_scope.py` grep 守门。|
| 3 | **监控指标真数据合理性** | ⏸️ 诚实 defer（非阻断）| 生产 `monitoring_metric` = **0 行**——周频 job 尚未首跑（NEXT 07-06，LAST=n/a）。**无 API 值可供手工 IC 交叉对照**。按团队约定退回本地测试 DB 验证计算路径：`test_monitoring_compute`（IC 纯函数，迁自已单测的 `b077_signal_first_look`）+ `test_monitoring_cpcv` + `test_monitoring_job` 全 PASS，数学与编排路径可跑。IC 面板首个真值将于 07-06 周频 job 后产生。如实标注：本项数学正确性有 L1 证据、生产真值待 07-06（该 job 已装载+计划，会自愈）。|
| 4 | **再验证 pipeline** | ✅ PASS（控制面+内核+守门）；长任务未触发（故意）| 控制面：timer/service/状态表（reverify_job）/触发 API 均在生产。内核对抗核验（见 §3）：参数完全冻结 + 无 validated→True。**未在生产实际触发** baostock 长任务（~30-40min + 写研究目录）——评估者判断：避免干扰生产数据目录，改本地守门（`test_reverify_frozen_params` / `test_reverify_landings` / `test_reverify_runner` 全 PASS）。生产侧只验证控制面存在。|
| 5 | **红卡 DB 化零回归** | ✅ PASS | 生产 `oos_verification_card` = **2 行**（`cn_attack_pure/quality_momentum`），`validated=0`、`oos_cagr_range="-9% ~ -11%"`、`oos_result=negative`、`source=seed`（迁移 0028 `op.bulk_insert` 落地）。最新 cn_attack（07-03 快照）`master_meta.research_caveat` 与 B079 时代硬编码**语义逐字一致**：`{validated:false, oos_result:"negative", oos_cagr_range:"-9% ~ -11%", headline_zh/en, detail_zh/en, backtest_ref}`。无行 fallback byte-identical 由本地单测焊死。|
| 6 | **trial registry 回填** | ❌ **BLOCKING** | 生产 `trial_registry` = **0 行**（spec F001 要求 ≥15，团队 L2 清单要求 ≥27）。详见 §3。|
| 7 | **paper 三口径** | ✅ PASS | 生产 `paper_account.base_currency`：`cn_attack_pure/quality_momentum` = **CNY**，`master_portfolio`/`regime_adaptive` = **USD**（迁移 0032 精确命中两 cn_attack id，master 零回归）。per-strategy benchmark 映射在代码（cn_attack→CSI300 / master·regime→SPY 不变，守门单测 `test_paper_benchmark` 断言 master 走 byte-identical SPY 路径）。首日 caveat 为 annotation-only（不重算 NAV）。|
| 8 | **/monitoring 面板 no-execution** | ✅ PASS（代码走查）| `src/app/(protected)/monitoring/page.tsx` 存在；页 + `components/monitoring/` grep 无 execute/order/buy/sell/下单/券商/broker/ticket 交易 affordance；reverify 触发钮走 `runReverify`（研究 pipeline，非交易）。e2e 守门 `tests/e2e/b080-monitoring.spec.ts` 在（CI 内断言交易 testId count=0）。截图未做（需登录态；结构由代码 + CI e2e 覆盖，如实标注）。|
| 9 | **零回归 + B079 soft-watch** | ✅ PASS，**B079 soft-watch 关闭** | safety 子集全绿；F002 `signal_scores` 前向积累在生产实测（07-03 快照 `master_meta.signal_scores` PRESENT(519 chars)、07-02 及更早全 NULL——正是"本批起前向积累"预期行为）。**B079 soft-watch：生产 `symbol_name` 现 5203 行（source=akshare_spot）**，07-04 01:30 日刷已落库全市场 A股名（正如 B079 预测）；最新 cn_attack pure 快照标的**25/26 已解析中文名**（001309.SZ→德明利 / 002384.SZ→东山精密 / 300308.SZ→中际旭创 …）→ **soft-watch 关闭**，B080 未破 B079 enrich 路径。|

---

## 3. BLOCKING 详解 — F001 trial_registry 历史回填生产缺失

**现象（生产真机只读）：**
```
sqlite> SELECT COUNT(*) FROM trial_registry;   →  0
```
spec §2 F001 acceptance 明写「幂等 seed 回填 **≥15 条**历史试验」；团队 L2 清单第 6 项明写「生产表行数（**应≥27**）」。生产 = 0，两项均不满足。

**根因（部署链非对称）：**
- **oos_verification_card**（同属 F001 红卡 DB 化）走**迁移 0028 `op.bulk_insert`** → `deploy.sh` 的 `alembic upgrade head` 自动落地 → 生产有 2 行 ✅。
- **trial_registry 回填****不在迁移里**（`0029_b080_trial_registry.py` docstring 明写「the historical backfill is seeded idempotently by `workbench-bootstrap` … neither belongs in a migration」；回填数据在 `cli/bootstrap.py::_import_trials` 从 `HISTORICAL_TRIALS` 常量落库）。
- **`workbench-bootstrap` 不在自动部署链**：`deploy.sh` 只跑 alembic（全文无 bootstrap CLI 调用）；`workbench-deploy.yml` 无 seed 步骤；无 systemd bootstrap unit；B021/B022 spec 明确 bootstrap 是「one-off CLI，first deploy 时手动跑一次」。B080 部署后**从未在生产重跑 bootstrap** → 回填未落库。

**佐证（bootstrap 自 B079 起从未重跑）：** 生产 `account_snapshot` = 7 行（bootstrap 很久前跑过一次的遗留），但 **`symbol_name` 中 curated（source≠akshare_spot）= 0 行**——即 B079 F001 的 curated 名 seed（`bootstrap.py:169`）也从未落生产（B079 靠进程内 `CURATED_SYMBOL_NAMES` 兜底才未暴露）。这说明是**系统性部署完整性缺口**：凡由 bootstrap seed 的数据（B079 curated 名、B080 trials）均静默不落生产。

**为何是 BLOCKING 而非 soft-watch：**
1. **不会自愈**：monitoring_metric（周 timer 07-06）、reverify（季 timer 10-01）都有计划任务会自动填充——是合法 soft-watch。trial 回填**没有任何调度器会填它**，永远停在 0，直到有人手动 bootstrap。「永不解决的 soft-watch」= 未闭环缺口。
2. **spec + 团队清单双硬性要求**生产落地，双双不满足。
3. **空的 N 反而更误导**：`trial_backfill.py` docstring 自陈回填目的是「the honest starting N, not an invented one」（DSR 需要 N）。生产 `/monitoring/trials` 返回 0、DSR 算出 N=0——27 个真实 config 试过却显示"从未试验过"，比没有登记簿更危险。
4. 代码本身正确（本地实证 `len(HISTORICAL_TRIALS)==27`，覆盖 B063×3/B066×6/B068×4/B070×2/B075×2/B076×8/B077×2；前轮已逐字核对 3 条对 signoff 原文一致）——缺的只是"在生产执行 seed"这一步。

**修复建议（供 generator/planner 裁量）：**
- **即时**：在生产幂等执行 `workbench-bootstrap`（`_import_trials` 用确定性内容 id upsert，re-run 为 no-op，安全），落库 27 条。
- **治本（防复发，强烈建议）**：把 bootstrap 的幂等 seed 接入 `deploy.sh`/部署 workflow（一并修复 B079 curated `symbol_name` 同源缺口），**或**将 trial 回填改为 data-migration 随 alembic 自动部署（与 oos card 同款自动落地机制，消除手动步骤）。
- **re-verify 判据**：生产 `SELECT COUNT(*) FROM trial_registry` ≥ 27，且抽 3 条对 signoff 原文精确一致。

---

## 4. 安全不变量（专项，对抗核验——独立复核成立）

- **不变量②「pipeline 永不自动摘红卡」— ✅ 已证。** 独立 grep `workbench_api/` 全量：`validated=True` / `"validated": True` 仅命中 3 处 **docstring 注释**（`oos_verification_card.py:7` model+repo、`reverify_landings.py:5`），**无任何代码写路径**。实际卡片写路径 `reverify_landings.py:59` 硬编码 `"validated": False`（非从 payload 派生）。AST 守门 `test_reverify_frozen_params::test_reverify_modules_never_set_validated_true` + 运行时 `test_reverify_landings::test_positive_revalidation_never_validates_card`（即使 PIT 结果为正，卡片仍 `validated=False`）本地 PASS。
- **参数冻结 — ✅ 已证。** `run_frozen_revalidation` 签名无可调参数、只读 FROZEN_* 常量；守门单测注入参数→拒绝，PASS。
- **Master paper 零回归 — ✅ 已证。** 生产币种 master=USD、benchmark 映射 master=SPY（守门单测断言 byte-identical SPY 写路径）；signal_scores 为纯加 meta 键。
- **CPCV-lite 诚实标注 — ✅。** 代码含 `CPCV-lite: K=4 quarter-staggered OOS + 1mo purge (not full CPCV)` 标签。

---

## 5. 最终裁定

**FIXING。** B080 代码实现质量过硬——L1 全绿，四条安全不变量（无 validated→True / 参数冻结 / Master 零回归 / no-execution）经 grep + AST + 运行时 + git-diff 四重对抗核验成立，红卡 DB 化 / paper 三口径 / signal_scores 前向积累 / timer 装载均在生产真机实测通过，B079 soft-watch 一并关闭。

**唯一阻断**：F001 的 trial_registry 历史回填（27 条，spec 与团队 L2 清单硬性要求）在生产缺失且不会自愈——根因是回填只走手动 `workbench-bootstrap`、未接入自动部署链。此项须修复（生产落库 27 条 + 治本接入部署链/改 data-migration）后复验方可 done。

**状态机动作：** `progress.json` status → **fixing**，`evaluator_feedback` 填 summary + issues[]（定位到文件与复现），`fail_count=1`；`features.json` F001/F005 标注。

---

*验收产物：本报告。未改任何产品代码 / 除状态机外的文件。所有数字为 VM 只读实测 + 本地实跑快照。*
