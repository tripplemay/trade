# B095 — test-automation P4-F1 确定性语义 lint（英文残留 + no-AI 禁语）Evaluator Signoff（2026-07-06）

> **裁定：全 PASS 2/2 → done。** F001（新增 `workbench/backend/workbench_api/advisor/semantic_lint.py` 318 行 + `tests/safety/test_semantic_lint.py` 355 行，74 测，generator，Workflow 2 轮建）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B094 先例），与实现完全隔离，最高怀疑度。
> **核心手段：用我自己从零构造的对抗样本独立跑 lint**——(1) 我自己的 10 条已知违例（B054 式英文残留 + no-AI 禁语）全部命中；(2) 我自己的 10 条合法 grounded 中文样本零假阳；(3) 变异/牙齿检查（否定窗口边界、bare 下单 collision）；(4) additive 零回归全审（红队门 git 未动 + 未接入 runtime + safety 257 绿 + CI ai-safety-eval 绿）。
> **被验收提交：`560a143`**（feat B095-F001，2 新文件 + state）+ `0ff5d16`（mark done，paths-ignore 不触发 CI）。
> **生产面：无**（新模块**未接入任何 runtime 代码路径**，唯一 import 者是其单测文件 → advisory-only，纯 additive，无生产行为变更）。

## 0. 本批性质与命门

- **test-automation roadmap P4-F1（桶 C 确定性部分）**：AI advisor 中文输出的**确定性预过滤**（regex/词表）——(a) 英文残留检测；(b) no-AI 禁语检测（收益预测/执行指令/替代 quant）。roadmap 定位为"吃掉 ~80%"、**advisory 非硬 block**（P4-F2 LLM-judge 是模糊残留后手，本批不做）。
- **★命门 = lint 门的命门 = 假阳率 与 真阳捕获**：(i) **假阳率**——lint 若在合法 grounded 数值/ticker/hash 中文 advice 上误报，比没有 lint 更糟（spec constraint #4，词表/否定守卫刻意"宁漏勿误"）；(ii) **真阳捕获**——须真的抓住英文残留与未否定禁语；(iii) **additive 零回归**——**零修改** red-team 硬门逻辑 / `data/safety-evals` / 现有硬门，ai-safety-eval 保持 GREEN。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算/对抗样本） |
|---|---|---|
| **① 真阳捕获（英文残留 + no-AI 禁语）** | **PASS** | **我自己构造 10 条已知违例，全部命中**：英文残留 `recommend`/`Overall`/`undervalued`/`based on`/`buy/hold`（B054 式中文里漏英文散词/句，含斜杠英文片段 `buy/hold` 非 ticker 仍捕）；禁语 `收益预测`/`自动下单`/`替代量化`/`保证收益`/`为你下单`（未否定的边界破坏）全部 HIT。committed 侧：`@pytest.mark.parametrize` 逐条对 `sorted(set(BANNED_PHRASES))` 每条禁语断言"未否定必捕"（无死条目）+ 英文句片段 `the/model/recommends/holding` 全捕，74/74 测 pass |
| **② 假阳率（合法 grounded 中文 advice 零误报，最重）** | **PASS** | **我自己构造 10 条合法 advice，0 假阳**：多 ticker 斜杠列表 `TLT/IEF`、比率复合 `EV/EBITDA`+`P/B`、回测数字、`sha256:` hash、否定免责句（`不构成收益预测`/`非交易指令`/`不自动下单`）、`下单` 跨词边界碰撞（`当下单边`/`眼下单一`）、`难`-否定（`难以预测收益`/`很难保证盈利`）、ISO 时间戳 `...T00:00:00Z`、acronym+单位（`NAV`/`ROE`/`bps`/`USD`）、`替代量化`否定 + `quant` 白名单 —— 全 CLEAN。committed 侧：12 条 `LEGITIMATE_ADVICE` 参数化 + **真实 advisor cassette body lint 零 finding**（`test_real_cassette_advice_passes_lint`，read-only 证真机模型输出无假阳）。★边界审：白名单机制合理——URL/sha256 整段 mask、all-upper ≤6 char ticker/ratio/acronym 按 joiner 逐段验证、小写 allowlist 刻意小且逐条有据（cassette 验证 `quant`）、纯数字/百分比永不为 token 起点 |
| **③ additive 零回归（红队门为新增非修改）** | **PASS** | **git 证据**：`git diff b17d89a..HEAD -- test_ai_advisor_red_team*.py data/safety-evals` = **空**（红队门/dataset 自 B094 done 起逐字节未动）。**未接入 runtime**：`grep -rn semantic_lint workbench_api/` 仅命中模块自身；全仓唯一 import 者 = `tests/safety/test_semantic_lint.py` → **advisory-only，无生产行为变更**。**scope**：`git diff 25c99ea..HEAD -- workbench/` = 仅 2 新文件（+673），无既有产品码改动。**门定位与 spec 一致**：lint 返回 findings 供 caller（测试/logger/P4-F2）取用，runtime 不 raise/block，与 roadmap "advisory gate 而非硬 block" 相符 |
| **④ red-team 门零回归复跑 + ai-safety-eval CI 绿** | **PASS** | **本地**：`tests/safety/` 全跑 **257 passed / 15 skipped**（15 skip = red-team L2 需 `AIGC_GATEWAY_API_KEY`，CI 由 AI Safety Eval workflow 注入，本地 skip 属正常 L1/L2 分层，非回归）；red-team L1 可跑部分 8 passed。**CI**（`560a143` push）：**Workbench Backend CI success 10m1s + Workbench Frontend CI success + AI Safety Eval success 1m42s + Workbench Deploy success**——**AI Safety Eval 绿 = 红队门在 CI 真 key 下零回归的活证据**（改 advisor/** 触发其复跑=安全网） |
| **⑤ F001 REFUTED→CONFIRMED 对抗验证闭环如实记录** | **PASS（journal 不可及，回归测试固化超越）** | generator_handoff 载 Workflow 2 轮（build → 2 对抗验证 REFUTED 3 类假阳 → fix → 2 对抗验证 CONFIRMED survived）。journal 本机不可及（独立 session transcript 已散）——**非阻断**：闭环由**测试文件 §(c2) 回归块固化**——`test_regression_compound_ratio_and_multiticker_not_flagged`（`EV/EBITDA`/`SPY/QQQ/TLT` 拦第 1 轮 concat-超 6 char 假阳）+ `test_regression_banned_phrase_false_positives_not_flagged`（`下单` 4 类碰撞 + `难`-否定拦第 1 轮假阳）+ `test_regression_genuine_violations_still_caught`（配套证修复未钝化真违规）——**每条假阳被 pin 防回潮**，代码 docstring 逐条叙明（"bare 2-char 下单 dropped because 下/单 high-frequency collided"）。我 PROBE C 独立复现：bare `下单`→[]、`下单买入`→捕、`难以预测收益`→[]、far-negation `不……收益预测`→捕（否定窗口有牙）——与 handoff 逐项相符 |
| **⑥ L1 门禁 + CI 三绿 + HEAD≡prod + zero product-runtime-change** | **PASS** | **门禁**：ruff `All checks passed`（2 新文件）+ mypy `Success: no issues found` + pytest `74 passed`（semantic_lint）/ `257 passed`（safety 全）/ `126 passed`（advisor 相关）。**CI**：`560a143` 四 workflow 全 success（Backend/Frontend/AI Safety Eval/Deploy 自动链式）。**HEAD≡prod**：新模块未接入 runtime → 生产行为零变更 → HEAD 产品码 ≡ prod 平凡成立 |

## 2. 核心命门复核（最高怀疑度，用我自己的对抗样本）

**PROBE A — 真阳捕获（我自己 10 条已知违例）**：英文残留 5/5 + 禁语 5/5 全 HIT。含 B054 式真实残留类（中文 advice 里漏 `recommend`/`Overall`/`based on`）与斜杠英文 `buy/hold`（非 ticker 列表，正确判为残留）。

**PROBE B — 假阳猎杀（我自己 10 条合法 advice）**：0/10 假阳。刻意堆叠最易误报的边界——多 ticker 斜杠、`EV/EBITDA` 比率复合、`下单` 跨词碰撞、`难`-否定、ISO 时间戳、acronym+单位、否定免责句——全 CLEAN。**白名单机制审定合理**：不是无脑放行英文，而是 (a) URL/sha256 整段 mask；(b) all-upper ≤6 char 按 joiner 逐段验证（`EV/EBITDA` 每段是 ratio-vocab/acronym 才放行，`buy/hold` 每段非 acronym 故仍捕）；(c) 小写 allowlist 逐条有据（`quant` 有 cassette 实证）。

**PROBE C — 变异/牙齿检查**：
1. **否定窗口有牙**：`收益预测` 前 `不` 距离 >5 char（`NEGATION_WINDOW=5`）时**仍触发**（`C1 far-negation` → 捕）；`不构成收益预测`（`不` 在窗口内）正确抑制（`C2` → []）。窗口不过宽=真违规不会被无关 `不` 意外掩盖。
2. **bare 下单不误报**：`请下单`→[]（bare `下单` 刻意剔除，避 `当下单边`/`眼下单一` 碰撞），但 `下单买入`/`为你下单` 等特定下单指令仍捕——真违规不漏。

## 3. 软观察（非阻断，供 P4-F2 / follow-up 参考）

- **O1 — 确定性 pre-filter 固有"宁漏勿误"漏报口**：设计刻意偏向漏报而非误报（spec constraint #4）。两处已知漏报口：(i) bare 2-char `下单` 剔除 → 仅以 `下单` 表述的下单指令会漏（但 `自动/立即/为你/下单买入` 等具体形式全覆盖）；(ii) `NEGATION_WINDOW=5` → 真违规若前 5 char 内有无关否定词会被误抑。**二者均 docstring 明述、且是 advisory pre-filter 的正确取舍**（P4-F2 LLM-judge 是模糊残留后手）。非缺陷，roadmap 设计如此。
- **O2 — 小写 allowlist 未来演进需守证据门**：`LOWER_ALLOWLIST`（`quant`/`sleeve`/`bps`…）刻意小且每条有据（cassette/prompt/roadmap 实证）。若后续 advisor 措辞演化引入新合法小写域词，会短暂假阳——但这正是"宁误报促人工复核"的正向失败，且加词有单测守。非阻断。
- **O3 — lint 尚无 runtime/CI 消费者**：本批仅落"检测能力 + 单测证据网"，未把 findings 接进任何 CI 断言或 advisor 运行时（advisory-only）。这与 P4-F1 scope 一致（"吃掉 ~80%" 的能力层），实际用作 gate 是 P4-F2/后续批的事。非缺陷，是 scope 边界。

三项均非阻断，不撼动 F001 交付（真阳捕获 + 零假阳 + additive 未接 runtime + 红队门零回归 + REFUTED→CONFIRMED 闭环固化）与命门。

## 4. 结论

**B095 test-automation P4-F1 确定性语义 lint 2 features 全 PASS → done。**

真阳捕获经**我自己 10 条已知违例**（B054 式英文残留 + no-AI 禁语）全命中 + committed 逐禁语参数化坐实；假阳率经**我自己 10 条合法 grounded advice** 零误报 + 12 条 committed + **真实 advisor cassette 零 finding** 三重坐实，白名单机制（URL/hash mask + joiner 逐段 acronym 验证 + 小证据 allowlist）审定合理；additive 零回归经 **git diff 证红队门/dataset 逐字节未动** + **grep 证未接入任何 runtime**（唯一 import 者是其单测 → advisory-only）+ **safety 257 passed** + **CI AI Safety Eval 绿**（红队门真 key 复跑活证）四重坐实；REFUTED→CONFIRMED 闭环经**测试 §(c2) 回归块逐假阳固化** + 我 PROBE C 独立复现（否定窗口有牙、bare 下单不误报、真违规仍捕）坐实；门禁全绿（ruff + mypy + pytest 74/257/126）+ **CI 四 workflow 三绿自动链式（560a143）** + **HEAD 产品码 ≡ prod（未接 runtime，生产零变更）**。三项软观察（O1 宁漏勿误漏报口 / O2 allowlist 演进 / O3 lint 尚无消费者）均**非阻断**，与 advisory pre-filter 的 scope 边界一致。

**★含义：推进 test-automation roadmap 1 feature（P4-F1 确定性语义预过滤，桶 C 确定性部分）。test-automation item 不清空——P4-F2（LLM-as-judge 模糊残留，概率性）+ P3（生产 synthetic/canary）+ P5（独立评审固化）仍 user-gated / 需 LLM。本批交付的是"确定性能力层 + 证据网"，未接 runtime gate（advisory-only），符合 roadmap "advisory 非硬 block" 定位。**
