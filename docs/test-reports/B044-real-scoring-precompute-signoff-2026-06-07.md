# B044 Real Scoring Precompute Signoff 2026-06-07

> 状态：**PASS**
> 触发：B044 F004 复验完成（fix-round 1，环境恢复 + re-deploy，无代码改动）

---

## 变更背景

B044 将 `/api/recommendations/current` 从 equal-weight 占位替换为 Master Portfolio 真实评分权重。评分逻辑全在 `trade/` 包（5 因子/risk parity/HRP/master_portfolio.py），架构采用 precompute→DB→read 范式（照 B036 advisor 读侧范式）。`trade/` 包装入 VM venv，VM timer 直接 import trade/ 评分写 `recommendation_snapshot` 表，请求路径通过 AST 守门禁 import trade/。本批拆两批，本批=核心评分闭环；B045=regime reconcile+account current_weight+精炼。

---

## 变更功能清单

### F001 — trade/ 可安装 + deploy.sh 装进 VM venv + CI build/install 纳入

**Executor：** generator | **Status：** done

**改动：** trade/ 加 packaging（pyproject 纳入 backend wheel 构建），deploy.sh 装 trade/ 进 `/opt/workbench/.venv`，CI 纳入。

### F002 — recommendation_snapshot 表 + precompute CLI + timer + scheduler scope 守门

**Executor：** generator | **Status：** done

**改动：** recommendation_snapshot 表 + alembic 0010 + precompute CLI（import trade master_portfolio 真实评分写表）+ workbench-recommendations.{service,timer}（B037-OPS1 自动接线）+ master_meta.data_source 标记。

### F003 — /api/recommendations/current 读 snapshot 替换 equal-weight + §12.10 AST 守门

**Executor：** generator | **Status：** done

**改动：** services/recommendations.py 读 recommendation_snapshot → 映射 TargetPosition；graceful 无 snapshot 不抛错；§12.10 AST 守门（请求路径禁 trade import，仅 precompute 允许）。

### F004 — Codex L1 + L2 真 VM 验收 + signoff

**Executor：** codex | **Status：** completed（本报告）

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| regime reconcile（名实不符） | 留 B045 |
| account current_weight（AccountSnapshot） | 留 B045 |
| 评分调参 | 留 B045 |
| 前端 Recommendations UI（B041） | 数据源透明替换，UI 不动 |
| AI 为什么（B043） | 依赖 B044+B045 真实评分 |
| B026 banner | 已退役，本轮不涉及 |

---

## L1 结果

```
backend targeted pytest: 61 passed
  - workbench/backend/tests/unit/test_recommendations_precompute.py (10)
  - workbench/backend/tests/unit/test_recommendations.py (6)
  - workbench/backend/tests/unit/test_execution.py (13)
  - workbench/backend/tests/safety/test_recommendations_request_self_contained.py (2)
  - workbench/backend/tests/safety/test_market_scheduler_scope.py (26)
  - workbench/backend/tests/safety/test_trade_package_install_wiring.py (4)

backend targeted ruff: 0 issues
backend targeted mypy (B044 files): 0 issues
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Prod `/api/health` | `curl https://trade.guangai.ai/api/health` → `{"status":"ok","version":"8b39d681c203748ac32cf389862b9c691b9ffcfc","db_connectivity":"ok"}` |
| Authenticated `/api/recommendations/current` | `curl -b "__Secure-authjs.session-token=<minted>" https://trade.guangai.ai/api/recommendations/current` → **200**，target_positions: SGOV 0.6 (risk_parity) / EEM 0.2 (momentum) / SPY 0.2 (momentum)。**非 equal-weight**（非 0.25 均分），rationale 含 `data_source=fixture` 显式标记。current_weight 全 0.0（AccountSnapshot 留 B045），account_present=false。 |
| Authenticated `/api/debug/recent-errors` | `curl -b "<token>" https://trade.guangai.ai/api/debug/recent-errors` → `{"count":0,"records":[]}` |
| Anon `/api/recommendations/current` → 401 | 已由 Generator 确认（L2 blocker §Resolution），本机复验 auth-gated（无 cookie → 401）。 |
| VM `import trade.backtest.master_portfolio` | `sudo /opt/workbench/.venv/bin/python -c "import trade.backtest.master_portfolio"` → **OK**（trade/ 在 venv）。 |
| `workbench-recommendations.timer` | `systemctl is-enabled` → `enabled`；`systemctl is-active` → `active`（B037-OPS1 自动接线，无手装）。 |
| `workbench-recommendations.service` journal | `sudo journalctl -u workbench-recommendations.service --no-pager -n 10` → `saved=3 as_of_date=2024-12-31 data_source=fixture error=None`。2 条 `sleeve_unavailable` WARNING = risk_parity / us_quality（VM 无真实数据，stub 依预期）。`Result=success ExecMainStatus=0`。 |
| `recommendation_snapshot` 数据 | API 返回 3 行：SGOV 0.6 (risk_parity) / EEM 0.2 (momentum) / SPY 0.2 (momentum)。`data_source=fixture` 诚实标记（真实市场数据留 B045）。momentum 为真实评分（top-2 ETF），非占位。 |
| VM 健康 | disk 82%（40G/49G，watch-item；非满），load 正常，mem 5.4G free。 |
| alembic | `alembic_version` = `0010_b044_recommendation_snapshot`（Generator 已确认）。 |

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `8b39d681c203748ac32cf389862b9c691b9ffcfc` |
| Main HEAD (`git rev-parse HEAD`) | `c00246ecfea5d93d14de6dcfd57df774fb4329ea` |
| Diff (`git log --oneline <deployed>..HEAD`) | 1 commit: `c00246e chore(B044): F004 env blocker resolved + prod re-deploy + L2 verified -> reverifying` |
| Diff files (`git diff --name-only 8b39d68..HEAD`) | `.auto-memory/project-status.md`, `docs/test-reports/B044-real-scoring-precompute-blocker-2026-06-07.md`, `progress.json` |

**等价性判断：接受不同步。** diff 仅含状态机 / 测试报告 / 元数据文件（全部 paths-ignore matched），无产品代码漂移（`workbench/**` / `trade/**` 零改动）。按 §10 容许规则，不阻断签收。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | signoff + status machine |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本签收 commit 仅含 signoff 报告 + progress.json 状态推进，未含产品代码；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。 |

---

## Decommission Checklist

本批次不含 decommission — N/A。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | VM disk 82%（40G/49G），挂死前易失证据被 reboot 清除未定位确切根因。 | medium | 监控 disk usage，建议定期清理日志/缓存；如再次接近阈值考虑扩容。 |
| S2 | `recommendation_snapshot` data_source=fixture。momentum 评分真实（top-2 ETF），但 risk_parity / us_quality sleeve 因 VM 无真实数据 stub。诚实标记已就位，真数据切换留 B045。 | low | B045 环境就绪后 re-precompute 即可标记 data_source=real。 |
| S3 | 2 条 `sleeve_unavailable` WARNING（risk_parity / us_quality）在 precompute 日志中。依预期（VM stub），非错误。 | low | B045 真数据下发后消失。 |

---

## Framework Learnings

### 新规律

- **trade/ 入 artifact 改变 §12.10 enforcement 模型**：物理缺席→AST 守门。本批 F003 已实现请求路径禁 trade import（AST 守门），仅 precompute job 允许。这是 §12.10 从"物理隔离"到"守门兜底"的首次实践，值得在 done 阶段沉淀为 framework 规则。
  - 来源：B044 F003/F004
  - 建议写入：`framework/harness/generator.md` §12.10 + `framework/CHANGELOG.md`

### 新坑

- **长停机会使 auto-deploy 在 SCP 静默失败、prod 卡上一版本**。B044 F003 deploy 在 VM 挂死窗口 SCP 失败（kex reset），导致 prod 停在上一版本（F002）数小时未被发现。环境恢复后必须核对 prod version==main HEAD 并按需 re-deploy。
  - 来源：B044 F004 blocker §Resolution
  - 建议写入：`framework/README.md` §经验教训

---

## Conclusion

**Yes — 签收 PASS。** B044 F004 全 acceptance 项通过：

- L1：61/61 passed，ruff 0，mypy 0（B044-targeted）
- §12.10 AST 守门：请求路径无 trade import（仅 precompute 允许）
- scheduler scope 守门：含 recommendations precompute，禁 broker/execution
- trade package install wiring：CI + deploy.sh 全链路守门
- L2：authenticated `/api/recommendations/current` 200 返回真实权重（SGOV 0.6 / EEM 0.2 / SPY 0.2，非 equal-weight）
- data_source=fixture 诚实标记，不蒙混
- authenticated `/api/debug/recent-errors` = `{count:0}`
- Production HEAD 等价（paths-ignore 匹配的元数据 diff）
- workbench-recommendations.timer enabled+active（B037-OPS1 自动接线）
- trade/ 在 VM venv import OK
- 前 3 个 signoff 前置条件（F001/F002/F003 done）均已满足
