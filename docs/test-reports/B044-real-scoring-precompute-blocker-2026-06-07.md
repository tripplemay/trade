# B044 Real Scoring Precompute Blocker 2026-06-07

> 状态：**BLOCKED**
> 触发：B044 F004 首轮验收未完成

---

## 结论

本轮 **不能签收**。L1 全 PASS，但 B044 是后端 / 运维 / precompute 批次，F004 的关键验收项都依赖 production L2：

- VM `trade` wheel 已安装可 import
- `workbench-recommendations.service` 可手动触发
- `workbench-recommendations.timer` 已自动 `enabled + active`
- `recommendation_snapshot` 已产生真实评分行
- `/api/recommendations/current` 已读到非占位的真实 target weights

当前 production API 与 VM SSH 均超时，导致上述证据无法取得，因此必须切回 `fixing`，等待环境恢复后复验。

---

## L1 结果

```text
backend targeted pytest: 61 passed
  - workbench/backend/tests/unit/test_recommendations_precompute.py
  - workbench/backend/tests/unit/test_recommendations.py
  - workbench/backend/tests/unit/test_execution.py
  - workbench/backend/tests/safety/test_recommendations_request_self_contained.py
  - workbench/backend/tests/safety/test_market_scheduler_scope.py
  - workbench/backend/tests/safety/test_trade_package_install_wiring.py

backend targeted ruff: 0 issues
backend targeted mypy: 0 issues
```

L1 说明：

- `§12.10` AST 守门通过：请求路径 `routes/services/recommendations` 无 `trade` import，仅 precompute job 允许。
- scheduler scope 守门通过。
- trade packaging / deploy wiring 守门通过。

---

## L2 阻塞证据

### 1. production API 超时

以下命令均未在 15 秒内完成：

```bash
curl --max-time 15 -sS https://trade.guangai.ai/api/health
curl --max-time 15 -sS -H "Cookie: __Secure-authjs.session-token=..." \
  https://trade.guangai.ai/api/recommendations/current
```

结果：

```text
curl: (28) Connection timed out after 15006 milliseconds
```

### 2. VM SSH 超时

```bash
ssh -o ConnectTimeout=15 tripplezhou@34.180.93.185 'echo connected'
```

结果：

```text
Connection timed out during banner exchange
Connection to 34.180.93.185 port 22 timed out
```

### 3. 直接影响的未验收项

由于 production/VM 不可达，以下 F004 必做项全部无法完成：

- `python -c "import trade.backtest.master_portfolio"` 真机 import
- `systemctl status/is-enabled workbench-recommendations.{timer,service}`
- `systemctl start workbench-recommendations.service`
- DB `recommendation_snapshot` 行与 `master_meta.data_source`
- authenticated `GET /api/recommendations/current` 真权重（非 equal-weight / 非空占位）
- `alembic_version=0010`

---

## 需要 Generator / 运维侧处理

先恢复 production / VM 的基本连通性，再让我复验。最低恢复标准：

1. `https://trade.guangai.ai/api/health` 在 15 秒内返回 `200`
2. `ssh tripplezhou@34.180.93.185` 可连通
3. VM 上 `workbench-recommendations` unit 可检查 / 可手动触发

环境恢复后，我将复验：

- trade import
- timer 自动接线
- oneshot precompute
- snapshot 写表
- `/api/recommendations/current` 真权重
- `data_source=fixture|real` 显式声明

---

## Conclusion

当前 blocker 不是代码级失败，而是 **production/VM 连通性失败**。在拿不到 B044 必需的 L2 真机证据前，不能签收。
