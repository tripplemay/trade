# B110 纯 E/P first-look Signoff 2026-07-21

> 状态：**PASS（验收完成）**
> 
> F004 裁定：**INCONCLUSIVE_COVERAGE_LIMITED**（保守采用冻结附录 D1/D6 的非决策档）
> 
> 触发：`verifying` 首轮验收，F001-F003 已交付，F004 由 Codex 独立执行。

## Scope

本轮验收覆盖 B110 的研究型 first-look：PIT TTM、2013-01 至 2024-12 的 144 个自然月末面板、双口径 E/P 分组统计、拆腿归因、覆盖漏斗和预注册裁定。没有执行 L2 staging 或真实外部付费调用；本批次没有产品 runtime、broker、下单、计费或 `DATA_NO_GO` 变更。

使用的源文档和产物：

- `docs/specs/B110-pure-ep-first-look-spec.md`
- `docs/specs/B110-frozen-conventions-addendum.md`
- `docs/audits/B110-F001-real-data-validation-2026-07-21.md`
- `docs/audits/B110-F002-panel.json`
- `docs/audits/B110-F002-monthly-funnel.csv`
- `docs/audits/B110-F002-tushare-silent-empty-response-2026-07-21.md`
- `docs/audits/B110-F003-signal-stats.json`
- `docs/test-reports/B110-F004-evidence-2026-07-21.json`

## 验收方法

Codex 使用独立脚本 [`b110_f004_verify.py`](/Users/yixingzhou/project/trade/scripts/test/b110_f004_verify.py)，不导入 B110 的 TTM 或信号统计计算入口。脚本直接读取原始 `income_rt1` / `income_rt2` 缓存和 `ep_panel.csv.gz`，用固定 seed `B110-F004-codex-independent-sample-v1` 每年自选 5 个证券-形成日，共 60 个样本；随后独立重算四分量、两条 TTM 路径、E/P、月度分组和拆腿。

## 实测证据（决策级/真数据）

命令：

```bash
.venv/bin/python scripts/test/b110_f004_verify.py
.venv/bin/python -m scripts.research.ashare_pit.signal_stats_cli \
  --detail data/research/B110/ep_panel.csv.gz \
  --out /tmp/B110-F003-signal-stats-recomputed.json
.venv/bin/python -m pytest -q \
  tests/unit/test_ashare_pit_ttm.py \
  tests/unit/test_ashare_pit_ep_panel.py \
  tests/unit/test_ashare_pit_ep_panel_cli.py \
  tests/unit/test_ashare_pit_returns.py \
  tests/unit/test_ashare_pit_signal_stats.py
.venv/bin/python -m ruff check scripts/test/b110_f004_verify.py
```

结果：

- 独立 TTM 样本 **60/60**，覆盖 2013-2024 每年 5 个样本；四个分量均以 formation date 重新取 raw `f_ann_date`。四分量共 **240/240** 个可用 `report_type=2` 对拍为 `MATCH`，`BREAK=0`，等价式 `path_a == path_b` 全部成立，且每个样本与面板 `ttm_cny`、`ep` 逐字匹配。
- 独立拆腿重算 **144/144 月**：主口径 `stub=0.00` 的 `a_long_ann=-0.323662%`、`a_short_ann=+0.621501%`、算术多空 `+0.297839%`；月度加法最大残差 `3e-29`。这说明可做的多头腿本身为负，不能用 IC 或空头腿贡献替代 long-only 判据。
- 144 行覆盖漏斗 `formation_seq=1..144`，端点为 `20130131` / `20241231`；最差联合覆盖 `71.6906%`，中位 `90.5592%`，最小负 TTM 数量 `187`，`period_not_fetched=0`，畸形证券行 `0`。每月按分子→分母→收益优先级的阶段恒等式闭合。
- `docs/audits/B110-F002-panel.json` 的 R1 `ttm_step_without_filing=0`；逐年 TTM 损失无 2022 年式尖峰。全量缓存扫描 **863** 个文件，恰为 5,000 行的缓存 **0** 个；6 个空文件分别是 `stock_basic_P` 与没有终值行情的 `daily_terminal_*`，不是取值源短表。
- 相关单测 **93 passed**；验收脚本 ruff **All checks passed**。独立重算 CLI 的四个 variant 与交付 `B110-F003-signal-stats.json` 的关键统计全部逐项相等。

## F001-F004 逐项结果

| Feature | 结果 | 证据与说明 |
|---|---|---|
| F001 PIT TTM 分子 | PASS | 3 个真实公司样本已在 F001 报告；本轮再以 60 个自选证券-形成日直接读 raw 缓存复算，四分量独立 as-of、Decimal、等价式和 R2 对拍均通过。全量 `CUMULATIVE_BASIS_BREAK=7,949` 已 fail-closed，不被误当作通过。 |
| F002 144 月面板与漏斗 | PASS | 144 个连续形成日、双口径字段、负 TTM 保留、漏斗阶段闭合、`period_not_fetched=0`、最差联合覆盖 71.6906%。修复后的缓存没有 5,000 行整页边界残留。 |
| F003 信号统计 | PASS | CLI 离线重算 144 月；主口径及三档退市 stub、剔负对照组均有结果；H7 产物只含原始统计，F003 JSON 不含裁定措辞。 |
| F004 Codex 独立验收/裁定 | PASS | 本报告及 [`B110-F004-evidence-2026-07-21.json`](/Users/yixingzhou/project/trade/docs/test-reports/B110-F004-evidence-2026-07-21.json) 为交付物。 |

## 预注册裁定

主口径是 `main_stub_0.00`，剔除负 TTM 的 variant 不参与裁定。按用户冻结 D2 的几何年化，独立重算与交付统计为：

| 口径 | Top 几何年化超额 vs B-scored | 正超额年份 | 字面单调性 / Q5 最优 | B-scored − B-wide |
|---|---:|---:|---|---:|
| `main_stub_0.00`（主） | **0.9606%** | **7/12** | `false / false` | **-1.7225pp** |
| `main_stub_-0.30` | 1.0201% | 7/12 | `false / false` | -1.7168pp |
| `main_stub_-1.00` | 1.1587% | 7/12 | `false / false` | -1.7034pp |
| `excl_negative_stub_0.00`（对照，不裁定） | 0.7240% | 6/12 | `false / false` | -1.6514pp |

主口径五组几何年化收益为 Q1 `10.1465%`、Q2 `8.4236%`、Q3 `12.1092%`、Q4 `14.2791%`、Q5 `12.7489%`；Q5 不是最优。IC 均值 `0.03020`、IC IR `0.2155` 只作辅助诊断，不改变 long-only 裁定。

严格按原 spec §4，主口径的 `0.9606% <= 1.0%`、正超额 `7/12 < 60%`、Q5 非最优均触发负向条件。与此同时，冻结附录 D1 明确规定 B-scored/B-wide 构成差超过 1.0pp 时进入 `INCONCLUSIVE_COVERAGE_LIMITED`，D6 又规定任一 stub 跨越判据边界时进入 `INCONCLUSIVE`；本轮三档从 0.9606% 跨到 1.0201% / 1.1587%。冻结规则没有定义 NO-GO 与 D1/D6 的优先级，因此本报告采用不放宽数据限制的保守裁定：**`INCONCLUSIVE_COVERAGE_LIMITED`**，并把主口径的负向证据完整保留，不将其改写成正向结论。该裁定不是策略 readiness，也不改变 `DATA_NO_GO`。

## H1-H7 边界审查

| 边界 | 结果 | 证据 |
|---|---|---|
| H1 不改产品代码 | PASS | `git diff --name-only 4a22ab1^..HEAD` 无 `trade/`、`workbench/`、`prisma/`、`sdk/` 路径；本轮新增仅 `scripts/test/` 与 `docs/test-reports/`。 |
| H2 不产生可交易信号/自动下单 | PASS | B110 只落盘研究面板和统计；无 readiness、broker、order 或 validated 状态变更。 |
| H3 保持 `DATA_NO_GO` | PASS | 无产品文件改动，`progress.json` 明确写入“不改 DATA_NO_GO”。 |
| H4 覆盖不足结构化、负 TTM 不静默剔除 | PASS | 144 月漏斗闭合；所有月份 `n_neg_ttm>0`；阶段码和 `CUMULATIVE_BASIS_BREAK` 独立披露。 |
| H5 分页统一使用 `fetch.py` | PASS | `ep_panel_cli.py` 的所有取值端点通过 `_fetch_cached -> fetch_paged`；整页边界重取、行数下限、长退避和原子缓存均有代码与单测证据。 |
| H6 token 不入仓/日志 | PASS | `.env.local` 被 `.gitignore` 忽略且未被 `git ls-files` 收录；本轮产物无 token 值。 |
| H7 Generator 不下裁定 | PASS | `B110-F003-signal-stats.json` 对禁用 verdict 词扫描为 0；其 `generator_boundary` 明确把裁定交给 F004。F002 审计中的一次“NO-GO 线”仅为阈值污染风险说明，不是统计裁定。 |

## Git 冻结与 CI

- `e4206b6` 是冻结附录提交；该提交时仓库不存在 B110 面板、E/P 或组合收益产物。`git diff e4206b6..HEAD -- docs/specs/B110-*` 为空，阈值和 D1-D8 未被结果反推。
- 实现提交 `ea7cae7` 的 Python CI run `29850500800`、Workbench Backend CI run `29850500257` 均为 `success`；随后 metadata-only HEAD `4a187cc` 的 Workbench Deploy run `29851107442` 为 `success`。
- 这是纯本地 research-only 批次，无 staging 端点、数据库写入或 L2 外部调用；Production / HEAD 等价性不适用，写为 N/A。签收提交只含测试证据和状态机元数据，不需要 post-signoff deploy。

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 原 spec 的 NO-GO 条件与冻结附录 D1/D6 的 INCONCLUSIVE 条件可以同时触发，未定义优先级。本轮用 `INCONCLUSIVE_COVERAGE_LIMITED` 保守收口，主口径负向证据仍完整披露。 | medium | 下一次 first-look 前由 Planner 在冻结附录中写明条件优先级或采用组合裁定表；本批次不修改已冻结 spec。 |
| S2 | 成本数字分布在 `B110-F002-panel.json` 的缓存复用运行（24 calls / 61,550 rows / 138.2s）与状态机/项目快照记录的首次全量运行（537 calls / 1.058M rows / 3,159s）。 | low | 后续批次把首次全量与增量运行合并为单独 cost ledger，避免读者把缓存复用运行误读为全量成本。 |
| S3 | D1 的构成效应以几何年化之差披露，文本没有明确“超过 1.0pp”取绝对值还是带符号值；本轮按“差”的绝对值解释。 | low | Planner 在下一份冻结口径中明确 signed/absolute 语义。 |

## Framework Learnings

### 新规律

- first-look 同时存在“主判据负向”与“覆盖构成/敏感带不确定”时，冻结规则必须定义优先级；否则单一三档枚举不是互斥完备的裁定空间。建议由 Planner 追加到 `framework/proposed-learnings.md`，用户确认后再沉淀。

### 新坑

- 分页源的缓存扫描应把“恰为页大小”“空的诊断终值文件”和“空的取值源文件”分成三个独立检查；本轮 863 个缓存的 5,000 行扫描通过，但空文件只有在结合端点语义后才能判为合法。

### 模板修订

- 建议 `framework/templates/signoff-report.md` 的裁定段增加“原始判据触发项”和“覆盖/敏感性覆盖项”两列，避免 evaluator 只能在 prose 中解释非互斥条件。

## Conclusion

F001-F004 的验收交付全部通过，F004 的独立裁定为 **`INCONCLUSIVE_COVERAGE_LIMITED`**。本批次达到签收条件，可将状态机推进到 `done`；该结论仅回答是否应继续投入 B110 后续 handoff gate 的研究决策，不是可交易策略、收益承诺或数据地基 readiness。`DATA_NO_GO` 保持不变。
