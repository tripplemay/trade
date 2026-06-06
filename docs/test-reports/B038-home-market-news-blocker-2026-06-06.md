# B038 Home Market News Blocker 2026-06-06

> 状态：**FAIL**
> 触发：B038 F003 production L2 验收

---

## Scope

- L1：B038 直接相关 backend/frontend 守门与单测
- L2：production `/api/news/latest`、`/api/debug/recent-errors`、`workbench-news.timer` 自动接线、`workbench-news.service` 手动触发验真、deploy log wiring 证据

---

## Result

L1 全 PASS，但 L2 存在 **1 个 blocker**，本轮 **不得签收**。

通过项：
- backend targeted pytest：`43 passed`
- frontend targeted vitest：`28 passed`
- production `/api/news/latest` authenticated `200 {"items":[]}`；anonymous `401`
- production `/api/debug/recent-errors` authenticated `{"count":0,"records":[]}`
- `workbench-news.timer` 已通过 B037-OPS1 durable 路径自动 install + enable，无需手装
- deploy run `27052426615` 明示 `workbench-news.timer` `✓ enabled`，且没有 timer wiring warning

阻塞项：
- `workbench-news.service` 在 production 手动触发时直接失败，无法完成新闻抓取真机验收

---

## Evidence

### L1

- backend targeted:
  - `.venv/bin/python -m pytest workbench/backend/tests/unit/test_news_latest_feed.py workbench/backend/tests/safety/test_market_scheduler_scope.py workbench/backend/tests/safety/test_b034_no_generative_ai.py workbench/backend/tests/safety/test_news_no_scheduler.py`
  - 结果：`43 passed`
- frontend targeted:
  - `cd workbench/frontend && npx vitest run tests/unit/home/HomeNewsPanel.spec.tsx tests/safety/no-execution-buttons.spec.ts`
  - 结果：`28 passed`

### L2 PASS evidence

- `curl https://trade.guangai.ai/api/health`
  - `{"status":"ok","version":"f031c1e3ab3dbdf88bfce1f8c1cacf7cd16be0a3","db_connectivity":"ok",...}`
- authenticated `GET /api/news/latest`
  - `{"items":[]}`
  - 说明：当前 production 新闻表仍为空，空列表本身符合 spec 的允许路径，不构成 blocker
- anonymous `GET /api/news/latest`
  - `401`
- authenticated `GET /api/debug/recent-errors`
  - `{"count":0,"records":[]}`
- `systemctl is-enabled workbench-news.timer`
  - `enabled`
- `systemctl status workbench-news.timer --no-pager`
  - `Loaded: ... enabled`
  - `Active: active (waiting)`
  - `Trigger: Sun 2026-06-07 02:00:00 UTC`
- deploy log（`gh run view 27052426615 --log | rg ...`）：
  - `→ install + enable workbench-news.timer`
  - `✓ workbench-news.timer enabled`
  - 未出现 `Could not install/enable workbench-news.timer`

### Blocker evidence

- 手动触发：
  - `ssh tripplezhou@34.180.93.185 "sudo systemctl start workbench-news.service"`
  - 返回：`Job for workbench-news.service failed because the control process exited with error code.`
- `systemctl status workbench-news.service --no-pager` + `journalctl -u workbench-news.service -n 80 --no-pager`
  - `Active: failed (Result: exit-code)`
  - `ExecStart=/opt/workbench/.venv/bin/python -m workbench_api.news.cli fetch --source=all`
  - traceback 核心：
    - `ModuleNotFoundError: No module named 'scripts.universe_us_quality'`
    - 路径：
      - `workbench_api/news/cli.py`, line 65
      - `from scripts.universe_us_quality import US_QUALITY_REAL_TICKERS`

### Root-cause location

- [workbench/backend/workbench_api/news/cli.py](/Users/yixingzhou/project/trade/workbench/backend/workbench_api/news/cli.py:60)
  - `_default_universe()` 直接 import repo-root `scripts.universe_us_quality`
- 这与已沉淀的 v0.9.32 §12.10 同类：
  - deploy artifact 只带 `workbench_api/` 包；请求/CLI 运行路径不能依赖 repo-root `scripts/`

---

## Required Action

Generator 需要修复 `workbench_api.news.cli` 的默认 universe 解析，使 production deploy artifact 自包含：

1. 移除 `workbench_api/news/cli.py` 对 repo-root `scripts.universe_us_quality` 的运行时依赖。
2. 改为复用已在包内 materialize 的 ticker 常量来源，或把所需 universe 常量显式搬入 `workbench_api/` 包内。
3. 补守门，覆盖：
   - news CLI default universe 在 deploy-artifact/self-contained 约束下可运行
   - production timer oneshot 不再触发 `ModuleNotFoundError`
4. 修复后重新 deploy，再由 Codex 复验：
   - `workbench-news.service` 手动触发成功
   - `/api/news/latest` 返回有数据或合规空窗，并记录实际结果
   - Home 新闻段 production 浏览器手验

---

## Conclusion

本轮 **Do not sign off**。B038 当前不是 timer wiring 问题，而是 `workbench-news.service` 的运行时自包含缺陷；状态应回到 `fixing`。
