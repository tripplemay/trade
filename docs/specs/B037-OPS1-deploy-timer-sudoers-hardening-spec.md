# B037-OPS1 — Deploy timer 自动接线 durable fix（sudoers 授权 + deploy.sh DRY）

> **批次类型：** 运维/部署卫生修复（横切，非 Phase 3 产品 roadmap 序列）。
> **来源：** B037 signoff `docs/test-reports/B037-home-restructure-signoff-2026-06-06.md` §Soft-watch S1 + §Framework Learnings；同根摩擦在 B035 / B036 / B037 三批重复出现。
> **命名：** 独立前缀 `B037-OPS1`，不占产品 roadmap 序号；Phase 3 roadmap B038–B043 保持不变。

---

## 1. 目标

让新增的 `workbench-*.timer`（read-only 数据拉取 / 预计算）在 `deploy.sh` 部署时**自动 install + enable**，无需 admin 每批手工接线。根治 B035/B036/B037 连续三批「endpoint/DB 已绿但 timer 没装」的运维摩擦（已沉淀 evaluator.md §24）。

---

## 2. 根因（已确认）

- `deploy.sh` 自 B035 起已有每个 timer 的 install/enable 逻辑（B035/B036/B037 各加一段近乎重复的 best-effort 块）。
- **但 VM 上 `/etc/sudoers.d/deploy-workbench` 只授权 5 条**（`systemctl restart/status workbench-{backend,frontend}.service` + `daemon-reload`），**没有**授权：
  - `/usr/bin/install -m 644 ... /etc/systemd/system/workbench-*`
  - `/bin/systemctl enable --now workbench-*.timer`
- 因此 deploy.sh 那三段 sudo 调用全部权限失败 → 只 `::warning::` → 每批 admin 手装。
- deploy 用户无法自授权 sudoers（chicken-and-egg），sudoers 应用本质是**一次性 admin VM 动作**。

---

## 3. 决策（2026-06-06 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 是否做 | ★ **先做 S1 运维修复批次** | 优先于 Phase 3 B038，根治三批重复摩擦 |
| sudoers 授权范围 | ★ **通配符 `workbench-*.{service,timer}`** | 未来新 timer 零手工、deploy.sh 自动装 = 真 durable；范围仍锁 `workbench-` 前缀 + systemd 目录 |
| 批次编号 | ★ **独立前缀 B037-OPS1** | 不占产品 roadmap 序号，roadmap B038–B043 不动 |

---

## 4. 永久硬边界（继承，不可破）

- **timer 仅边界 (r)**：read-only 市场数据拉取（market-context / prices）+ 已过 CI safety-gate 的 advisor 预计算；**NOT 交易执行 / 下单 / broker**。本批不新增任何 timer，只改接线机制。
- sudoers 授权**仅限** `workbench-*` 前缀单元 + `/etc/systemd/system/` 目录；不得扩到任意 service / 任意路径 / 任意 sudo。
- deploy 用户**不得**获得 install 包 / 编辑其他 config / 任意 sudo 的能力（B021 narrow-sudoers 原则延续）。

---

## 5. 技术架构

### 5.1 版本化 sudoers 工件（仓库内新增）

新增 `workbench/deploy/sudoers/deploy-workbench`（440, root:root），作为 VM `/etc/sudoers.d/deploy-workbench` 的权威源：

```
# 现有 5 条（B021）保留
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart workbench-backend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart workbench-frontend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status workbench-backend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl status workbench-frontend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload
# B037-OPS1 新增：timer 自动接线（通配符，锁 workbench- 前缀 + systemd 目录）
deploy ALL=(ALL) NOPASSWD: /usr/bin/install -m 644 * /etc/systemd/system/workbench-*.service
deploy ALL=(ALL) NOPASSWD: /usr/bin/install -m 644 * /etc/systemd/system/workbench-*.timer
deploy ALL=(ALL) NOPASSWD: /bin/systemctl enable --now workbench-*.timer
```

> **安全注意（Generator + security-reviewer 必须裁决）：** sudoers 通配符用 `fnmatch(3)` **不带** `FNM_PATHNAME`，`*` 可匹配 `/`。F001 实施时必须由 security-reviewer 评估通配符能否被滥用作路径穿越（如 install 目标 `workbench-*` 是否可逃逸 `/etc/systemd/system/` 目录），并在 spec/runbook 记录残留风险与缓解（例如目标前缀 `/etc/systemd/system/workbench-` 字面锁定已限制逃逸面；`install -m 644` 模式固定）。若评估认为通配符逃逸面不可接受，回退到「通配符但更紧后缀约束」或显式枚举并报告。

### 5.2 deploy.sh DRY 重构

把 B035/B036/B037 三段硬编码 timer 块收敛为**对 `${SYSTEMD_SRC}/workbench-*.timer` 的单循环**：
- 对每个 `*.timer`：install 其 `.service` 兄弟 + install `.timer` + `daemon-reload` + `enable --now`。
- 保留 best-effort warn 语义（sudo 失败不阻断 backend/frontend 部署）+ 边界 (r) read-only 注释。
- **未来新 timer（B038+）零改 deploy.sh 自动覆盖。**

### 5.3 守门 / 回归测试

- `tests/safety/`（或 deploy 测试目录）新增守门：
  - (a) deploy.sh **无残留 per-timer 硬编码 enable 块**（grep 断言：`enable --now workbench-` 字面只出现在循环体一次，不是每 timer 一段）。
  - (b) `workbench/deploy/systemd/` 下每个 `*.timer` 都有同名 `.service` 兄弟（循环前提）。
  - (c) sudoers 工件覆盖所有现有 timer（解析 sudoers + 交叉核对 systemd 目录，确保通配符匹配现存单元）。

### 5.4 文档

更新 `docs/dev/B021-vm-setup-runbook.md` sudoers 段：新授权内容 + 「装入后 deploy.sh 自动接线」说明 + 一次性 admin 应用步骤。

---

## 6. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | sudoers 工件 + deploy.sh DRY 循环 + 守门测试 + runbook 更新（security-reviewer 裁决通配符） |
| F002 | codex | L2 真 VM 验收：admin 应用 sudoers → re-deploy → 三 timer 自动 enabled（无 warn）+ durable 验证 + signoff + 关闭 Soft-watch S1 |

---

## 7. Ops 前置动作（F002 L2 前，admin 在用户授权下执行）

`/etc/sudoers.d/deploy-workbench` 替换为 §5.1 新工件（`sudo visudo -c` 校验通过 + chmod 440）。**这是一次性 admin VM 动作**（deploy 用户无法自授权），等同 B021 #3 / B035-B036 timer 手装的角色边界例外，须用户显式授权。完成后即可 re-deploy 让 deploy.sh 自动接线。

---

## 8. 不做的事（YAGNI）

- 不新增任何 timer / service（本批只改接线机制）。
- 不改 timer 调度频率 / 边界 (r) 语义。
- 不把 sudoers 应用塞进 deploy.sh（chicken-and-egg：deploy 用户无权写 `/etc/sudoers.d/`）。
- 不扩 deploy 用户到任意 sudo / 包安装 / 其他 config。
- 不触 Phase 3 产品工作（B038+ Home market context 等）。

---

## 9. 验收门槛汇总

- **F001**：sudoers 工件 + deploy.sh 单循环 + 3 守门测试 + runbook 更新；CI 全绿（backend pytest 不破 / 既有部署路径不破）；security-reviewer 对通配符出具裁决记录；boundary (r) 仍只读非执行。
- **F002**：admin 应用 sudoers 后 re-deploy；`systemctl is-enabled workbench-{market-context,advisor,prices}.timer`=enabled + `status`=active(waiting)；deploy 日志**无 timer warn 行**（自动接线成功）；durable 验证（循环覆盖所有现存 timer，假想新 timer 会被覆盖）；health 200 / recent-errors=0 / HEAD≡main；signoff 用模板（含 §24 接线检查勾选 + §Soft-watch S1 标记 resolved）。

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| sudoers 通配符路径穿越 | F001 security-reviewer 裁决 + 目标前缀字面锁 `/etc/systemd/system/workbench-` + runbook 记残留风险 |
| deploy.sh 循环重构破坏现有 3 timer 接线 | 守门测试 (b) 保证每 timer 有 service 兄弟；F002 L2 实测三 timer 全 enabled |
| sudoers 应用失误锁死 deploy 用户 | `visudo -c` 强制校验；保留现有 5 条不动；分离 drop-in 文件不碰主 sudoers |
| admin 未应用 sudoers 就验收 | F002 把「sudoers 已应用」列为 L2 前置；未应用则 deploy 仍 warn（回到现状，不退化） |

---

## 11. 参考文档

- B037 signoff §Soft-watch S1 + §Framework Learnings：`docs/test-reports/B037-home-restructure-signoff-2026-06-06.md`
- evaluator.md §24（本批是其 durable fix）：`framework/harness/evaluator.md`
- 现有 sudoers + VM 运维：`docs/dev/B021-vm-setup-runbook.md`
- deploy.sh：`workbench/deploy/scripts/deploy.sh`（L265-311 三 timer 块）
- generator.md §12（systemctl 多 service vs sudoers）/ §12.9（production secret 三处接线）：同族 ops-wiring 规则
