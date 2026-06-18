---
name: environment
description: 生产/Staging 环境地址、服务器配置、测试账号（很少变）
type: reference
---

## 生产环境

- 控制台：`[https://example.com]`
- API：`[https://example.com/api]`
- [其他端点，如 MCP / SDK / Admin]

## 生产服务器（2026-06-18 — B067 done 实测填实，治本占位符）

| 项目 | 值 |
|---|---|
| 云 | GCP（hostname `instance-20260403-154049`）|
| **外网 IP** | **`34.180.93.185`**（2026-06-18 SSH 实测可达）|
| **SSH** | **`ssh tripplezhou@34.180.93.185`** |
| 部署路径 | `/srv/workbench/current/backend`（symlink → `/srv/workbench/releases/<sha>/backend`；历史 release GC 见 commit e49e217）|
| 启动 | systemd（`workbench-*.service` + `*.timer`）|
| 数据根 | `WORKBENCH_DATA_ROOT=/var/lib/workbench/data` |
| 部署后台 venv | `/opt/workbench/.venv`（含 akshare/baostock）|
| CI/CD | GitHub Actions（绿 CI 自动链式部署）|

### ★连接失败先核对 IP，勿误判 fail2ban/封锁（2026-06-18 — B065+B067 两次误判教训；evaluator §25 实例）

- **真 VM IP = `34.180.93.185`**。曾出现 agent 用**旧/猜的 IP**（如 `162.14.96.221`）连不上 → **误判为「SSH fail2ban 封锁」并把核心验收降级为 soft-watch**（B067 F004 evaluator + B065 各一次）。
- **规约（evaluator §25 实例）：SSH/连接失败 → 先核对用的是不是上表 `34.180.93.185`**，再判封锁/超时；勿在用错 IP 时归因 fail2ban。
- **timer/precompute job 运行机制**：`*.service` 设 `WorkingDirectory=/srv/workbench/current/backend` + `ExecStart=/opt/workbench/.venv/bin/python -m workbench_api.<module>`。`workbench_api` 从 **WorkingDirectory 源树** import（`/opt/workbench/.venv` 的 site-packages 里 workbench_api 是 stale，缺 strategy_modes 等子包）→ **本地 import-check 必须先 `cd /srv/workbench/current/backend`**，否则误报 ModuleNotFoundError（B067 planner 自己也差点踩此 false alarm）。

## 测试账号（如有）

- **Admin:** `[email]` / `[password]` / API Key: `[redacted]`
- **Developer:** `[email]` / `[password]` / API Key: `[redacted]`

## 本机 Python 解释器

- 仓库要求 Python `>=3.11`（pyproject.toml）。
- 本机系统 `python3` 为 3.9.6，不满足要求。
- **所有 pytest / ruff / mypy / compileall 命令必须显式使用 `.venv/bin/python`**（或激活 venv 后调用）。
- 来源：B012 signoff soft-watch S1（2026-05-14，Codex L1 验收）。

## CI 分层：改 `trade/` 须本地 `mypy trade` 自检（v0.9.41 — B050 沉淀）

- 有**两条独立 CI**：Workbench Backend CI 只查 `workbench_api`；独立「Python CI」对仓库根跑 `mypy trade` + `ruff check .` + 全 root pytest，**比 backend CI 严**。
- **改了 `trade/` 包的代码，本地门禁必须额外跑 `.venv/bin/mypy trade`**（不止 workbench 那套），否则 backend CI 绿但 Python CI 红。
- 来源：B050 F002/F003 触红（hotfix `8728621`：us_quality `_iso_date` 用 `Any`+`str()`、hk_china `_execute_period` 复用加 `arg-type` ignore）。
- **ruff 本地必须目录上下文 `python -m ruff check .`，勿对单文件/子集跑 `check`/`--fix`**（v0.9.47 — B065 F001）：单文件模式缺 project 根 → 不识别 `workbench_api` 为 first-party → 漏 isort 组间空行（`I001`）→ 本地绿 CI 红。详见 generator.md §19.1。

<!-- 写入规则：由 Planner 统一维护，环境变更后及时更新。账号密码避免明文，必要时引用 secret manager。 -->
