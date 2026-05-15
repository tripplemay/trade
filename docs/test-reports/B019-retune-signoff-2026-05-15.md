# B019-retune-signoff-2026-05-15

> 状态：**Evaluator 复验通过**（progress.json status=done）
> 触发：B019 F005 完成，B013 在 F002 winning cell `('quarterly', 0.11)` 上完成默认值变更与回归签收

---

## 变更背景

B019 的目标是基于 B018 attribution 结论，对 B010 / B013 的 `(cadence, vol_target)` 邻域做真实数据 retune 裁决，并在 gate 命中时只更新命中的策略默认值。  
F002 结果显示 B013 的 `('quarterly', 0.11)` 通过四条 gate，B010 未达标，因此 Stage 2 只应改 B013。

---

## 变更功能清单

### F001：Sweep harness fine-grid extension

**Executor：** generator

**文件：**
- `trade/analysis/parameter_sweep.py`
- `tests/unit/test_parameter_sweep_b019.py`

**改动：**
增加 joint cadence × vol-target sweep 与 retune gate verdict 数据结构和测试。

**验收标准：**
- 592 条测试全通过
- B018 既有 sweep 测试无回归

### F002：Stage 1 real-data sweep + Pareto verdict

**Executor：** codex

**文件：**
- `docs/test-reports/B019-retune-sweep-2026-05-15.md`
- `docs/test-reports/B019-retune-sweep-2026-05-15.json`

**改动：**
在 B014 real snapshot 上完成 B010 / B013 sweep、gate 裁决与 Pareto 推荐。

**验收标准：**
- B010 `gate_met=False`
- B013 `gate_met=True`，`winning_cell=('quarterly', 0.11)`

### F003：B013 default mutation

**Executor：** generator

**文件：**
- `trade/strategies/regime_adaptive/config.py`
- `tests/unit/test_regime_adaptive_config.py`
- `tests/unit/test_parameter_sweep_b019.py`

**改动：**
B013 默认值更新为 `quarterly / 0.11`，并同步更新相关 baseline 断言。

**验收标准：**
- 默认值变更能通过参数哈希与 baseline 测试
- B010 默认值保持不变

### F004：B011 / B014 / B015 联动

**Executor：** generator

**文件：**
- `scripts/generate_b019_default_change_baseline.py`
- `scripts/generate_b015_activation_policy_report.py`
- `docs/test-reports/B019-default-change-baseline-2026-05-15.md`
- `docs/test-reports/B019-default-change-baseline-2026-05-15.json`
- `docs/test-reports/B019-b015-activation-policy-rerun-2026-05-15.md`
- `docs/test-reports/B019-b015-activation-policy-rerun-2026-05-15.json`

**改动：**
生成新默认值基线 sidecar，并补出 B015 激活策略真实数据 rerun 报告。

**验收标准：**
- `B019-default-change-baseline` 真实数据数值与 F002 winning cell 匹配
- `B019-b015-activation-policy-rerun` 真实数据状态为 `ran`

### F005：Evaluator 复验 + signoff

**Executor：** codex

**文件：**
- `docs/test-reports/B019-retune-signoff-2026-05-15.md`
- `progress.json`
- `.auto-memory/project-status.md`
- `backlog.json`

**改动：**
执行全量测试、真实数据数值复验、签收、状态机收口、backlog 结案。

**验收标准：**
- `pytest tests/ -q` 全 PASS
- `ruff check trade tests scripts` 通过
- `mypy trade` 通过
- `compileall -q trade tests scripts` 通过
- B013 新默认值 real-data 结果与 F002 预测一致

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| `trade/` 其他策略逻辑 | B010 未改，其他策略默认值未调整 |
| 运行边界 | 不引入 broker / paper / live / secret / AI 执行 |
| 测试体系 | 仅补充和运行验证，不改测试框架结构 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| B013 默认 cadence | `monthly` | `quarterly` |
| B013 默认 target volatility | `0.08` | `0.11` |
| B010 默认值 | `monthly / 0.08` | `monthly / 0.08` |

---

## 类型检查 / CI

```text
.venv/bin/python -m pytest tests/ -q
592 passed in 8.78s

.venv/bin/python -m ruff check trade tests scripts
All checks passed!

.venv/bin/python -m mypy trade
Success: no issues found in 49 source files

.venv/bin/python -m compileall -q trade tests scripts
passed
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| 真实 snapshot | `data/public-cache/regime-adaptive-prices-manifest.json`，snapshot `regime-adaptive:b69883b08eedea7d` |
| 数值确定性 | B013 `('quarterly', 0.11)` 在 `B019-default-change-baseline` 中与 F002 预测逐项一致，浮点误差在 1e-13 量级 |
| B015 rerun | `B019-b015-activation-policy-rerun-2026-05-15` 已更新为 `real_data_status=ran` |

---

## Harness 说明

本批次按 Harness 状态机完成 `planning → building → verifying → fixing → reverifying → done` 交付。  
`progress.json` 已设为 `status: "done"`，`docs.signoff` 已填入本报告路径。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | `scripts/generate_b015_activation_policy_report.py` 的默认全量 snapshot 路径会撞到 T+1 open execution 边界；Evaluator 已通过保留 one-trading-day headroom 的方式补出 real-data rerun。 | low | 后续若要无人值守复跑，建议脚本默认窗口预留尾部 headroom 或显式截断最后一个 signal date。 |

---

## Framework Learnings

### 新规律
- 当月度 T+1 执行模型消费 snapshot 尾部数据时，必须保留至少一个交易日 headroom，否则最后一个 signal date 会触发 `no trading date exists after signal_date` 类边界错误。

### 新坑
- B015 激活策略重跑在真实 snapshot 尾部需要留一日缓冲；否则虽然数据存在，执行日却可能不存在。

### 模板修订
- 后续 B015 类 report script 可考虑在默认窗口上自动 trim 最后一个 signal date，或者在 CLI 里显式记录 tail headroom。

---

_Disclaimer: research-only; never authorizes paper or live trading._
