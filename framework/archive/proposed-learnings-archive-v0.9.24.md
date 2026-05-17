# Proposed Learnings Archive — v0.9.24

> 归档日期：2026-05-17
> 来源批次：B021-cloud-deploy-auth F003-F006 fix-round 1-7 + Planner first-time VM bootstrap
> 闭环情况：8 candidates 归并为 3 groups + 1 sub-pattern，全部 Accept（用户 5/17 done wrap-up 决议）+ 落 framework/harness/{planner.md, generator.md}，CHANGELOG v0.9.24 已记录。

---

## Group A — Cloud-deploy spec planning gap (v0.9.24 #1)

**类型：** 新规律（spec-writing checklist 缺项）

**内容：** B021 spec 起草时只覆盖 incremental redeploy 流（CI push → SCP → systemctl restart），假设 VM 已经处于"基础设施就位"态。但实际上从未有人在这台 VM 上安装过 workbench，导致 Codex L2 reverify 时所有 systemd unit / nginx vhost / cert / venv 全空白。Planner 用 5 个 commit 7 轮 retry 才把 bootstrap 跑通。这 ~2-3h"踩坑"完全可由 spec 时多写 1 个 feature 预防。

**配套：** B021 prep 列了 5 个 user 手动 prereq，但 GitHub Secrets prep 只列 7 个（DEPLOY_HOST/USER/SSH_PRIVATE_KEY/OAuth client_id/secret/NextAuth secret/email），**漏了 DEPLOY_SSH_KNOWN_HOSTS** —— deploy workflow 用 SSH 必须有 known_hosts 否则 `Host key verification failed`。这也是 spec-writing checklist 缺项。

**沉淀位置（已写入）：** `framework/harness/planner.md` §"Cloud-deploy spec checklist" 含：
- 必含 first-time bootstrap feature 的 7 必做项表格（apt 系统依赖 / 目录权限 / systemd install + enable / nginx + cert / env 文件初始化 / 第一次 deploy / 手动 prereq 验证）
- workflow_run deploy 工作流配套 8 GitHub Secrets 清单（含 DEPLOY_SSH_KNOWN_HOSTS）
- B021 F006 fix-round 1-7 反面时间线作为案例

---

## Group B — systemd + Linux infra 部署 gotchas (v0.9.24 #2)

**类型：** 新坑（systemd + 单元 / 用户 / 沙箱 / snap 交互）

**4 子条：**

1. **`/etc/<app>/` 目录 traversal 权限**：非 root 应用用户读 /etc/<app>/config.json 类配置需要目录有 `x` bit；`chmod 750 root:root` 阻断 app user `open()`，即使文件本身 644。B021 fix-round 5 卡 1 小时找到这个。
2. **systemctl restart 多 service 一行 ≠ sudoers per-service whitelist**：sudoers `NOPASSWD: /bin/systemctl restart workbench-backend.service` 不匹配 `sudo systemctl restart workbench-backend.service workbench-frontend.service`（两个 service 名一行）。必须拆开。
3. **PrivateTmp=true + snap-confined binaries 不兼容**：systemd 私有 /tmp namespace 与 snap mount namespace 冲突 → snap-confined binary 看不到 systemd service 写在 /tmp 的文件。symptom：脚本前半 log 有，后半哑火，exit 1。
4. **snap-confine + systemd non-root 服务 cap_dac_override 缺失**：systemd `NoNewPrivileges=true` 剥 capability，snap-confine 引导需 cap_dac_override 报 "required permitted capability cap_dac_override not found"。**修法**：cloud CLI 工具走 apt 装而非 snap（B021 改 `apt-get install google-cloud-cli` 后立解决）。

**沉淀位置（已写入）：** `framework/harness/generator.md` §12 "systemd + Linux infra 部署 gotchas" 四子节，含具体修法代码示例 + 来源 commit。

---

## Group C — Frontend SSR vs Browser context (v0.9.24 #3)

**类型：** 新坑（同构 SSR 框架配置 URL 上下文歧义）

**内容：** Next.js / Nuxt / Remix 等同构框架的组件代码在 SSR (Node)和 Client (浏览器)两个上下文都跑。"localhost" 在 SSR = 跑 build 的机器；在 Client = 用户的笔记本。B021 frontend page 默认 `HEALTH_URL = http://127.0.0.1:8723/api/health`，build 时 inline 进 client bundle，浏览器在用户机器上 fetch 127.0.0.1 必失败。Codex L2 reverify fix-round 5 阻塞就是这个。

**规约：**
- 配置 URL 一律走 same-origin 相对路径（`/api/...`）
- 必须跨 origin 时用 `NEXT_PUBLIC_*` env + build-time 注入（runtime 注入对 client bundle 无效）
- 加 regression test grep build artifact 不含 `127.0.0.1` / `localhost:` 字面串
- dev mode 用 `next.config.mjs` rewrite proxy 让 same-origin path 在开发也工作

**沉淀位置（已写入）：** `framework/harness/generator.md` §13 "Frontend SSR vs Browser context"。

---

## Sub-pattern — Pre-flight PLACEHOLDER-REPLACE-ME grep scope (v0.9.24 #4，扩 §10)

**类型：** 新坑（CI workflow grep 范围错误）

**内容：** B021 F004 加 deploy workflow pre-flight 步 grep `PLACEHOLDER-REPLACE-ME` over `.`（整 repo），误命中 `docs/specs/B021-...-spec.md` / `docs/dev/B021-vm-setup-runbook.md` / `.github/workflows/bootstrap-env.yml`（其自身 grep 守卫代码）/ `progress.json`（讨论该 check 的 session_notes 字符串）/ `features.json`（acceptance 描述）等 5 处文档引用。每个引用都是讨论该 check 的合法用法，不是真 placeholder 漏到生产。

**规约：** pre-flight grep **scope 只能是 deployable source 目录**（如 `workbench/`），配合 `--exclude="*.md" --exclude="*.lock" --exclude="package-lock.json"` 进一步 narrow。

**沉淀位置（已写入）：** `framework/harness/generator.md` §10 GitHub Actions Node 24 forward-compat 节末新增 sub-pattern + 完整 yaml 代码示例。

---

## 整批回顾

B021 cloud-deploy 是项目首次「真云端单用户单 VM hosted」批次，暴露了项目历史从未遇过的 6 类 cloud / systemd / snap / Linux infra 互动陷阱。该批 framework 沉淀价值高于以往任何一批（v0.9.21 / v0.9.22 / v0.9.23 各只 1-2 条），主要因为：

- 之前所有批次都在 `trade/` 纯 stdlib 本地范围
- B020 是首次 dev tooling 含 Node/npm，仅触及 dev 环境陷阱（已沉淀 v0.9.23）
- B021 首次涉及 systemd + nginx + cert + cloud SDK + 多用户 host 共住 + GitHub Actions deploy，触发面广

后续 B022 Workbench Phase 1 + B023 Phase 2 复用同 cloud 基础设施，**应大幅受益于本批 v0.9.24 沉淀的 4 条规约**。

来源：B021 signoff `docs/test-reports/B021-cloud-deploy-auth-signoff-2026-05-17.md`，runbook `docs/dev/B021-vm-setup-runbook.md` first-time VM bootstrap addendum，及 commits `e5020ea` / `f4dcef2` / `5910bb6` / `5f6ad5d` / `10c7994` / `0f15d3d` / `92b6b6f` / `04b0e50` / `9bd4743` / `c727fd1` / `600fc55` / `4eb9c48`。
