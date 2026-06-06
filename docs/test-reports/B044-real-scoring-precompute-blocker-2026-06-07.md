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

---

## Resolution (Generator — 2026-06-07)

**根因（环境，非代码）**：生产 VM 主机级挂死。网络层 SYN 仍被应答，但 nginx(443) 与 sshd(22) 应用握手都不响应（curl `connect=0` 60s 超时；ssh banner exchange 超时）——典型 host-level 资源耗尽/hung。本机网络正常（github 200）、DNS 正确解析、本批 L1 全绿（backend 61 / ruff 0 / mypy 0），确认非代码问题、非 DNS。SSH 进不去 → Generator 无法远程修复；需 out-of-band GCP 恢复。

**恢复动作（用户授权下）**：用户在 GCP 控制台 reset 实例；Generator 轮询命中即恢复（SSH_OK + health 200）。

**关键发现 — F003 部署在停机窗口失败**：失败的 deploy run `27067303783`（16:12）在 SCP 步报 `kex_exchange_identification: read: Connection reset by peer` / `scp: Connection closed`——纯因 VM 挂死，非代码。导致 prod 停在 **F002 版本 `1626ea2`**（缺 F003 读路径），但 F002 deploy 已落 `alembic=0010` + trade wheel + reco timer。

**Generator 重新部署（用户授权 re-deploy）**：`gh workflow run "Workbench Deploy" --ref main` → run `27075389529` **success** → prod 版本推进到 **`8b39d68`（main HEAD）**，F003 读路径上线。deploy.sh 各步幂等（alembic 已 0010、trade 已装、reco timer 已 enabled）。

**Production L2 真机验证（version 8b39d68）**：
- `GET /api/health` → 200，`version=8b39d68`，`db_connectivity=ok`；**Production HEAD ≡ main HEAD**。
- VM `import trade.backtest.master_portfolio` → OK（trade wheel 在 venv）。
- `alembic_version` → `0010_b044_recommendation_snapshot`。
- `workbench-recommendations.timer` → **enabled + active**（B037-OPS1 自动接线，无手装）。
- 手动 `systemctl start workbench-recommendations.service` → **`Result=success ExecMainStatus=0`**；journal：`saved=3 as_of_date=2024-12-31 data_source=fixture error=None`（2 条 `sleeve_unavailable` WARNING = risk_parity/us_quality 在 VM 因数据不可用 stub）。
- `recommendation_snapshot` 3 行真实评分：**SGOV 0.6 (risk_parity) / EEM 0.2 (momentum) / SPY 0.2 (momentum)** —— **momentum 真实评分（top-2 ETF），非 equal-weight**；`master_meta.data_source=fixture`（诚实标记，真实市场数据留 B045）。
- anon `GET /api/recommendations/current` → **401**。
- VM 健康：up 后 load 正常、mem 5.4G free、无 OOM/failed units；**disk 82%（40G/49G，watch-item，非满）**——挂死前易失证据被 reboot 清除，未能定位确切根因，但磁盘偏高建议监控/清理。

**状态**：`fixing → reverifying`（fix_rounds 1，环境恢复 + re-deploy + precompute 验真，无代码改动）。

**Codex 复验剩余**（需 cookie，归 evaluator）：authenticated `GET /api/recommendations/current` 200 返回上面的真实权重（非 equal-weight）；authenticated `/api/debug/recent-errors={count:0}`；据此完成 F004 signoff（含 §Framework Learnings：trade 入 artifact 改 §12.10 enforcement 物理缺席→AST 守门）。
