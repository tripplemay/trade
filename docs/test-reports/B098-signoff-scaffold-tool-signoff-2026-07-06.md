# B098 — signoff 自动起草工具（机械 scaffold, 铁律#4-safe） — Signoff 2026-07-06

> 状态：**Evaluator 验收通过 → done**（progress.json status=verifying → done）
> 触发：F002 = Codex 独立验收（代 Codex，用户 /goal 授权 + B079–B097 先例，与实现完全隔离，最高怀疑度）。
> 裁定：**全 PASS 2/2**（F001 工具实现 + F002 独立验收）。

---

## 变更背景

test-automation roadmap **P5-F1**：signoff 自动起草工具。目的 = 让 evaluator 少写样板，工具从批次状态**机械提取**可自动填的事实（批次/feature、被验收 commit、改动文件、CI 结论、门禁 echo、生产面位置），**判断核（裁定/命门/软观察/learnings）一律留 `[待独立评估填写]` 占位**，交独立 evaluator 亲填。

- 新增文件（additive，零产品码）：`scripts/gen_signoff_draft.py`（598 行）+ `tests/unit/test_gen_signoff_draft.py`（299 行，23 测）。
- 被验收 commit：`6fc0721`（feat，工具+测试）、`ae8c1cd`（chore，mark done）、`99a3d53`（chore，开批）。

**★命门（goal 焊死）：** ①工具**不僭越判断**（铁律#4，最重）——绝不预填 verdict/裁定/命门，绝不从绿 CI 推 PASS；②**additive 零回归**——无 runtime/CI 消费者，既有 signoff 流程不变；③L1 有牙 + CI 绿 + HEAD≡prod + 产品策略码 0 行改动。

---

## 验收方法（独立，非信任实现自证）

未信任 generator 的「铁律#4-safe / render_judgment 0 参」声明，而是**逐行读工具代码 + 独立复跑门禁 + 亲自对活工具做对抗反向测试 + grep 全仓消费者**：

1. 逐行读 `scripts/gen_signoff_draft.py` 全 598 行，确认判断段渲染函数结构。
2. 独立复跑 23 单测（系统 py3 + `workbench/backend/.venv/bin/python` 双环境）+ ruff + mypy。
3. **对抗反向测试**：亲自 `python3 scripts/gen_signoff_draft.py --batch B097`（真绿 CI 批次）跑出草稿，grep 判断段是否被绿 CI 诱导出 verdict。
4. `git diff` 全仓 grep `gen_signoff_draft` 消费者 + `.github/workflows/` grep signoff wiring。
5. 独立 `gh run view` 具体 run id 复核 CI 真绿（不靠被验工具自证）。
6. `git diff --name-only` 产品路径确认 0 行产品码改动。

---

## ★命门裁定（BLOCKING 项逐条）

### 命门 1 — 工具不僭越判断（铁律#4） · **PASS（BLOCKING 清除，最重项已核）**

**(a) 结构证（代码级）：** `render_judgment_sections()` 定义为 `def render_judgment_sections() -> str:` — **零参数**，函数体是**硬编码**的章节标题 + `JUDGMENT_PLACEHOLDER.format(label=...)` 占位符列表（§7 裁定 / §8 命门 / §9 软观察 / §10 learnings 全部 `[待独立评估填写：…]`）。**判断段不接受任何批次 state 入参 → 结构上不可能从 git/gh/features 推出裁定。** 单测 `test_judgment_function_takes_no_state` 用 `inspect.signature` 断言参数数=0（有牙）。

**(b) 对抗反向测试（活工具，独立复现）：** 亲自跑 `--batch B097`（真绿 CI，3 workflow success）→ 拆分 `# 以下为判断段` banner 后半段 grep `PASS|FAIL|裁定：|全 ?PASS|→ done|✅|通过` = **NONE**。判断半段仅 4 个 `[待独立评估填写：…]` 占位。**绿 CI 未被诱导成隐式 PASS。** 无法构造让工具输出"已填 PASS"的 signoff（无输入路径能触及判断渲染器）。单测 `test_full_draft_with_all_green_ci_still_has_no_verdict_in_judgment` 同样断言此不变量。

**(c) 机械段只搬事实不搬裁定：** 逐节核——
- §4 CI：echo gh 原始 `conclusion` 字段（success/failure），**不映射为 PASS/FAIL**，表头明标「gh 的机械结论字段…非本工具或 evaluator 的裁定」。**工具不读测试结果自动判绿**，只 echo gh 词汇。
- §1 features：echo features.json 的 `status` 原字段（机械事实）。
- §5 门禁：`json.dumps(generator_handoff)` 原样 echo，标「generator **自报**…未独立复跑、未判定真伪…判定属 evaluator 职责」。
- §6 生产面：纯文件路径前缀分桶（location fact），标「非风险裁定」；单测断言输出不含 `PASS/FAIL/安全/有风险`。
- **结论：工具是辅助脚手架，结构上不做任何评估。铁律#4 未破。**

### 命门 2 — additive 零回归 · **PASS（BLOCKING 清除）**

- **无消费者**：全仓 grep `gen_signoff_draft`（*.py/*.yml/*.sh/*.toml/*.md）除自身两文件外 **命中 0**。`.github/workflows/` grep `signoff` = 空。**未接入任何 CI 硬门，不自动生成并提交 signoff。**
- **既有流程不变**：evaluator 仍可（本批即）手写 signoff，工具是**可选**辅助。read-only：仅 `git log`/`git diff --stat`/`git diff --name-only`/`gh run list` 只读命令；写只发生在显式 `-o/--output` 时（`Path(args.output).write_text`），**从不改仓库 state**；缺数据 graceful 降级为占位不 crash（单测覆盖 garbage/None/缺键/缺 binary）。
- 无硬编码 secret（grep `sk-/Bearer/password=/api_key=/token=` = 无；仅 docstring 提及）。

### 命门 3 — L1 有牙 + CI 绿 + HEAD≡prod + 0 产品码 · **PASS（BLOCKING 清除）**

- **L1 单测（23 测，有牙非平凡）**：系统 py3 **23 passed**；`workbench/backend/.venv/bin/python` 环境同样 **23 passed**。ruff **All checks passed**、mypy **Success: no issues**（backend venv）。牙齿测试：`inspect.signature` 结构证 / `collect_commits` scope-vs-body-mention 精准过滤（body 提及 B097 的 chore 被正确排除）/ all-green-CI 反向无 verdict / graceful degradation。
- **CI 真绿（独立 `gh run view` 复核，非靠被验工具自证）**：Workbench Backend CI @ `6fc0721` = success；**Python CI @ `6fc0721` = success**（该 workflow 跑 `tests/unit/` → 23 测 CI 内亦绿）；Workbench Deploy @ `ae8c1cd` = success。
- **0 产品码改动 → HEAD≡prod（产品树）**：`git diff --name-only 99a3d53^..ae8c1cd -- trade/ workbench/backend/ workbench/frontend/` = **空**。改动仅 `scripts/`（新工具）+ `tests/`（新测）+ 状态机/文档（features.json/progress.json/.auto-memory/B097 signoff md）。产品策略码逐字节未动，无回归面。
- **机械提取准确性（对 B098 自身抽验）**：3 commit 与 `git log` 逐一吻合（scope 过滤正确）；CI conclusion echo 与真 run 一致；diffstat 数字准。

---

## Workflow 对抗验证记录复核

generator_handoff 记「Workflow 3 子代理 build + 2 对抗验证 CONFIRMED survived」。本 evaluator **未止于抽查其记录，而是独立复现了同一对抗测试**（命门 1(b) 活工具反向跑 + grep NONE），并佐以 23 测中的 `test_full_draft_with_all_green_ci_still_has_no_verdict_in_judgment` 与 `test_judgment_function_takes_no_state` 双重结构不变量。独立复现结论与 generator 记录一致：**绿 CI 不推裁定，铁律#4 结构性成立**。

---

## 裁定

| feature | 标题 | 裁定 |
|---|---|---|
| F001 | P5-F1 signoff 机械起草工具 | **PASS** |
| F002 | Codex 独立验收 + signoff | **PASS** |

**全 PASS 2/2 → done。** test-automation roadmap **generator-buildable 部分全落地（P0–P5-F1）**。剩余 P5-F2（独立评审流程触发点）= evaluator 流程域，非 generator 可有意义构建，不含本批。

---

## 软观察（soft-watch，非阻断）

- **S1**（设计 nit）：§5 门禁 echo 的是**整个** `generator_handoff.summary` 叙事 blob，本仓中它含 generator 自拟的「signoff / 守铁律4 / 机械提取正确」框架性措辞。**已明标「自报/未判定真伪」且置于机械半段（§7 裁定仍空占位）→ 不破铁律#4**，但未来加固可只 echo 结构化门禁数字（tests/ruff/mypy）以最小化对 generator 框架的锚定。非缺陷。
- **S2**：commit-range 启发式 `oldest^..newest` 使 §3 diffstat 纳入开批 chore commit（`99a3d53`）里与 F001 工具无关的文件（B097 signoff md、auto-memory 编辑）。作为「本批 commit 范围内改了什么」是机械正确的原始事实，非 bug；evaluator 读草稿时需知 diffstat 范围宽于单一 feature。
- **S3**：本机 `python3=3.9.6` 无 ruff/mypy，须用 `.venv`/backend venv 跑门禁（project-status 已知 gap 已记）。非工具缺陷。

---

## 证据索引

- 工具：`scripts/gen_signoff_draft.py`（598 行，`render_judgment_sections()` @ L502 零参）
- 测试：`tests/unit/test_gen_signoff_draft.py`（299 行，23 测；结构证 @ L160、反向证 @ L168）
- 对抗草稿产物：`--batch B097` 判断半段 grep verdict = NONE（本地复现）
- CI：Backend CI + Python CI @ `6fc0721` success、Deploy @ `ae8c1cd` success（`gh run view` 独立复核）
- 消费者 grep：`gen_signoff_draft` 外部命中 0、`.github/workflows/` signoff wiring 空
- 产品码 diff：`99a3d53^..ae8c1cd -- trade/ workbench/backend/ workbench/frontend/` = 空
