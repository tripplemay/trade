# B012 Paper Trading Prep MVP Signoff 2026-05-14

> 状态：**Evaluator 已签收**（progress.json status=done）
> 触发：B012 `verifying` 阶段 L1 验收完成，全部检查通过

---

## 变更背景

B012 交付的是研究回测到未来 paper/live 适配之间的接口边界，不是实盘执行系统。此次验收确认 Target Positions schema、Broker Adapter 抽象、Mock Broker journal-only、以及 Backtest-to-Paper bridge 都符合 spec，并且没有引入 forbidden broker SDK、network、secret 或 paper/live execution 语义。

---

## 变更功能清单

### F001-F005：B012 Paper Trading prep MVP

**Executor：** generator

**文件：**
- `trade/paper_prep/target_positions.py`
- `trade/paper_prep/broker_adapter.py`
- `trade/paper_prep/mock_broker.py`
- `trade/paper_prep/bridge.py`
- `tests/unit/test_target_positions.py`
- `tests/unit/test_broker_adapter.py`
- `tests/unit/test_mock_broker.py`
- `tests/unit/test_paper_prep_bridge.py`
- `tests/unit/test_paper_prep_safety_guards.py`

**改动：**
实现 research-only 的 Target Positions 双输出 schema、BrokerAdapter 抽象接口、MockBroker journal-only 适配器、Backtest-to-Paper bridge，以及对应的安全回归。

**验收标准：**
- TargetPositions 同时输出百分比权重与美元 exposure，并通过校验
- BrokerAdapter 仅保留抽象方法，不依赖真实 broker SDK
- MockBroker 只追加 JSON Lines journal，不模拟成交，不触网，不读环境变量
- bridge 支持任意时间手动触发，`signal_date` 无匹配时 fail closed
- safety guard 覆盖 forbidden imports、API host、execution language、env/secrets、network

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 真实 paper/live broker adapter | B012 明确不实现，留给后续批次 |
| 任何产品实现代码 | 本轮只做验证与签收，不改 `src/` 类实现 |
| staging / production 交互 | 本轮为 L1 本地验收，未做 L2 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| Paper Trading prep 接口边界 | 无 | 已具备 |
| Mock Broker 意图记录 | 无 | JSON Lines append-only journal |
| 安全回归覆盖 | 部分 | B012 相关 forbidden 面已被测试锁定 |

---

## 类型检查 / CI

```text
.venv/bin/python -m pytest tests/unit/test_target_positions.py tests/unit/test_broker_adapter.py tests/unit/test_mock_broker.py tests/unit/test_paper_prep_bridge.py tests/unit/test_paper_prep_safety_guards.py
60 passed

.venv/bin/python -m pytest
219 passed

.venv/bin/ruff check .
All checks passed!

.venv/bin/python -m compileall trade
OK

.venv/bin/mypy
Success: no issues found in 33 source files
```

---

## L2 实测记录

无 staging 影响 - N/A

---

## Ops 副作用记录

本批次无数据库 ops。

---

## Harness 说明

本批次经 Harness 状态机验证完成。
`progress.json` 已更新为 `status: "done"`，`docs.signoff` 已填入本报告路径。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 系统默认 `python3` 为 3.9，不满足仓库 `>=3.11` 要求；本轮改用 `.venv/bin/python` 完成验收 | low | 后续本机验证继续固定使用 `.venv/bin/python` |

---

## Framework Learnings

本批次无 framework learnings。
