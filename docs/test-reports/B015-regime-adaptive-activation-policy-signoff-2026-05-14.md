# B015 Regime-Adaptive Activation Policy Signoff 2026-05-14

> 状态：**Evaluator 已签收**（progress.json status=done）
> 触发：B015 `verifying` 阶段 L1 验收完成

---

## 总体结论

B015 通过验收。`regime_activation_policy` 枚举、校验、`should_l1_gate_run` 9 组 truth table、`always_on` backwards-compat、比较报告、以及安全回归都通过。

当前仓库未包含 B014 真实 snapshot manifest，因此比较报告的 real-data 分支按 spec 走 `skipped`。这符合验收要求，不构成失败。

---

## 验证结果

### F001 配置字段与校验

**结果：PASS**

- `RegimeAdaptiveConfig.regime_activation_policy` 存在，默认值为 `always_on`
- 仅允许 `always_on` / `only_non_normal` / `only_crisis`
- `parameter_hash()` 已包含该字段

### F002 L1 gating 条件启用

**结果：PASS**

- `should_l1_gate_run(regime_label, policy)` 覆盖 9 组组合
- `always_on` 在所有 regime 下都返回 `True`
- backtest 在 policy-skipped 时会绕过 L1 gating，并记录 `l1_active`

### F003 / F004 比较报告

**结果：PASS**

- 比较报告文件存在
- 三个 policy 行存在
- B006 / B010 / static 60/40 baseline 行存在
- 2020 / 2022 stress verdict per policy 已写入
- real-data section 在 manifest 缺失时正确标记为 `skipped`

### F005 Backwards-compat 与安全回归

**结果：PASS**

- `always_on` 与 B013 既有 fixture 行为一致
- 无新增 broker / AI / env / socket 访问风险
- 报告文本未引入 paper/live 执行表述

---

## 类型检查 / CI

```text
.venv/bin/python -m pytest
423 passed

.venv/bin/ruff check .
All checks passed!

.venv/bin/python -m compileall trade
OK

.venv/bin/mypy
Success: no issues found in 44 source files
```

---

## L2 实测记录

无 staging 影响 - N/A

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | B015 比较报告的 real-data 分支当前为 `skipped`，因为仓库里未包含 B014 manifest | low | 后续若恢复 B014 snapshot，可重新跑 `scripts/generate_b015_activation_policy_report.py` 生成 real-data 版本 |

---

## Framework Learnings

本批次无 framework learnings。

