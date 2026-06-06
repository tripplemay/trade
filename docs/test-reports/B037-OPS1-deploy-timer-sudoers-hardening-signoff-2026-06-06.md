# B037-OPS1 Deploy Timer Sudoers Hardening Signoff 2026-06-06

> 状态：**PASS**
> 触发：B037-OPS1 F002 完成 L1/L2 验收

---

## 变更背景

B035/B036/B037 连续三批都出现同类运维摩擦：endpoint / DB 已经就绪，但新增 `workbench-*.timer` 因 deploy 用户 sudoers 不足而无法自动 install + enable，最终只能由 admin 每批手工补装。B037-OPS1 的目标是把这条接线链路做成 durable 机制，而不是继续靠一次性人工补丁。

---

## 变更功能清单

### F001：版本化 sudoers 工件 + deploy.sh DRY timer 循环 + 守门测试

**Executor：** generator

**文件：**
- `workbench/deploy/scripts/deploy.sh`
- `workbench/deploy/sudoers/deploy-workbench`
- `workbench/deploy/sudoers/workbench-install-unit`
- `workbench/backend/tests/safety/test_deploy_timer_wiring.py`
- `workbench/backend/tests/safety/test_market_scheduler_scope.py`
- `docs/dev/B021-vm-setup-runbook.md`

**改动：**
把三段硬编码 timer wiring 块收敛为 `workbench-*.timer` 单循环；新增版本化 sudoers 工件；通过 root-owned wrapper 消除 sudoers wildcard 的路径穿越类风险；补齐相应 safety guards 与 runbook。

**验收标准：**
- deploy.sh 不再残留 per-timer 硬编码 enable 块
- 所有现存 `*.timer` 均有 `.service` sibling，且被 sudoers / loop 自动覆盖
- 边界 (r) 继续保持 read-only / advisor precompute，不能触达 execution surface

### F002：Codex L1 + L2 真 VM 验收与签收

**Executor：** codex

**文件：**
- `docs/test-reports/B037-OPS1-deploy-timer-sudoers-hardening-signoff-2026-06-06.md`
- `progress.json`
- `features.json`
- `.auto-memory/project-status.md`

**改动：**
执行本地守门复核、重新 dispatch production deploy、抽取 deploy log / systemd / authenticated API 证据，并在全 PASS 后推进状态机到 `done`。

**验收标准：**
- deploy log 无 timer wiring warning
- `workbench-{market-context,advisor,prices}.timer` 全部 `enabled + active(waiting)`
- production `health=200`、authenticated `recent-errors=0`、Production SHA 与 `main` HEAD 等价
- Soft-watch S1 关闭

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 新增 timer 类型 | 本批不新增任何 timer，只修 deploy wiring |
| 调度频率 / service 内容 | systemd 单元语义不变 |
| 产品业务代码 | Home / Advisor / Market Context / Prices 业务逻辑均未在本批改动 |
| broker / execution 边界 | 继续永久禁止，scheduler 仍只允许边界 (r) |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| 新增 timer 上线方式 | admin 每批手工 install + enable | deploy.sh 自动 install + enable |
| deploy log | 常见 `Could not install/enable ...` warning | 三 timer 全部 `✓ enabled`，无 warning |
| 后续新增 `workbench-*.timer` | 需要再改 deploy.sh / sudoers 或人工补装 | 同一 loop + 同一 sudoers wildcard 自动覆盖 |

---

## 类型检查 / CI

```text
local targeted pytest: 32 passed
  - workbench/backend/tests/safety/test_deploy_timer_wiring.py
  - workbench/backend/tests/safety/test_market_scheduler_scope.py
local targeted ruff: All checks passed
secret grep on B037-OPS1 artifacts: 0 hits
generator handoff baseline CI: backend pytest 772 passed / ruff 0 / mypy 0 / backend+frontend CI green
deploy workflow: Workbench Deploy run 27050937093 passed
```

---

## L2 实测记录（v0.9.9 — BL-031 沉淀）

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | production `curl https://trade.guangai.ai/api/health` 返回 `version=5393343134f8e639ca97ee78cfe26e5fc6696f02`；本地 `git rev-parse HEAD` 同为 `5393343134f8e639ca97ee78cfe26e5fc6696f02`。 |
| 端到端流验证 | 我手动 dispatch `gh workflow run "Workbench Deploy" -r main`，run `27050937093` 成功。deploy log 显示 `install + enable workbench-advisor.timer`、`workbench-market-context.timer`、`workbench-prices.timer` 三段逐条执行，随后三条 `✓ <timer> enabled` 与 `✓ deploy complete`；未出现任何 `Could not install/enable` warning。 |
| 关键 invariant | authenticated `GET /api/debug/recent-errors` 返回 `{"count":0,"records":[]}`；production `/api/health` 返回 `{"status":"ok","db_connectivity":"ok"}`。 |
| 新增 user-facing 路由真 VM authenticated 200（v0.9.32 — B034 沉淀） | N/A。本批为 deploy/ops durable fix，不新增用户路由。 |
| 浏览器手动验（如 UI 类） | N/A。本批无 UI 变更；验收重点在 deploy log、systemd wiring 与 authenticated debug surface。 |

> authenticated `recent-errors` 使用 production env 派生的临时 Auth.js session cookie 完成，只读访问，不走真实 OAuth 交互。

### systemd wiring 证据

- `systemctl is-enabled workbench-market-context.timer` → `enabled`
- `systemctl is-enabled workbench-advisor.timer` → `enabled`
- `systemctl is-enabled workbench-prices.timer` → `enabled`
- `systemctl status ...timer --no-pager` 三者均为 `Loaded: ... enabled` + `Active: active (waiting)`
- 下次触发分别为：
  - `workbench-market-context.timer` → `2026-06-07 00:00:00 UTC`
  - `workbench-prices.timer` → `2026-06-07 00:30:00 UTC`
  - `workbench-advisor.timer` → `2026-06-07 01:00:00 UTC`

### Durable 验证

1. `deploy.sh` 的 wiring 已经从三段硬编码块收敛为：
   - `for timer_path in "${SYSTEMD_SRC}"/workbench-*.timer; do ...`
   - loop 内统一执行 sibling `.service` install、`.timer` install、`daemon-reload`、`enable --now "${timer_unit}"`
2. `deploy-workbench` 中的授权也同样收敛为：
   - `/usr/local/bin/workbench-install-unit * workbench-*.service`
   - `/usr/local/bin/workbench-install-unit * workbench-*.timer`
   - `/bin/systemctl enable --now workbench-*.timer`
3. 因此未来新增第 4 个合法命名的 `workbench-*.timer` 时，只要它与同名 `.service` 一起进入 release `systemd/` 目录，就会被同一 deploy loop 和同一 sudoers wildcard 自动接线；无需再改 `deploy.sh`，也无需再改 sudoers。

---

## Ops 副作用记录（v0.9.9 — BL-030/BL-031 沉淀）

本批次无数据库 ops。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → done）交付。
本签收完成后，`progress.json` 已更新为 `status: "done"`，signoff 路径已写入 `docs.signoff`。

---

## Production / HEAD 等价性（v0.9.25 — B022 沉淀）

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `5393343134f8e639ca97ee78cfe26e5fc6696f02` |
| Main HEAD (`git rev-parse HEAD`) | `5393343134f8e639ca97ee78cfe26e5fc6696f02` |
| Diff (`git log --oneline <deployed>..HEAD`) | `0 commits` |

**等价性判断：**

Production 与当前 `main` HEAD 同 SHA，直接 PASS。

---

## Post-signoff Deploy（v0.9.27 — B025 沉淀）

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | N/A |
| Workflow run 链接（若是） | N/A |
| Production 最终 SHA = signoff commit SHA | N/A |
| 接受不同步声明（若否） | 本次 signoff commit 仅含 signoff 报告、`progress.json`、`features.json`、`.auto-memory/project-status.md` 等状态机/证据文件；不含产品代码或 deploy-impacting 改动。按 v0.9.25 §Production/HEAD 等价性 接受签收后不同步，无需额外 dispatch。 |

---

## Decommission Checklist（v0.9.31 — B030 沉淀）

本批次不含 decommission，N/A。

---

## Soft-watch（不阻塞 done，需后续跟进）

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | B035/B036/B037 连续三批的“新增 timer 需 admin 手工 install/enable”摩擦 | **resolved** | 本批已关闭：deploy run `27050937093` 证明三 timer 可自动接线，后续 `workbench-*.timer` 由同一 loop + sudoers wildcard 持续覆盖。 |

---

## Framework Learnings

无新增 framework 沉淀需求。本批就是对既有 `evaluator.md §24` 的 durable fix 落地与闭环验证。

---

## Conclusion

可以签收。B037-OPS1 的 durable 目标已经兑现：production re-deploy 后 timer wiring 不再降级为 warning，三只现存 timer 均维持 `enabled + active(waiting)`，authenticated `recent-errors=0`，并且未来新增 `workbench-*.timer` 已有零手工覆盖路径。
