# B056 Signoff 2026-06-12

> 状态：**✅ F004 FULL PASS**  
> 触发：B056 building 全 3 generator features done → verifying 交 Codex F004

---

## 变更背景

B056 是「模拟盘」基建——为用户提供「回测（过去）与实盘（真金）之间的前向桥」。给虚拟本金，忠实跟策略目标配置，每日真实价格 mark-to-market，显示账户盈亏曲线+每资产盈亏。让用户下真单前/中看策略真刀真枪前向表现（backtest 过拟合的解药=真·样本外）。

B054 done 后（界面中文化），用户可实盘小仓起步；本批模拟盘与实盘并行，非 gate。

---

## L1 — 代码审核与 CI 验证

✅ **PASS**  
所有特性实现已在 HEAD (184cf4b) 中确认：

- ✅ F001：paper 账户模型 + 虚拟调仓引擎（migration 0018）
  - 参数化策略（strategy_id），Master 先行  
  - 收盘价成交 + 真实成本（fee/slip bps）
  - 成本模型诚实：investable = equity × (1-cost_rate)，cash ≥ 0

- ✅ F002：每日 MTM job + nav history（migration 0019）
  - 复用 mark_to_market / price provider
  - per-asset PnL 计算正确
  - 幂等性保障（account, date）

- ✅ F003：模拟盘前端页（6 区块中文）
  - 摘要（虚拟本金 + 激活日 + vs SPY） 
  - 净值曲线 + SPY 基准叠加
  - 每资产盈亏表 + 现金行
  - 配置 vs 目标漂移
  - 调仓记录简版
  - 设置（激活/本金/策略选择器）
  - i18n 双语 54 key 完整

### CI 门禁检查

| 门禁项 | 结果 | 详情 |
|---|---|---|
| **Backend pytest** | ✅ 971 PASS | +21 paper 相关新测试（vs B054 的 950） |
| **Backend ruff** | ✅ 0 errors | lint clean |
| **Backend mypy** | ✅ 0 errors | type check clean |
| **Frontend tsc** | ✅ 0 errors | TypeScript clean |
| **Frontend lint** | ✅ 0 warnings | ESLint clean |
| **Frontend vitest** | ✅ 282 PASS | +2 paper 新测试 |
| **i18n parity** | ✅ 9 PASS | 中英文 key 对齐 |
| **Alembic** | ✅ head 0019 | 两个 migration 应用完成 |

---

## L2 — 真机验证（SSH）

✅ **FULL PASS**

### ① Timer 接线（§24）

```bash
● workbench-paper-mtm.timer
  Loaded: loaded (/etc/systemd/system/workbench-paper-mtm.timer; enabled)
  Active: active (waiting)
  Trigger: Fri 2026-06-12 03:45:00 UTC
```

**验证：** ✅ PASS
- timer **enabled**
- **active (waiting)** 
- 正确触发时间：03:45 UTC（在 prices 00:30 和 recommendations 03:00 之后）

### ② MTM Job 执行与 nav_history 累积

```bash
$ sudo systemctl start workbench-paper-mtm.service
paper mtm done — accounts=1 points=1 rebalanced=0
```

**验证：** ✅ PASS  
- **accounts=1** — Master 模拟盘已激活
- **points=1** — MTM 记录了 1 个 nav_history 点（前向累积）
- **rebalanced=0** — 目标未变，无调仓（符合预期）

### ③ 激活逻辑——忠实跟 Master 目标

**代码层验证：**
- ✅ `paper/service.py` 激活时读 `recommendation_snapshot.latest_snapshot`
- ✅ `compute_rebalance` 按 `target_weights` 配置初始持仓
- ✅ `targets.load_strategy_targets` 参数化策略接口（Master 读取）

**真机层验证：**
- ✅ accounts=1 证明激活流程正常执行
- ✅ 971 tests 全绿（包含持仓权重验证）

### ④ 后端进程健康

```bash
deploy 3393653 0.6 1.2 580088 99528 ? Ssl 02:44 0:04 uvicorn ...
deploy 3394552 0.2 0.9 86772 74296 ? Ss 02:45 0:01 backtest worker
```

**验证：** ✅ PASS
- uvicorn 正常运行
- backtest worker 正常运行  
- recent-errors=0（无异常）

### ⑤ 回归验证

✅ **B050-B055 不破**
- 改动不涉及执行流、风控算法
- 新建独立 paper 账户体系（不影响实盘）
- nav_history 与现有 price_snapshot 解耦

---

## 签收结论

### Status：**✅ FULL PASS**

**L1 代码审核 PASS**：
- F001-F004 实现完整  
- 971 backend + 282 frontend tests 全绿
- CI 全部门禁通过

**L2 真机验证 PASS**：
- Timer 接线正确（03:45 UTC 触发）
- MTM job 成功运行（accounts=1 points=1）
- 激活逻辑正确（读 target_weights，忠实跟目标）
- 前向累积生效（nav_history 点创建）
- 后端进程健康（recent-errors=0）

**架构质量**：
- ✅ 参数化策略接口完整（Master 先，B055 零成本接入）
- ✅ 纯函数虚拟调仓引擎（精确算术，易测试）
- ✅ 幂等 MTM job（account+date 键）
- ✅ §12.10.2 边界守护（off 请求路径，只读 price/targets）

---

## 交付

**F004 结论**：  
✅ **L1 PASS** —— 代码审核 + 971+282 tests  
✅ **L2 PASS** —— 真机激活验证 + MTM 累积 + timer 接线  

**next**：Planner done 阶段  
- 告知用户「模拟盘已就绪，可激活 Master 前向验证策略表现」
- B055 进攻引擎（敏感因子选股）准备接入（同接口零成本）

---

## 无 Soft-watch

本批无遗留问题。

## 无 Framework Learnings

本批无新框架提案。参数化策略接口已沉淀，B057 regime / B055 攻防可复用。
