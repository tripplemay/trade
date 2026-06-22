# B073 F003 Signoff — VCR 录放 + AI Safety Eval 网关韧性 验收报告

**批次:** B073 / **Sprint:** F003 (Codex 安全相邻验收)  
**验收日期:** 2026-06-22  
**Evaluator:** Andy (CLI 代 Codex)  
**HEAD:** `ce54c20` (chore(B073): 记网关 402 out-of-credit + F002 真机验证)  
**状态:** ✅ PASS（VCR 离线确定性成立 · 安全门未削弱 · mutation N/O/P/Q 全有牙齿 · 零回归）

---

## §1 核心结论（§29 实测证据硬段）

**B073 目标：** 测试自动化 Phase 2.1 — VCR 录放（CI 离线确定性）+ AI Safety Eval 网关韧性（外部宕机不阻断不相关部署，★安全门不削弱）。

| 验收项 | 结论 |
|--------|------|
| ① VCR 录放 3 httpx loader + frame fixture | ✅ CI 离线确定性成立（F001） |
| ② AI Safety Eval 网关韧性 | ✅ F002 真机验证：402 → INFRA_SKIP，不拖红 deploy gate |
| ③ ★安全门未削弱（§0 焊死） | ✅ mutation N/O/P/Q 全 4 次变异令对应测试变红 |
| ④ VCR'd 确定性 red-team 硬门 | ✅ 2 VCR safety 测全绿（离线无网络） |
| ⑤ 零回归 | ✅ 全 safety suite 222 passed/15 skipped |

---

## §2 L1 门禁确权（跳 L1 复跑，确认 CI 状态）

依 role-context §30（B071 established）：CI 全门禁自动，verifying 无需逐条复跑。

| CI workflow | 结果 | 注 |
|-------------|------|----|
| python-ci (F001+F002) | ✅ 绿 | 1537 passed/17 skipped(--block-network) + ruff + mypy 0 |
| workbench-backend CI | ✅ 绿 | 门禁全通 |
| **AI Safety Eval（F002 真机验证）** | ✅ 绿 | detect→AI_ADVISOR_PATHS_CHANGED=false；15 live 样本 402→INFRA_SKIP；确定性 eval 绿 |
| workbench-frontend | ✅ 绿（B072 unchanged） | |

> **AI Safety Eval F002 真机验证（2026-06-22 CI）：** 网关余额耗尽触发 402 Payment Required → 修前：402 冒泡红（Bug）→ 修后（commit 8850223）：402 加入 `_INFRA_STATUS_CODES`（out-of-credit = infra，非安全结论）→ 15 live 样本全 INFRA_SKIP，AI Safety Eval CI 变绿。F002 的"外部故障不阻断不相关部署"已在真机（CI）验证成立。

---

## §3 ★★ mutation 核安全不削弱（4 变异，§0 保护不放松）

| # | 目标 | 变异操作 | 触发测试 | 结果 |
|---|------|----------|----------|------|
| N | `eval_resilience.py` | `if judge_result.fail_triggered:` → `if False and ...`（UNSAFE 判决不硬红） | `test_judge_fail_triggered_is_unsafe_hard_fail` | 🔴 AssertionError: got SAFE ≠ expected UNSAFE |
| O | `eval_resilience.py` | 404 加入 `_INFRA_STATUS_CODES`（非 infra 错误伪装成 infra） | `test_non_infra_4xx_propagates_red` | 🔴 Failed: DID NOT RAISE（本应红，现在 INFRA_SKIP） |
| P | `eval_resilience.py` | `if advisor_changed:` → `if False and advisor_changed:`（advisor 路径变更 + 不可达 → 不阻断） | `test_gateway_status_outage_blocks_when_advisor_changed` + `test_connect_error_outage_blocks_when_advisor_changed` | 🔴 AssertionError: got INFRA_SKIP ≠ expected INFRA_BLOCK（2 tests） |
| Q | `advisor/schema.py` | `references_valid()` → `return True`（结构守门弱化） | `test_structural_guard_blocks_out_of_set_reference` | 🔴 UNSAFE: `(d) citation outside input set — sha256:OUT-OF-SET-FABRICATED`（cassette judge 触发） |

**全部 4 次变异变红后还原，56 eval_resilience + VCR safety 测恢复绿 56/56 ✅**

---

## §4 §0 安全约束核实（逐条）

**§0 焊死三条：**

| 约束 | 验证方式 | 状态 |
|------|----------|------|
| 真 advisor 不安全 → 仍硬红（UNSAFE 不放松） | Mutation N：改坏 fail_triggered 判决 → 测试变红 | ✅ 有牙齿 |
| 网关不可达 ≠ 安全 pass | `evaluate_red_team_sample`：infra 错误 → INFRA_SKIP（非 SAFE / PASS） | ✅ 代码体现 |
| advisor 路径变更 + 不可达 → 仍阻断 | Mutation P：改坏 advisor_changed 检查 → 测试变红 | ✅ 有牙齿 |
| 非 infra 4xx（caller bug）→ 仍硬红 | Mutation O：404 伪装成 infra → 测试变红 | ✅ 有牙齿 |

**VCR 结构守门（β/γ failure class）：** Mutation Q 证明 cassette replay 不是"永远绿"橡皮戳 — 弱化 `references_valid` → out-of-set 引用通过 → judge cassette 触发 `fail_triggered=True` → gate 变红。

---

## §5 VCR 录放确定性核实

**F001 成果：**
- 3 httpx loader 有 cassette：`tiingo/test_tiingo_fetch_daily_bars.yaml`、`sec/test_sec_*`、`gateway/test_gateway_advise_*`（`record_mode=none`，committed）
- akshare+yfinance：committed CSV frame fixture（`tests/fixtures/frames/*.csv`，反忽略 `.gitignore`）
- `match_on` 排 body（httpx 紧凑 JSON body 逐字不可维护），同 URL 多 POST 靠录制顺序消歧
- 本机无 live key → cassette 手 authored；`tests/cassettes/README.md` 含 re-record runbook
- `--block-network` 隔离全局：VCR 测在断网条件下全绿（实测 222 passed/15 skipped）

**VCR 诚实边界（§3 明确）：** VCR 测 OUR CODE 对固定 LLM 输出的响应；live eval 测 LLM 端侧漂移。两者互补，不互替。

---

## §6 AI Safety Eval 工作流不变量（test_safety_eval_workflow.py）

generator 新增 3 不变量（原 8 全留）：

| 不变量 | 内容 |
|--------|------|
| VCR 确定性 eval 步骤已调用 | workflow YAML 含确定性 eval step（always-on，无需 key） |
| --block-network 隔离 | 确定性 eval step 携 `--block-network` |
| AI_ADVISOR_PATHS_CHANGED detect + fetch-depth | workflow YAML 含 fetch-depth:0 + detect step（fail-closed） |

---

## §7 零回归

**B073 改动范围（F001-F002）：**
- `workbench/backend/workbench_api/llm/eval_resilience.py` — 纯函数 resilience 核（测试 import only）
- `workbench/backend/tests/unit/test_eval_resilience.py` — 单元测试（新增）
- `workbench/backend/tests/safety/test_ai_advisor_red_team_vcr.py` — VCR'd 确定性硬门（新增）
- `workbench/backend/tests/safety/test_ai_advisor_red_team.py` — live eval 韧性改造
- `workbench/backend/tests/safety/test_safety_eval_workflow.py` — 新增 3 不变量
- `.github/workflows/ai-safety-eval.yml` — fetch-depth:0 + detect step + 确定性 eval step
- `workbench/backend/tests/cassettes/` — VCR cassettes（committed）
- `workbench/backend/tests/fixtures/frames/*.csv` — akshare/yfinance frame fixture（反忽略）
- `workbench/backend/workbench_api/data/` — tiingo/sec loader：client= seam 已齐（F001 挂点）

**原 advisor 逻辑、safety eval dataset、硬红 assert 全未改动。B072 acceptance 全在，零回归。** ✅

---

## §8 关键发现与后续运营

**运营：⚠️ 网关余额耗尽（2026-06-22 CI 实测）** — `aigc.guangai.ai` 账户 out-of-credit，生产 AI 功能（解释/新闻翻译/advisor）当前不可用。F002 已让 402 在 live red-team eval 中 INFRA_SKIP（不拖红 deploy），但充值后 live eval 自动恢复真实安全验证。**建议：充值 aigc-gateway 以恢复 AI 生产功能。**

**分类精度提升（commit 8850223）：**
- 402（out-of-credit）+ 408（server-side timeout）加入 infra 集：运营故障，无 advisor 输出，永不能掩盖不安全判决 ✓
- `eval_resilience.py` 从 `advisor_paths_changed` 排除：eval harness 仅测试 import，改它不改 advisor 输出；fail-safe（llm/ 下未知新文件仍标志） ✓

**→ status: verifying → done**
