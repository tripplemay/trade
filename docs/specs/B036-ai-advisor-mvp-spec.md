# B036 — AI Advisor MVP（Phase 2 / Stream 3.C）🎯 里程碑 B / Phase 2 终点

> **批次类型：** 混合批次（3 generator + 1 codex）
> **状态流转：** planning → building → verifying → (fixing ⟷ reverifying) → done
> **依赖：** B031 LLM Gateway（✅ `advise`/routing/cost_guard）+ B032 AI Safety Eval（✅ `judge.py` / red-team dataset / CI deploy gate）+ B034 News 关联（✅）+ B035 Market context（✅）
> **决策对齐：** 2026-06-05 用户已批（见 §2）

---

## 1. 目标

项目**首次真正的生成式 AI**：整合 quant signal + real data + B034 news 关联 + B035 market context → 生成式投资建议文本，**强制带可引用来源**（`quant_signal_sha` + `news_urls`），JSON schema 输出，Home 页 AI Advisor 段呈现，`INSUFFICIENT_GROUNDING` fallback，并**通过 B032 已建的 15 条红队样本 safety gate**（CI 100% 拦截后才允许 deploy）。完成即达成 **🎯 里程碑 B / Phase 2 终点**。

**关键复用（B036 不从零建）：** B032 已落地 `gateway.advise()`（routed chat）、`llm/judge.py`（Sonnet judge + INSUFFICIENT_GROUNDING 短路）、`tests/safety/test_ai_advisor_red_team.py`、red-team dataset、CI safety-eval **deploy gate**。B036 建 **advisor service**（接真 grounding + JSON 契约 + fallback）并让红队样本对**真 advisor** 100% 拦截。

**不做**（见 §6）：盘中实时建议 / 个股买卖指令 / 收益预测数字 / 自动交易执行 / 替代 quant 评分作唯一决策依据。

## 2. 决策矩阵（2026-06-05 用户已批，★=拍板）

| # | 决策 | 取值 | 依据 |
|---|---|---|---|
| 1 ★ | 触发/刷新 | **每日预计算（复用 B035 systemd timer）** | 用户拍板；与 ai-safety §2「只 CI 预走」一致 |
| 2 ★ | grounding 输入 | **quant signal + B034 news + B035 market context 全量**；`references=[{quant_signal_sha, news_urls}]` | 用户拍板；ai-safety §2 β 引用契约 |
| 3 ★ | advisor 模型 | task=`daily_advisor` → `claude-haiku-4.5`（routing.py live-verified 2026-05-27）；judge 仍 `safety_judge`→Sonnet 4.6；**red-team gate haiku 不稳 → 一行 routing 升 Sonnet** | 用户「按 gateway 实际可用定」= routing.py 既有 source of truth；边界 (l) |
| 4 | 输出契约 | JSON schema：per-sleeve `{advice, rationale, references:[{quant_signal_sha, news_urls}]}` + 校验 references ⊆ input set | ai-safety §2 §4 |
| 5 | fallback | `INSUFFICIENT_GROUNDING`（grounding 不足/refs 不在 input set/quant payload 不可解析）→ 不渲染 AI，显示 fallback 文案 | ai-safety §6 |
| 6 | 5 子条生成式边界 | prompt + 输出校验强制 | v0.9.28 / positioning §6.1 |
| 7 | CI | unit fixture-first；red-team gate 在 CI 跑真 judge（B032 既有 deploy gate，~45s/run）| ai-safety §5 |
| 8 | Cost | `daily_advisor`=haiku-4.5，cost_guard（边界 m）≤¥1500/月 cap | ai-safety §2 / B031 §6 |

## 3. 永久硬边界（继承 + AI 边界全触发 + (r) 修订）

- **系统层（继承）：** no-broker SDK / no-paper-or-live URL / no-credential / **no-auto-execution（自动交易/下单）** / 多用户禁 / Cloud SQL 禁 / same-origin `/api/*` / auth-gated / Repository。
- **AI 永久边界 v0.9.28 5 子条（B036 首次全量生成式触发，硬 enforce）：**
  - (a) **no auto-execution**：AI 输出永不触发下单/交易。
  - (b) **no 收益预测数字**：无具体收益预测 / 目标价 / "预计 X%" 等未来数字预测。
  - (c) **no 替代 quant 评分作唯一决策依据**：AI 是解释/聚合层，不替代 quant signal。
  - (d) **必须可引用**：每条 actionable 建议带 `quant_signal_sha` + `news_urls`，且引用必须在 input set 内（伪造/越界引用 → fail）。
  - (e) **允许** explain / summarize / translate / aggregate context。
  - 守门：B032 `test_ai_advisor_red_team.py` 15 样本（α 收益预测 / β 无引用 / γ 越界个股）对**真 advisor** 100% 拦截；CI safety-eval workflow 失败则 **deploy 拒绝**。
- **数据/CI 层（继承）：** fixture-first 离线 unit CI / §12.8 runtime dep / §12.9 secret（本批次无新 secret — 复用 `AIGC_GATEWAY_API_KEY`）/ §12.10 请求路径自包含。
- **🔧 边界 (r) 修订（B036）：** B035 起调度器原 scope =「仅只读市场数据拉取」；**B036 修订为：调度器可（a）只读数据拉取 +（b）运行已过 CI safety-gate 的 AI advisor 预计算**（写 advice 入 DB）；**仍明确 NOT 交易执行/下单/broker**。守门 `test_market_scheduler_scope.py` 放宽允许 advisor import，但仍禁 broker/ticket/execution 模块。与 ai-safety §2「runtime 不做 sync check（已 CI-gated）」一致。

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/
├── advisor/
│   ├── __init__.py
│   ├── grounding.py      # F001 组装 quant signal + B034 news + B035 market context
│   ├── service.py        # F001 AdvisorService.advise_sleeve() → JSON + 校验 + fallback
│   ├── schema.py         # F001 AdviceOutput JSON schema + references 校验
│   └── precompute.py     # F002 每日预计算 job（timer 调用）
├── llm/                  # 复用 B031/B032：gateway.advise / judge / routing / cost_guard
├── db/
│   ├── models/advisor_recommendation.py   # F001 AdvisorRecommendation 表
│   ├── repositories/advisor_recommendation.py
│   └── migrations/versions/0008_b036_advisor.py  # down_revision=0007_b035_market_context
├── schemas/advisor.py    # F003 AdvisorResponse
└── routes/advisor.py     # F003 GET /advisor

workbench/deploy/systemd/  # F002 timer 扩 advisor precompute（或新 .service）
workbench/frontend/src/app/(protected)/  # F003 Home AI Advisor 段 + fallback UI
tests/safety/test_ai_advisor_red_team.py  # F001 接真 advisor service（B032 既有）
```

### 4.2 `advisor_recommendation` 表（F001）

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID PK | 复用 `_UuidString` |
| sleeve | TEXT NOT NULL | |
| advice_json | JSON NOT NULL | per-sleeve 结构化输出（advice/rationale/references）|
| quant_signal_sha | TEXT NOT NULL | grounding 的 quant signal SHA |
| references_json | JSON NOT NULL | `[{quant_signal_sha, news_urls}]` |
| model | TEXT NOT NULL | e.g. `claude-haiku-4.5` |
| status | TEXT NOT NULL | `ok` / `insufficient_grounding` |
| generated_at | DateTime(tz=True) NOT NULL | |

- Index `ix_advisor_recommendation_sleeve` / `ix_advisor_recommendation_generated_at`；最新 by (sleeve, generated_at desc)。
- alembic `0008_b036_advisor`，`down_revision='0007_b035_market_context'`；downgrade 显式目标。

### 4.3 AdvisorService（F001）

- `grounding.py`：`build_grounding(sleeve) -> Grounding`：取 quant signal（含 sha）+ B034 `NewsAssociationService.news_for_sleeve`（含 url）+ B035 `MarketContextRepository.latest_by_series`。
- `service.py`：`advise_sleeve(sleeve) -> AdviceOutput`：
  1. build grounding；若 quant payload 不可解析 / 无 quant signal → 直接 `INSUFFICIENT_GROUNDING`。
  2. 构造 prompt（系统 prompt 含 5 子条边界 + 引用契约 + JSON schema 指令）。
  3. `gateway.advise(ChatRequest(task="daily_advisor", ...))`（cost_guard 边界 m）。
  4. 解析 JSON；**校验 references ⊆ input set**（每个 quant_signal_sha == grounding sha；每个 news_url ∈ grounding news urls）；越界 → `INSUFFICIENT_GROUNDING`。
  5. 落 `AdvisorRecommendation`。
- `schema.py`：`AdviceOutput` 结构 + 校验函数（纯 Python，可被 unit + red-team 复用）。
- **red-team（B032 既有）：** `test_ai_advisor_red_team.py` 改为对 `AdvisorService`（真 advisor）跑 15 样本，断言每个 `judge_output(...).fail_triggered is False`（被拒/INSUFFICIENT_GROUNDING）。

### 4.4 每日预计算（F002，边界 (r) 修订）

- `precompute.py`：`run_daily()` 遍历 sleeve → `AdvisorService.advise_sleeve` → 落库（幂等 by (sleeve, date)）。
- 复用 B035 systemd timer：扩 `.service` ExecStart 链（market 拉取后跑 advisor precompute）或新增 `workbench-advisor.timer`（每日，market 之后）。
- **边界 (r) 修订守门**：`test_market_scheduler_scope.py` 更新——允许 import advisor/llm，但仍 AST 断言不 import broker/ticket/execution。
- cost_guard 保护每日 N sleeve × advise 调用 ≤ cap。

### 4.5 API + 前端（F003）

- `GET /advisor`（auth-gated, same-origin）→ `AdvisorResponse { sleeves: [{sleeve, advice, rationale, references[], status, generated_at}] }`；读最新预计算。
- Home AI Advisor 段：渲染 advice + rationale + **引用链接（news_urls 外链 + quant_signal_sha 标注）**；`status=insufficient_grounding` → 显示 ai-safety §6.2 fallback 文案「AI 建议未通过安全检查，今日跳过」，**不影响** quant signal / news / risk 区。
- §12.10 请求路径自包含守门。

### 4.6 Fixture / CI

- unit fixture-first：mock gateway 返回录制 advice JSON（含合规 + 越界两类）测 service 校验 + fallback。
- red-team gate（B032）：CI 跑真 Sonnet judge（既有 deploy gate）；15 样本 100% 拦截才 deploy。

### 4.7 安全 / regression test 矩阵

| 测试 | 守门 |
|---|---|
| `test_ai_advisor_red_team.py`（B032 既有，接真 advisor）| 15 样本 α/β/γ 100% 拦截 |
| `test_market_scheduler_scope.py`（更新）| 调度器允许 advisor，但禁 broker/ticket/execution（边界 (r) 修订）|
| advisor references 校验 unit | 越界 quant_sha / 伪造 news_url → INSUFFICIENT_GROUNDING |
| `test_advisor_request_self_contained`（§12.10）| /advisor 请求路径不读 repo-root fixtures |
| secret | 无新 secret（复用 AIGC_GATEWAY_API_KEY）|

## 5. Feature 拆分

### F001 — Advisor service + grounding + JSON 契约 + red-team 接真（generator，3 天）
grounding 组装 + service + schema 校验 + INSUFFICIENT_GROUNDING + advisor_recommendation 表 + alembic 0008 + repository + 让 `test_ai_advisor_red_team` 对真 advisor 100% 拦截 + pytest。详见 features.json。

### F002 — 每日预计算（B035 timer 扩）+ 边界 (r) 修订守门（generator，2 天）
precompute.py + timer 接线 + scope 守门更新 + cost_guard + pytest。详见 features.json。

### F003 — Home AI Advisor 段 + GET /advisor + fallback UI（generator，2 天）
API + 前端 + 引用渲染 + INSUFFICIENT_GROUNDING fallback + vitest/Playwright。详见 features.json。

### F004 — Codex L1 + L2 真 VM 验收 + signoff（codex，1-2 天）
L1（red-team 15/15 拦截 + safety-eval deploy gate + 全门禁）+ L2（advisor 预计算跑通 / Home 渲染 + fallback / alembic 0008 / timer scope / HEAD≡main）+ signoff。详见 features.json。

## 6. 不做的事（YAGNI）

- 盘中实时 / 高频建议（仅每日预计算）。
- 个股买卖指令 / 收益预测数字 / 目标价（5 子条 b/c 禁）。
- 自动交易执行（边界 a）。
- AI 替代 quant 评分作唯一决策依据（边界 c）。
- 多轮对话 / 用户自由提问 advisor（本批次仅预计算 per-sleeve 建议）。
- 新 LLM provider / 新 secret（复用 B031 gateway + AIGC_GATEWAY_API_KEY）。

## 7. 验收门槛汇总

| 门禁 | 阈值 |
|---|---|
| backend pytest | F001 ≥ baseline+≥12 / F002 ≥ +≥6 / F003 ≥ +≥6（B035 收尾 baseline 704）|
| **red-team safety gate** | **15/15 样本对真 advisor 100% 拦截**（CI safety-eval workflow，失败则 deploy 拒绝）|
| frontend | vitest ≥180（+advisor 段）/ Playwright ≥40（+fallback e2e）/ lint 0 / typecheck pass |
| ruff / mypy | exit 0 |
| alembic | upgrade head（0008）+ downgrade 到 0007 可逆 |
| 安全守门 | §4.7 全过；边界 (r) 修订 scope；§12.10 自包含；5 子条 enforce |
| AI 边界 | 5 子条 prompt + 输出校验；references ⊆ input set |

## 8. 参考文档

- `docs/product/ai-safety-evals-2026-05.md` §2-§6（red-team / judge / CI gate / INSUFFICIENT_GROUNDING / fallback UI）
- `docs/product/positioning-2026-05.md` §1.1 §6.1（AI 5 子条永久边界）
- `docs/product/implementation-path-2026-05.md` §4 Phase 2 / Stream 3.C（B036 行）
- `docs/test-reports/B032-ai-safety-eval-signoff-2026-05-28.md`（既有 harness + deploy gate）
- B031 `llm/gateway.py` `advise` + `routing.py`（`daily_advisor`→haiku-4.5）+ `cost_guard.py`（边界 m）+ `judge.py`
- B034 `news/association.py`（news_for_sleeve）+ B035 `db/repositories/market_context.py`
- framework v0.9.28（AI 5 子条 + spec acceptance 模板）/ v0.9.32 §12.10 / §23 L2 新路由 200

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| haiku-4.5 advisor 不稳过 red-team（生收益预测/漏引用）| routing 一行升 `daily_advisor`→sonnet-4.6（边界 l）；prompt 强约束 + 输出校验二次拦截 |
| references 幻觉（引用 input set 外）| service 强校验 refs ⊆ input；越界 → INSUFFICIENT_GROUNDING |
| 调度器跑 AI 偏离边界 (r) | scope 守门 AST 禁 broker/ticket/execution；advisor 输出永不触发下单（边界 a）|
| 每日预计算 token 成本 | daily_advisor=haiku-4.5 + cost_guard cap（边界 m）+ N sleeve 有限 |
| grounding 不足时硬输出 | INSUFFICIENT_GROUNDING fallback（ai-safety §6）；不渲染 AI，不影响其他区 |
| CI red-team 跑真 judge 不稳定 | B032 既有缓存（Anthropic prompt caching 5min）+ ~45s baseline |

## 10. 与既有批次的边界

- **复用不改** B031 gateway/routing/cost_guard/judge / B032 red-team dataset + CI gate（仅把 test 接真 advisor）/ B034 news association / B035 market context + timer。
- **不动** quant 策略信号生成逻辑（advisor 只读 quant signal + sha）/ B033 news (q) / B026 banner / 既有 recommendations/risk/execution。
- **修订** 边界 (r)（调度器允许跑 CI-gated advisor）。

## 11. 后续（B036 之后）

- 🎯 **B036 done = 里程碑 B / Phase 2 终点。** 后续进入 Phase 3（Home + UI 重构）等，按 implementation-path / roadmap 由 Planner 在 B036 done 阶段与用户重新规划。
