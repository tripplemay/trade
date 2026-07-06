# B096 — test-automation P4-F2 LLM-judge 语义层（模糊残留 + grounding，advisory）Evaluator Signoff（2026-07-06）

> **裁定：全 PASS 2/2 → done。** F001（新增 `workbench/backend/workbench_api/llm/semantic_judge.py` 278 行 + `tests/safety/test_semantic_judge_vcr.py` 284 行 + 2 个 VCR cassette + `routing.py` +10 行；generator，Workflow 3 子代理 build + 2 对抗验证）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B095 先例），与实现完全隔离，最高怀疑度。
> **核心手段：从磁盘独立解码 cassette 的 gzip 响应体、独立比对评测集标签、全 git 历史脱敏扫描、离线复跑**——不信任 committed 测试的自证。
> **被验收提交：`4ff104d`**（feat B096-F001，5 文件 +1476）+ `ce2650c`（mark done，paths-ignore 不触发 CI）。
> **生产面：无**（语义 judge **未接入任何 runtime 代码路径**，唯一 import 者是其单测文件 → advisory-only，纯 additive，无生产行为变更）。

## 0. 本批性质与命门

- **test-automation roadmap P4-F2（桶 C 概率部分）**：坐落在确定性 P4-F1 lint **之上**、红队硬门（`llm/judge.py` 边界规则）**之旁**（永不替代）的 **LLM 语义层**——(1) 模糊英文/混合残留（P4-F1 regex 漏的整句 English prose）；(2) grounding（数值是否 trace 回给定 quant/data 输入，无编造）。roadmap 定位 **advisory 非硬 block**。用户 2026-07-05 授权 `AIGC_GATEWAY_API_KEY`（验 HTTP200）解锁本批。
- **★★命门 1（最高优先）= API key 零泄露**：key 在对话中明文暴露过 → 任何 committed 文件（cassette / 模块 / 配置 / 全 git 历史）出现明文 key = **FAIL（BLOCKING）**。
- **命门 2 = 评测集准确性**：9 例 labeled → judge 判定须与预期标签一致，且构造非平凡、有防漂移锚点。
- **命门 3 = additive 零回归**：红队门 / `data/safety-evals` 逐字节未动，语义 judge 未接任何 runtime gate，ai-safety-eval 硬门绿。
- **命门 4 = VCR 机制正确性**：cassette 离线确定性重放，无真网调用即可跑测。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算/脱敏扫描） |
|---|---|---|
| **① ★API key 零泄露（最高优先，BLOCKING gate）** | **PASS** | **(a) cassette 无 authorization header**：`grep -niE "^\s*authorization:"` 两个 committed cassette = **零命中**（`filter_headers=["authorization"]` 在录制时整条剥除；gateway 用 `Authorization: Bearer {key}` 发送，剥除后 cassette 里既无 header 也无 `Bearer <value>`）。**(b) 全 git 历史脱敏扫描**：`git log -p --all \| grep -oE "sk-[A-Za-z0-9]{20,}"` = **空**；`grep -oiE "bearer [A-Za-z0-9._-]{16,}"` = **空**（跨所有 commit/分支无明文 key/token）。cassette 里的长 base64 串 = gzip 压缩响应体（`H4sI…`），`req_*`/`trc_*` = 请求/追踪 ID，均非 secret。**(c) 无硬编码**：`gateway.py` 用 `os.environ.get("AIGC_GATEWAY_API_KEY")`（缺失即 raise），非任何文件字面量。**(d) 脱敏机制常驻**：`conftest.py` `record_mode="none"` + `filter_headers=["authorization"]` + `filter_query_parameters=["token","apikey","api_key"]`。**(e) `.env.example`** `AIGC_GATEWAY_API_KEY=`（空）；`.gitignore` 覆盖 `.env` / `.env.*`（`!.env.example` 例外）；工作树无未跟踪 `.env` 文件 |
| **② LLM-judge 评测集准确率（防漂移）** | **PASS** | **独立解码坐实 9/9**：我从磁盘 `yaml.safe_load` → `gzip.decompress` → `json` 逐条解开 810 行 cassette 的 9 个响应体，独立比对 `EVAL_SET` 预期标签 → **9/9 全 match**（含跨 4 象限：3 clean(F,F) / 2 fuzzy(T,F) / 3 ungrounded(F,T) / 1 both(T,T)）。**证真机录制非伪造 stub**：evidence 字段引用具体模型措辞——`'the momentum outlook remains constructive'`、`'约 18%'`、`'P/E 为 12.5'`、`'35%'`、`'outlook 依旧 bullish'`——与注入的残留/未 grounded 数字**精确对应**。**构造非平凡**：含硬 mismatch（P/E 12.5 vs 输入 22；TLT 35% vs 输入 15% —— 不是单纯缺失而是数字对不上）。**防漂移锚点**：`test_prompt_template_pins_both_checks`（pin 两 CHECK + 白名单 token + JSON 契约）+ `accuracy == 1.0` 精确断言 + `record_mode="none"` 冻结响应（模型/prompt 漂移即变准确率即红） |
| **③ additive 零回归（红队门为旁路非修改）** | **PASS** | **git 证据**：`git diff 3845ae4^..HEAD -- test_ai_advisor_red_team* data/safety-evals judge.py conftest.py` = **空**（红队硬门 + dataset + judge.py + conftest 自 B096 开批前逐字节未动）。**未接 runtime**：`grep -rniE "semantic_judge\|judge_semantic\|SemanticVerdict" workbench_api/`（除模块自身 + routing 条目）= **空**；全仓唯一 import 者 = `tests/safety/test_semantic_judge_vcr.py` → **advisory-only，无生产行为变更**。**routing.py additive**：仅新增 `"semantic_judge": "claude-haiku-4.5"` 一条 + 注释，既有条目未动。**硬门 scope**：`ai-safety-eval.yml` 只列 `test_ai_advisor_red_team.py` + `test_ai_advisor_red_team_vcr.py` + `test_safety_eval_workflow.py`，**不含**本新测 → 本测非 deploy gate |
| **④ red-team 门零回归复跑 + CI 绿** | **PASS** | **本地全跑**：`tests/safety/` = **261 passed / 15 skipped**（15 skip = red-team L2 需真 key，CI 由 AI Safety Eval 注入，本地 skip 属正常 L1/L2 分层，非回归）。**CI**（`4ff104d` push）：**Workbench Backend CI success 11m28s + AI Safety Eval success 1m47s + Workbench Deploy success 5m0s**——**AI Safety Eval 绿 = 红队门在 CI 真 key 下零回归的活证据**。⚠ Workbench Frontend CI = failure，但见 §3 O1：**Playwright E2E smoke flake，与本批 backend-only 变更无关**（B096 触碰 0 个 frontend 文件；前序 commit 亦见同 flake），非 deploy gate，Deploy 已绿到底 |
| **⑤ advisory 非硬 block + task 路由无硬编码模型** | **PASS** | **advisory**：`SemanticVerdict.advisory: bool = True`（永久标记），`judge_semantic` docstring 明述"never raises on a flagged output"，仅在**契约违反**（非 JSON/错 shape/错类型）时 raise `ValueError`（fail-loud 防静默误判全集）；单测 `assert verdict.advisory is True`。**路由无硬编码**：`semantic_judge.py` 用 `task=SEMANTIC_JUDGE_TASK="semantic_judge"`，模型名仅在 `routing.py` ROUTING_TABLE（单一真相）；独立解码路由 cassette 的请求体 = `model":"claude-haiku-4.5"` → 证经路由表解析到 haiku，非模块内字面量。**独立 task**（非 `safety_judge` 复用）→ advisory 层不可能与红队硬门混淆/误路由 |
| **⑥ VCR 离线确定性 + L1 门禁 + HEAD≡prod** | **PASS** | **VCR**：`record_mode="none"`（仅重放，无匹配 cassette 即 raise，绝无真网调用）；`_offline_gateway()` 用 dummy key `"vcr-deterministic"` + `_NoopGuard` → 无需真 key 无需 DB；`AIGC_GATEWAY_API_KEY= pytest test_semantic_judge_vcr.py` = **4 passed**（空 key 离线跑通）。确定性：`temperature=0` + `sort_keys` 稳定渲染 + vcrpy 按录制顺序重放。**门禁**：ruff `All checks passed`（3 文件）+ mypy `Success: no issues found in 320 source files` + pytest 4（semantic）/ 261（safety 全）。**HEAD≡prod**：新模块未接 runtime → 生产运行行为零变更 → HEAD 产品码 ≡ prod 平凡成立，Deploy 链已绿 |

## 2. 核心命门复核（最高怀疑度，独立解码 + 全历史扫描）

**命门 1 — API key 零泄露（BLOCKING，独立三重扫描）：**
1. **cassette header 剥除**：gateway 以 `Authorization: Bearer {self._api_key}` 发请求（`gateway.py:185`）。若 key 被录进 cassette，会以 `Bearer <key>` 出现在 request headers。两个 committed cassette 的 `grep "^\s*authorization:"` = **零命中**，`grep "bearer <value>"` 全历史 = **空** → `filter_headers` 确已整条剥除，未来录制亦自动脱敏（机制常驻 conftest）。
2. **全 git 历史**：`git log -p --all` 扫 `sk-` / `bearer <value>` = 空；40+ 字符长串定位 = git SHA（40-hex）+ 既有 cassette 的 gzip 响应体（out-of-scope 旧文件），非本批引入的 secret。
3. **无硬编码 + 环境隔离**：key 走 `os.environ`；`.env.example` 空；`.gitignore` 覆盖 `.env*`；工作树无未跟踪 `.env`。**结论：任何 committed 文件、任何 commit、任何 cassette 均无明文 key。BLOCKING gate 通过。**

**命门 2 — 评测集准确率（独立解码，非信任测试自证）：** 我未信任 `assert accuracy == 1.0`，而是自己 `gzip.decompress` 逐条解开 9 个响应体、strip code fence、`json.loads`、比对 `(fuzzy_residual, ungrounded_number)` 与 `EVAL_SET` 预期 → **9/9**。evidence 字段引用真实模型措辞（非空 stub）证 cassette 为真机 Haiku 录制。跨 4 象限 + 硬 mismatch 案例（数字对不上而非缺失）→ 判别力非平凡。

**命门 3 — additive 零回归（git 逐字节）：** `git diff 3845ae4^..HEAD` 对红队门/dataset/judge.py/conftest = 空；grep 证唯一 import 者是单测 → advisory-only 未接生产；ai-safety-eval 硬门文件清单不含本测。四重坐实纯 additive。

**命门 4 — VCR 离线确定性：** `record_mode="none"` 使测试只能重放、绝无真网；空 key 下 4 passed + 全 safety 261 passed 坐实离线可跑。

## 3. 软观察（非阻断，供 follow-up 参考）

- **O1 — Workbench Frontend CI 在 `4ff104d` 为 failure，但与本批无关（非回归）**：失败作业 = **Playwright E2E smoke**（boot dev server），frontend-only。B096 是 **backend-only 变更（触碰 0 个 frontend 文件）**，且前序历史（B083 同 failure、并有 `fix(ci): harden risk-banner defensive-flip test (CI-timing flake)` commit）证该 E2E smoke 为**已知间歇性 flake**。它**非 deploy gate**（deploy 门 = Backend CI + AI Safety Eval，二者绿），Workbench Deploy 已 success 到底。非本批缺陷，非阻断。
- **O2 — 语义 judge 尚无 runtime/CI-gate 消费者**：本批仅落"LLM 检测能力 + 评测集证据网 + drift 检测测试"，findings 未接进 advisor 运行时或 deploy 断言（advisory-only）。与 roadmap P4-F2 "advisory 非硬 block" 定位一致，实际用作 gate 是后续批的事。非缺陷，是 scope 边界。注：`workbench-backend.yml` 的 `pytest tests/safety -q` **会**在每次 backend CI 离线跑本评测集 → drift 检测已进 CI（正向）。
- **O3 — cassette 依赖录制顺序重放**（`match_on` 排除 body）：vcrpy 按录制顺序服务 9 个响应，故 `EVAL_SET` 列表顺序 load-bearing。已由测试 docstring 明述且录制/重放同源，非缺陷；未来若重排评测集需同步重录。

三项均非阻断，不撼动 F001 交付（key 零泄露 + 9/9 准确 + additive 未接 runtime + 红队门零回归 + VCR 离线确定性）与命门。

## 4. 结论

**B096 test-automation P4-F2 LLM-judge 语义层 2 features 全 PASS → done。**

★API key 零泄露经**独立三重扫描**坐实（cassette 无 authorization header + 全 git 历史无 `sk-`/`Bearer <value>` + key 走 env 无硬编码 + `.env.example` 空 + `.gitignore` 覆盖 + 工作树无未跟踪 env）——**BLOCKING gate 通过，无需轮换触发**（key 未进任何 committed 文件；但因 key 曾在对话明文暴露，用户仍宜按开批约定在用完后主动轮换，与本批 commit 安全性独立）；评测集准确率经**我从磁盘独立解码 9 个 gzip 响应体逐条比对** → 9/9（evidence 引真机措辞证非伪造，跨 4 象限含硬 mismatch 非平凡）；additive 零回归经 **git diff 证红队门/dataset/judge.py/conftest 逐字节未动** + **grep 证未接 runtime**（唯一 import 者是单测 → advisory-only）+ **safety 261 passed** + **CI AI Safety Eval 绿**（红队门真 key 复跑活证）四重坐实；advisory 非硬 block 经 `advisory=True` 永久标记 + 仅契约违反 raise 坐实；task 路由无硬编码经**独立解码路由 cassette 请求体 = claude-haiku-4.5** 坐实；VCR 离线确定性经 `record_mode="none"` + **空 key 4 passed** 坐实；门禁全绿（ruff + mypy 320 + pytest 4/261）+ **HEAD 产品码 ≡ prod（未接 runtime）**。三项软观察（O1 frontend E2E flake 与本批无关 / O2 尚无 runtime gate 消费者 / O3 cassette 顺序依赖）均**非阻断**。

**★含义：推进 test-automation roadmap 1 feature（P4-F2 LLM-judge 语义层，模糊残留 + grounding，概率性）。test-automation item 不清空——P3（生产 synthetic/canary，已授权待 B097）+ P5（独立评审固化，铁律 4）仍待办。本批交付的是"LLM 语义能力层 + 评测集证据网 + drift 检测（已进 backend CI）"，未接 runtime gate（advisory-only），符合 roadmap "advisory 非硬 block" 定位。**
