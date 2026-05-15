# Proposed Learnings Archive — v0.9.23

> 归档日期：2026-05-15
> 来源批次：B020-dev-infrastructure F001 / F002 / F003
> 闭环情况：3 条 learnings 全部 Accept（用户 5/15 done wrap-up 决议）+ 落 framework/harness/generator.md + 立即应用到 workbench-* workflows + CHANGELOG v0.9.23 已记录。

---

## [2026-05-15] Claude CLI — 来源：B020-F001 Playwright 本机 boot（v0.9.23 #1）

**类型：** 新坑（dev environment prerequisites）

**内容：** WSL/Ubuntu 22.04+ 上跑 Playwright Chromium 必须先装 `libnss3 libnspr4 libasound2t64`（24.04+ 是 libasound2t64，22.04 仍是 libasound2）。但常见用户配置 `http_proxy=127.0.0.1:10808`（Clash / v2rayN / mihomo 类工具）会因 sudo 默认 `env_reset` 行为 sanitize 掉代理变量 → `sudo apt-get install` 直连 ports.ubuntu.com 卡死超时。本机 dev environment 模板若引入 Playwright，需在 README prerequisites 显式标注此点，否则首次安装卡死会被误判为环境损坏。

**沉淀位置（已写入）：**
- `framework/harness/generator.md` §9 "Dev environment prerequisites — Playwright / Chromium 类前端项目"，含：
  - WSL/Ubuntu 系统库清单（按 distro 区分）
  - `sudo -E` 透传当前 env 的修法
  - `/etc/apt/apt.conf.d/95proxies` 持久化方案
  - Spec/README 起草 checklist（系统库 + sudo 代理 + `npx playwright install` 配置）

**实物时间线：** B020-F001 commit `dc0c4c6` 期间，本机首次 boot 卡 ~90 分钟才发现根因（apt-get 卡在 timeout）。后续 frontend 类批次若不沉淀这条会重复踩。

---

## [2026-05-15] Claude CLI — 来源：B020-F002 CI workflow（v0.9.23 #2）

**类型：** 新坑（CI forward-compat — 时间敏感）

**内容：** GitHub Actions 2026-06-02 changelog 宣布 `actions/checkout@v4` / `actions/setup-node@v4` / `actions/setup-python@v5` / `actions/cache@v4` 等 JS-based actions 默认 Node 20 runtime 即将切到 Node 24：

- 2026-06-02 起：可通过 env var `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` 强制 Node 24（手动 opt-in 测兼容）
- 2026-09-16 起：完全移除 Node 20 runtime；不显式 opt-in 但仍依赖 Node 20 的 action 红屏

**沉淀位置（已写入）：**
- `framework/harness/generator.md` §10 "GitHub Actions Node runtime forward-compat（2026-09-16 deadline）"，强制规则：任何新增 `.github/workflows/*.yml` 必须在顶层 `env:` 块加 `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"`。
- 立即应用到 `.github/workflows/workbench-backend.yml` + `workbench-frontend.yml`（不等 6 月被动切）。

**为什么立即动而不是等 6 月：** 改什么都是 3 个 workflow 改 1 行，加起来 5 分钟。"立即动"防止后人忘 / 切换日突变。

---

## [2026-05-15] Claude CLI — 来源：B020-F003 ruff SIM300 trap（v0.9.23 #3）

**类型：** 新坑（Python 编码约定）

**内容：** Ruff 规则 `SIM300`（Yoda condition detection）会把 `UPPERCASE_CONSTANT == frozenset()` 视为 Yoda（uppercase + 构造函数 → ruff 推断"常量在左，违反 Yoda"，suggest 反着写）。对 `frozenset()` / `set()` / `dict()` 这种构造函数右值场景，改用 `len(...) == 0` 或 `not ...` 更稳健，符合常用阅读习惯（"check X equals empty"）。Generator 在 strict ruff (SIM 选中) 项目里写 assertion 时应该默认避开 `const == Constructor()` 形式。

**沉淀位置（已写入）：**
- `framework/harness/generator.md` §11 "Python 编码约定 — ruff strict mode 常见陷阱"，含 反例 + 推荐写法。

**实物时间线：** B020-F003 commit `6184a1b` `tests/safety/test_settings_env_allowlist.py` 写 `assert ALLOWED_ENV_VARS == frozenset()` 触发 SIM300 → 改 `assert len(ALLOWED_ENV_VARS) == 0` 通过。
