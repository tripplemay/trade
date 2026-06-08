# B049 — 全页面真实化审计 gate（里程碑 C 收口）

> **批次类型：** 混合批次（3 generator + 1 codex）
> **状态：** planning → building
> **里程碑：** C 收口 gate —— 审计通过 = 里程碑 C「所有用户投资页面显示内容接真实引擎」正式达成
> **前置：** B046 / B048 / B048-OPS1 / BL-B023-S1 / BL-B011-S2 / B042 / B047 / B047-OPS1 / B047-OPS2 全 done
> **来源：** backlog.json B049（2026-06-07 用户拍板）+ progress-review-2026-06.md §9.1 覆盖矩阵 + 2026-06-09 planner 实地审计

---

## 1. 背景与目标

里程碑 C 的硬标准（2026-06-07 用户拍板）：**里程碑 C 完成时，所有用户投资页面显示内容均接真实引擎，无合成/占位。** 前序批次已逐页真实化（Home/Recommendations/Reports/Risk/Strategies 注册表/Backtest/Execution）。本批是**收口 gate**：

1. 修掉实地审计确认的 **3 个残余显示占位**；
2. 由独立 evaluator 做**全页面穷举审计** + 里程碑 C 达成裁定（= 达成证据）。

### 1.1 实地审计基线（2026-06-09 planner + Explore 核查）

审计**未发现**除以下 3 点之外的用户可见合成/占位残余：

| # | 残余 | 位置 | 性质 |
|---|---|---|---|
| 1 | Snapshots 合成进度 | `services/snapshots.py:93-110` `_iter_stages()` 5 段硬编码 + 固定 0.05s sleep；`routes/snapshots.py` docstring | 刷新进度动画是合成表演（数据已 B045 真，仅进度假）|
| 2 | Strategies 陈旧 synthetic note | `services/strategies.py:101-104`（global_etf_momentum）+ `:159-162`（us_quality）「Synthetic fixture only; not live market data / not actual filings」 | 文案陈旧（B045 已接真数据）|
| 3 | Dashboard 死路由 + 占位 | `routes/dashboard.py`（前端零页面引用）+ `services/dashboard.py:45` 第三份 kill_switch 0.20 + `:159` master_drawdown=0.0 占位 + `tests/unit/test_dashboard.py:112` 断言 0.2 陈旧 | 死服务 + 阈值副本不一致 + 占位字段 |

### 1.2 明确**不动**的诚实声明式占位（铁律：不得隐瞒真相）

以下是**正确的诚实披露**，B049 **严禁**修改（动了反而误导用户）：

- `services/strategies.py:167-171` satellite_stub「defensive placeholder. No strategy implemented yet」（hk_china 已 BL-B011-S2 实现？需核——若已实现则此条另议，见 F002 acceptance (5)）
- `services/strategies.py:218+`、`:240/:258` regime_adaptive「Research-state ... ships inactive / weight 0.0」（regime 留研究态，B046 F002 已对齐）
- 任何明确标注 `status: research` / `stub status` 的字段

---

## 2. 范围边界

**做：** 上述 3 残余的真实化/清理 + 全页面穷举审计 + 守门回归测试 + signoff。

**不做：**
- 不改 master 评分逻辑 / 5 因子 / planning weights / canonical / async worker 架构；
- 不激活 regime_adaptive（留研究态）；
- 不动诚实声明式占位（§1.2）；
- 不碰内部工具页（backlog / dev / docs —— 非用户投资内容，排除）；
- 不引入无限深回填 / 新数据源 / broker 接入；
- §12.10.2 请求路径禁 import trade、no-execution、定位 §1.1、i18n parity 等永久硬边界不破。

---

## 3. Feature 分解

| id | executor | 标题 |
|---|---|---|
| F001 | generator | Snapshots 真进度（去合成 5 段动画，接真实刷新操作进度 + 真实 manifest）|
| F002 | generator | Strategies note 更正（去陈旧 synthetic note，保留诚实 stub/research 披露）+ 守门 |
| F003 | generator | Dashboard 死路由清理 + kill_switch 阈值单一来源统一 + 占位字段移除 + api.ts drift 同步 |
| F004 | codex | L1 全门禁 + L2 真 VM 全页面穷举审计 + 里程碑 C 达成裁定 + signoff |

---

## 4. F001 — Snapshots 真进度（generator）

### 4.1 现状根因

`services/snapshots.py` docstring（行 6-16）自述：真实 `scripts/refresh_public_snapshot` 子进程「从未接入（B023 takes that on）」，F011 ship 了合成 5 段进度生成器；设计为「只改 `_iter_stages` 函数体即可换真」。**核实结论（planner 2026-06-09）**：`scripts/refresh_public_snapshot` 物理不存在；真实刷新操作是 B045 的 `workbench_api/data_refresh/cli.py`（已 allowlist 可 import trade）。

### 4.2 架构决策点（generator 定，二选一并注明理由）

snapshots「refresh」的真实语义未定，generator 实施前须确认并文档化选择：

- **(A) 轻量真实 manifest（planner 倾向）**：refresh = 读取**当前真实数据状态**（CSV / price_history / `backtest_data_window` 覆盖窗口）构建真实 manifest，stage 事件反映真实的「读数据 → 算行数/质量 → 写 manifest」工作，`SnapshotMeta` 记录**真实** manifest 数据（实际 symbol 数 / 行数 / 覆盖窗口 / quality）。不重跑昂贵 pipeline，不与 B045 timer job 冲突，§12.10.2 安全（请求路径只读数据 + 写自己的 SnapshotMeta，不 import trade）。
- **(B) 重跑 data-refresh 子进程**：spawn `python -m workbench_api.data_refresh.cli`（独立进程，allowlist 同 worker/canonical）→ 解析真实 stdout 进度 → SSE。重、需 CLI 发结构化进度、可能撞 timer / Tiingo 限流。若选此，须确保子进程是自包含 deploy artifact（§12.10）+ 不阻塞请求过久。

### 4.3 Acceptance

1. **去合成动画**：删除 `_iter_stages` 的固定 5 段硬编码 + `_STAGE_DELAY_SECONDS` 固定 sleep 表演；进度事件反映**真实刷新操作的实际阶段边界**（按 §4.2 选定方案）。
2. **真实 manifest**：`_persist_snapshot` 去 `del detail # placeholder`，`SnapshotMeta` 写入**真实** manifest 数据（真实 manifest_path + 反映真实数据状态的 quality_status，非恒 "ok" 占位）。
3. **docstring 去 synthetic**：`services/snapshots.py` 模块 docstring + `routes/snapshots.py` 路由 docstring 删除「synthetic」「hasn't been wired yet」等陈述，改述真实接线。
4. **前端**：`snapshots/page.tsx` 已通用化消费 `event.stage`/`event.detail`（行 84-95）；若 stage 名/语义变化，同步前端展示 + i18n，否则仅验证不破。
5. **边界守门**：snapshots refresh 请求路径不在进程内 import trade（§12.10.2 AST 守门覆盖 routes/services/snapshots）；若选 §4.2(B)，子进程走 allowlist + §12.10 自包含核查。错误路径仍 yield `stage: error` 不漏栈。
6. **测试**：refresh 产真实进度事件（非固定 sleep 序列）+ SnapshotMeta 真实字段断言 + 错误路径 + §12.10.2 守门 + 前端 vitest（若改 stage）。
7. **Gates**：backend pytest ≥ baseline / ruff 0 / mypy 0；frontend（若动）vitest/lint/tsc 0。
8. **不动**：B045 timer data-refresh job / canonical / 评分。

---

## 5. F002 — Strategies note 更正（generator）

### 5.1 Acceptance

1. **更正陈旧 note**：`services/strategies.py:101-104`（global_etf_momentum）+ `:159-162`（us_quality）去除「Synthetic fixture only; not live market data / not actual filings」，改为反映 B045 真实数据来源的诚实文案（如标注真实价格/真实 filings 来源 + planning_weight），**不夸大**（仍是 research-only advisory，不得宣称收益预测）。
2. **保留诚实披露**：§1.2 列出的 satellite_stub / regime research-state 占位**不动**。
3. **i18n**：若 note 文案在前端有 i18n key，双语同步 parity；若 note 是后端直出英文串，确认前端如何展示，必要时纳入 i18n。
4. **守门回归测试**：新增/扩 guard 测试断言用户可见 strategy note **不含**「Synthetic fixture only」「not live market data」「not actual filings」等陈旧合成词（同时不误伤诚实 stub/research 披露文案）。
5. **hk_china 核查**：BL-B011-S2 已实现 hk_china 策略（Master 4/4 真实），核查 `:167-171` satellite_stub note 是否仍指 hk_china——若 hk_china 已激活，该 note 已陈旧应一并更正；若指其它未实现 sleeve 则保留。generator 实施时据 master_portfolio 实际组成裁定并在 commit 注明。
6. **Gates**：backend pytest ≥ baseline+ / ruff 0 / mypy 0 / i18n parity（若涉及）。

---

## 6. F003 — Dashboard 死路由清理 + 阈值统一（generator）

### 6.1 Acceptance

1. **删前确认零运行时消费者**（铁律：删除前看目标）：grep 前端 `fetch('/api/dashboard'`、`useDashboard`、任何 `/api/dashboard` 运行时调用——确认仅 OpenAPI 生成类型引用、无页面/hook 消费后，方可删 `routes/dashboard.py` + 注销路由注册；保留 Home 复用的 `_aggregate_nav` 等共享 helper（移到 service 公共位置，不随 dashboard service 死）。
2. **kill_switch 阈值单一来源**：`services/dashboard.py:45` 的第三份 `DEFAULT_KILL_SWITCH_THRESHOLD=0.20` —— 若 dashboard service 随死路由整体移除则连带消失；若 service 仍被 Home/其它复用则改为引用单一来源 `nav_history.KILL_SWITCH_THRESHOLD`（0.15），与 `recommendations.py:80` 同款（沉淀 v0.9.37）。
3. **master_drawdown 占位**：`services/dashboard.py:159` `master_drawdown=0.0` —— 随死路由移除；若 service 复用字段则接真实 `nav_history` master DD（去 0.0 占位）。
4. **测试更新**：`tests/unit/test_dashboard.py:112` `assert ... == 0.2` —— 随死路由移除对应测试，或改断言 0.15 / 导入常量（依 §6.1.1 删/留裁定）。
5. **OpenAPI / api.ts drift 同步**：删 `/api/dashboard` endpoint → 重新生成前端 OpenAPI 类型，确保 `api.ts` 无 drift（CI drift 检查绿）。
6. **§12.10 边界**：清理不引入新执行路径；保留的 helper 仍遵守只读边界。
7. **Gates**：backend pytest ≥ baseline / ruff 0 / mypy 0；frontend api drift 0 / tsc 0 / lint 0；alembic 不涉及。

---

## 7. F004 — L1+L2 真 VM 全页面审计 + 里程碑 C 达成裁定（codex）

### 7.1 Acceptance

**L1（CI 内）**：F001+F002+F003 全门禁 —— backend pytest（snapshots 真进度 / strategies guard / dashboard 删后无回归）+ frontend（若动 vitest/tsc/lint）+ ruff/mypy + §12.10.2 守门 + i18n parity + api.ts drift 0 + artifact grep secret=0 + alembic head（不涉及则确认不变）。

**L2（真 VM）**：
1. **Snapshots 真进度**：触发 snapshots refresh → 进度事件反映真实操作（非固定 0.05s 节奏的合成 5 段）；SnapshotMeta 列表显真实 manifest 数据。
2. **Strategies 页**：strategy note 显真实数据来源文案，**不含**「Synthetic fixture only」；诚实 stub/research 披露仍在。
3. **Dashboard 死路由**：`GET /api/dashboard` 返 404（已删）或确认无前端消费；Home 等复用页不破。
4. **★全页面穷举审计**（= 里程碑 C 达成证据）：逐页核查 **Home / Recommendations / Reports / Risk / Strategies / Backtest / Snapshots / Execution** 每页用户可见显示内容无合成/占位/硬编码 stub —— **审计看「内容类别是否该页应有的真实投资类别」不只 grep stub**（来源：Reports 接开发签收语料的错配教训）；grep `synthetic/stub/placeholder/hardcode/占位` + 逐页手验。产出**逐页审计清单**（PASS/残余）写入 signoff 作里程碑 C 达成证据。
5. **回归**：B023 交易闭环不破 + recent-errors={count:0} + HEAD≡main + B026 absent。
6. **Signoff**：`docs/test-reports/B049-all-pages-real-engine-audit-signoff-2026-MM-DD.md` 用模板（§Production/HEAD 等价 + §Post-signoff Deploy + **§全页面真实化覆盖矩阵逐页裁定**）。
   - **evaluator.md §25 适用**：snapshots 真进度、strategies 真文案、全页面审计均须**正面证据**才可 done；审计任一页发现真实残余 → 不得判 non-blocking，回 fixing。
   - 更新 progress.json status→done / docs.signoff / evaluator_feedback；若审计通过，明确裁定**里程碑 C 达成**。

---

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| F001 snapshots 真进度语义不明，generator 误接昂贵 pipeline | §4.2 留 A/B 决策点 + planner 倾向轻量 manifest（A）；实施前确认语义并文档化 |
| F003 删 dashboard 路由误删仍被复用的 helper | §6.1.1 删前 grep 确认零消费者 + 保留 `_aggregate_nav` |
| 审计「只 grep 不看类别」漏判（Reports 错配教训） | F004 acceptance (4) 明确「看内容类别」+ 逐页手验 |
| 误改诚实声明式占位隐瞒真相 | §1.2 明确禁改清单 + F002 guard 测试不误伤 |

---

## 9. 里程碑 C 达成定义

F004 审计逐页全 PASS（8 个用户投资页面无合成/占位）+ 3 残余修复确证 = **里程碑 C「所有页面接真实引擎」正式达成**，写入 signoff + project-status + progress-review 覆盖矩阵全绿。达成后回到 **B043 AI 解释层**（解释一个干净的全真实系统）。
