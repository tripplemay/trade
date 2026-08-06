# B112 F002 Fix-Round 1 复验 2026-08-06

> 状态：**FAIL**
>
> 裁定：pure mode **NO-GO**；quality mode 的 100 万机制档 **NO-GO**、10 万容量档
> **GO**。裁定输入已可独立复算，但 F001 的 H6 披露和 V0 零回归证据仍未闭环，
> 本批次不得 signoff。

## Scope

- 复验首轮 B112-F001-1~5、F001/F002 acceptance、spec §1/§2 及 H1-H6。
- 真实本地 1500 PIT 宇宙、价格、基本面与 CSI300 数据；完整 8-cell 空 cache 回测。
- 本批零生产接入；未执行生产写入、外部通知、broker、订单或付费 API。
- 验收前 `git pull --ff-only origin main`：`Already up to date.`；产品实现 HEAD
  `93c1fd4`，其 Python CI、Workbench Backend CI、Deploy、Prod Canary 均 success。
  `93c1fd4..23bc5d7` 只含研究结果和状态文件，不改变产品运行时。

## Verification

| 检查 | 结果 |
|---|---|
| 定向 L1 | `pytest test_cn_attack_defense_gate.py test_b112_defense_gate_ab.py -q` → **17 passed** |
| 类型/静态 | `ruff check .` → PASS；`mypy trade` → PASS |
| 独立复算 | `scripts/test/b112_verify_artifact.py`：delta、70/30、MA200、1500 宇宙、输入计数和年化换手均匹配；价格 splice 披露 FAIL |
| 空 cache 全矩阵 | 临时全新 cache 完整跑完 2 mode × 2 arm × 2 capital，8/8 无异常；未读取原 pickle cell cache |
| fresh cell 对拍 | pure/V0/10万与交付值仅 5 个 IEEE-754 末位差异，最大约 `3e-13`，无决策指标漂移 |
| 1500 宇宙 | 45,000 行、30 块、每块 1,500、3,907 个唯一证券；rank 1..1500 连续，无重复/空值，仅 `.SH/.SZ` |

独立证据：

- `docs/test-reports/B112-F002-independent-evidence-2026-08-06.json`
- `docs/test-reports/B112-F002-empty-cache-rerun-2026-08-06.json`
- `docs/test-reports/B112-F002-fresh-cell-diff-2026-08-06.json`

空 cache 全 payload 的 canonical hash 不同：交付 `374aee7...`、fresh `a29d9bd...`。
代表 cell 字段级 diff 证明差异来自浮点累计末位，不跨越任何判据边界；后续复验应使用
数值容差比较，不能把 canonical JSON hash 当作浮点回测的稳定等价判据。

## Resolved Findings

| 首轮 finding | 结果 | 证据 |
|---|---|---|
| B112-F001-1 冻结宇宙错误 | PASS | runner 切到 30×1500 PIT 块，生产同款 `point_in_time_top_n`，空 cache 8 cell 跑通 |
| B112-F001-2 HEAD quality 不可复跑 | PASS | 原始 CSV 日期解析/schema 补齐；quality 4 cell 从空 cache 全程无 TypeError |
| B112-F001-3 缺评估日未 fail-open | PASS | `fail_open_missing_eval_date`；Evaluator 对抗用例通过 |
| B112-F001-4 报告字段缺失 | PARTIAL | OOS Sharpe、年化换手、覆盖结构已补；价格来源仍漏新名段，见新 finding 4a |
| B112-F001-5 V0 byte 零回归 | PARTIAL | 测试字段比较已扩充，但仍未对 pre-B112 基线，见新 finding 5a |

## Independent Adjudication

| mode | 本金角色 | ΔMaxDD 全样本 | ΔMaxDD OOS | ΔCAGR | ΔSharpe | 判据结果 |
|---|---|---:|---:|---:|---:|---|
| pure | 10 万容量 | +10.75pp | **-2.93pp** | +3.47pp | +0.179 | **NO-GO**（主 B 未过） |
| pure | 100 万机制 | +22.05pp | **-0.73pp** | +2.23pp | -0.027 | **NO-GO**（主 B 未过） |
| quality | 10 万容量 | +18.13pp | +5.62pp | +1.92pp | +0.115 | **GO** |
| quality | 100 万机制 | +8.15pp | **+1.78pp** | -1.82pp | +0.012 | **NO-GO**（主 B 未过） |

- **pure mode：NO-GO。** 机制档与容量档都未通过 OOS MaxDD +3pp 主门。
- **quality mode：NO-GO（机制档）。** 10 万容量档通过，但 100 万机制档 OOS
  MaxDD 仅 +1.78pp，按“主判据任一不过”规则不得放行机制。
- OOS Sharpe/CAGR 不用于覆盖 OOS MaxDD 主门；未触发任何敏感性或改档条款。

## Residual Findings

### B112-F001-4a

- **Severity:** medium
- **Finding:** H6 价格/指数来源披露仍不完整且有错误标签。
- **Evidence:** 实际 runner 输入为 base `2,467,137` 行 + ext `44,660` 行 +
  `prices_newnames.pkl` `3,219,272` 行，去重后恰为报告的 `5,731,069` 行；但
  `input_coverage.prices.splice` 和 Markdown 只写前两段，漏掉占半数以上的新名价格。
  Markdown 又把 `1780` 写成“日历日覆盖”，实际窗口有 2,679 个日历日、1,780 个
  交易日，正确口径应为指数交易日覆盖 `1780/1780`。
- **Required Fix:** JSON/Markdown 明列三段价格输入、各段行数及去重规则；指数披露改成
  `window_trading_days_covered / window_trading_days_total = 1780/1780`，不得使用
  “日历日 1780”措辞。保留 verifier 的 `h6_price_splice_discloses_new_names` 门禁。

### B112-F001-5a

- **Severity:** medium
- **Finding:** V0 “byte 零回归”测试仍是同一实现的等价配置对比，未证明 pre-B112
  引擎行为未漂移。
- **Evidence:** `CnAttackBacktestConfig()` 与
  `CnAttackBacktestConfig(defense_gate=None)` 结构上完全相等，二者都调用当前 HEAD
  的同一 `run_cn_attack_backtest`；复验实测 `configs_equal=True`。扩充比较字段只能
  证明确定性，不能证明与 `2e81836` 前基线相同。
- **Required Fix:** 从 pre-B112 commit `2e81836` 对固定合成输入生成 golden 输出/hash，
  当前 `defense_gate=None` 必须逐字段对拍该固定基线；至少覆盖 equity curve、daily
  records、终值、成本、换手、调仓数和退出数。不得用当前默认配置作为“旧基线”。

## Frozen Clause Review

### §1 冻结口径

| 条款 | 结果 | 证据摘要 |
|---|---|---|
| 现引擎 + B081 开关 / PRB=False | PASS | runner 使用现引擎默认保真配置 |
| top~1500 PIT / 生产同源 | PASS | 30 块×1500，生产同款排序函数，输入/板块边界有留痕 |
| 2019-04-01→2026-07-31 | PASS | 独立确认 1,780 交易日 |
| 70/30 | PASS | 独立机械分割 `2024-05-22`，8 cell 一致 |
| 10 万 + 100 万 | PASS | 两档并排，资本角色分别裁定 |
| 现 CnCostModel | PASS | runner 未覆盖成本模型 |
| V0 两 mode / 生产参数 | PARTIAL | 参数正确；pre-B112 byte 基线证据仍缺 |
| V1 MA200 / 次月现金 / 无前视 | PASS | 88 月状态独立重建匹配 |
| MA200 禁扫参 | PASS | 单一默认 200，无扫描 |
| 指数缺失 fail-open + flag | PASS | 精确评估日缺失返回可见 fail-open reason |
| 两 mode 独立 | PASS | pure/quality 独立四组 comparison |

### §2 预注册判据

| 条款 | 结果 | 证据摘要 |
|---|---|---|
| 主 A 全样本 +5pp | PASS | 四档均可独立复算 |
| 主 B OOS +3pp | 触发 NO-GO | 仅 quality 10 万通过；其余三档未过 |
| 副 C CAGR -2pp / Sharpe -0.05 | PASS | 四档均未越界 |
| mode 独立、资本角色分开 | PASS | pure/quality 与 10万/100万逐档陈述 |
| 全/OOS 与年化换手披露 | PASS | 指标列齐全、公式精确 |
| H7 Generator 只算不裁 | PASS | Generator 产物无结论性措辞 |

### §3 H1-H6

| 条款 | 结果 | 证据摘要 |
|---|---|---|
| H1 零生产接入 | PASS | 无 strategy_modes/precompute/timer 接入 |
| H2 无交易信号/readiness | PASS | 无生产信号或 flag 变更 |
| H3 不新增 alpha | PASS | 仅 MA200 风险覆盖层 |
| H4 不用 -41% 拟合/挑窗 | PASS | 冻结窗口未变，保留诚实性声明 |
| H5 单一 MA200 | PASS | 无参数扫描/第二闸型 |
| H6 覆盖不足结构化呈现 | PARTIAL | 分母已补，但价格第三段遗漏、指数标签错误 |

## Ops Side Effects

本轮无生产或数据库 ops。空 cache 使用 Python `TemporaryDirectory`，结束后自动清理；
仓库原始 `data/research/b112/ab_cache` 未改变。

## Conclusion

三项 High 已修复，正式裁定已从 INCONCLUSIVE 收敛为：pure **NO-GO**、quality
100 万机制档 **NO-GO**（10 万容量档 GO）。但 F001-4a/F001-5a 均是 hard
acceptance 的证据缺口，不能作为 soft-watch 放行。状态回 `fixing`，`fix_rounds` 保持
1，`docs.signoff` 保持 null；下一轮只需复验两项 residual finding 和重新渲染产物。
