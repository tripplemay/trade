# B027 Real Data Snapshot Foundation Blocker 2026-05-26

> 状态：**L1 PASS / L2 FAIL**
> 触发：F003 首轮验收

## 结论

`B027 F003` 当前不能签收，已退回 `fixing`。

本地 L1 门禁通过，但生产 L2 在 Tiingo smoke API test 处失败。根因是 production runtime 缺少 `httpx`，导致 `TiingoSnapshotLoader` 在 VM 上连 import 都失败，因此无法满足 spec/F003 的硬性验收项：

- `production backend 触发一次 TiingoSnapshotLoader.health_check() → Tiingo 返回 200 / budget_log 增 1 行`

## 已通过项

### L1

- backend `pytest`: `273 passed, 2 skipped`
- backend `ruff check .`: pass
- backend `mypy workbench_api tests`: pass
- alembic round-trip: `upgrade head -> downgrade 0002 -> upgrade head` pass
- frontend `vitest`: `166 passed`
- frontend `build`: pass
- Playwright: `38 passed`
- `.next/static` / build artifact grep：未命中 `TIINGO_API_KEY` / `api.tiingo.com` / 本地 backend host 泄漏

### L2 已确认通过的子项

- `https://trade.guangai.ai/api/health` 返回 `200`
- production `version` 与本地 `git rev-parse HEAD` 一致：
  - production: `c46bda37cd165ed5a81153b9b876eee56ae2e5c7`
  - main HEAD: `c46bda37cd165ed5a81153b9b876eee56ae2e5c7`
- VM `/etc/workbench/workbench.env` 已存在 `TIINGO_API_KEY`（已脱敏确认）
- VM SQLite 存在 `tiingo_budget_log` 表
- systemd unit 确认 backend 以 `WorkingDirectory=/srv/workbench/current/backend` 启动

## Blocker

### 1. production runtime 缺少 `httpx`

在 VM 上按服务同样的工作目录执行 smoke：

```bash
cd /srv/workbench/current/backend
set -a
. /etc/workbench/workbench.env
set +a
/opt/workbench/.venv/bin/python - <<'PY'
from workbench_api.data.tiingo_loader import TiingoSnapshotLoader
print('IMPORT_OK')
print('HEALTH_RESULT', TiingoSnapshotLoader().health_check())
PY
```

实际结果：

```text
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/srv/workbench/releases/c46bda37cd165ed5a81153b9b876eee56ae2e5c7/backend/workbench_api/data/tiingo_loader.py", line 44, in <module>
    import httpx
ModuleNotFoundError: No module named 'httpx'
```

这说明：

- `TIINGO_API_KEY` 注入本身不是 blocker
- schema / deploy SHA 也不是 blocker
- 真正问题是 production venv 缺运行时依赖 `httpx`

### 2. 为什么本地没暴露、生产暴露

本地测试环境使用的是带 dev 依赖的 `.venv`，其中已有 `httpx`，所以 unit/integration tests 都通过。

但 backend `pyproject.toml` 当前把 `httpx` 放在 `[project.optional-dependencies].dev`，没有放进 runtime `dependencies`。因此 production venv 不会安装它，导致 live Tiingo 路径在 VM 上直接失败。

## 非阻塞观察

- `/opt/workbench/.venv/lib/python3.11/site-packages/workbench_api` 只包含顶层包和少量子目录，不含 `data/`、`routes/`、`services/` 等完整源码树；不过 systemd 当前通过 `WorkingDirectory=/srv/workbench/current/backend` 从 release 源码目录启动，所以这不是本轮 blocker 的直接原因。
- spec 文案写的是 `/etc/workbench/.env.production`，而实际生产环境文件是 `/etc/workbench/workbench.env`。这是 checklist 文本漂移，不单独计失败。

## Generator 下一步

至少需要修复：

1. 让 production runtime 安装 `httpx`（例如把它提升到 backend runtime dependency，而不是仅 dev extra）。
2. 修复后重新 deploy，并让 production VM 上的 `TiingoSnapshotLoader().health_check()` 真正返回 `True`。
3. 复验时需要补齐：
   - `budget_log` 调用计数 `+1`
   - `/api/debug/recent-errors`
   - B026 banner 不受影响

## 产物

- 本报告：`docs/test-reports/B027-real-data-snapshot-foundation-blocker-2026-05-26.md`
