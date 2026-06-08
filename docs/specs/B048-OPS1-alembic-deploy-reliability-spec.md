# B048-OPS1 — deploy alembic 自动升级可靠性（migrations 自动 apply + 后置断言 head）

> **状态：** planning（2026-06-07 起草）。
> **批次类型：** 运维/部署卫生修复（横切，非产品序列；同 B045-OPS1 先例）。
> **来源：** B048 signoff §Finding #1 + §Soft-watch S2——deploy 后 prod alembic 停在 0006、缺 0007-0011 共 5 个 migration，`price_history` 等表不存在，需手动 `alembic upgrade head`。
> **命名：** 独立前缀 `B048-OPS1`，不占产品序号。
> **排序：** 里程碑 C 路径 **order 3**（BL-B023-S1 闭环冒烟之前）——闭环冒烟需 deploy 可靠建表，否则又缺表。

---

## 1. 目标

让 deploy 时 **DB migrations 可靠自动 apply 到 prod**（无需手动 `alembic upgrade head`），并加 **deploy 后断言 `alembic current == head`**（失败硬报，把静默失败转响亮失败，同 v0.9.36 smoke check 思路）。根治 B048 Finding #1。

---

## 2. 根因现状（待 generator 真机诊断确认）

- deploy.sh **有** alembic 步骤（注释 line 11『Run alembic upgrade head (idempotent)』+ 源 `/etc/workbench/workbench.env` 后跑），但 B048 deploy 后 prod 停 0006 缺 0007-0011。
- 候选根因（含历史同类坑）：
  - (a) **env 未加载→alembic 跑 DEFAULT_DEV_DB_URL scratch DB**（deploy.sh 注释明载 B022 同款坑：ENV_FILE 不可读→warning→升级 scratch 而非 prod；可能 regression / env 文件权限/路径）；
  - (b) alembic 步骤 silent fail（`--quiet` / 退出码未捕获）；
  - (c) B044 主机挂死 + B045 中断部署期间该步骤未达/SCP 失败 → prod DB 久未迁移积累 5 个缺口。
- F001 真机诊断确认根因，对症修。

---

## 3. 决策（2026-06-07 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 处理方式 | ★ **拆 B048-OPS1 修部署** | alembic 自动升级缺陷正交 B048 功能码、影响所有后续批次（同 B045-OPS1） |
| durable 防线 | **deploy 后断言 alembic current == head**（planner 决） | 无论根因，静默失败→响亮硬失败（v0.9.36 同思路） |
| 排序 | **order 3，BL-B023-S1 之前** | 闭环冒烟需 deploy 可靠建表 |

---

## 4. 永久硬边界（继承）

- 单 VM 单用户 / WORKBENCH_DB_URL 指向 prod sqlite；alembic 幂等。
- §12.10.2 / B023 / 评分边界不动（仅动 deploy.sh + 可能 CI）。
- deploy 用户 narrow-sudoers 不扩。

---

## 5. 技术架构

### 5.1 诊断 + 修 alembic 自动升级（F001）

- 真机诊断 Finding #1 根因（env 是否加载、alembic 是否对 prod DB 跑、退出码、prod DB 当前 revision）。
- 对症修，确保 **fresh deploy 后 prod DB alembic current == head**（无需手动）。候选修法按诊断：
  - 确保 ENV_FILE 可靠加载（alembic 对 prod WORKBENCH_DB_URL 跑，非 scratch）；
  - 去 `--quiet` / 捕获 alembic 非零退出 → deploy 硬失败；
  - 确认 alembic 步骤在 SCP/install 成功后必达。

### 5.2 deploy 后断言 alembic == head（F001，核心 durable 防线）

- deploy.sh alembic upgrade 后加断言：`alembic current` == `alembic heads`（对 prod DB）；**不等 → `::error::` + exit 1 硬失败**（不被静默吞）。
- 同理可 echo 当前 revision 便于排查。

### 5.3 测试 / 守门

- deploy.sh 段可 dev rehearsal（best-effort 不崩）。
- deploy 守门测试加 alembic-upgrade + assert-head 步骤存在断言。

---

## 6. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 诊断+修 deploy alembic 自动升级（prod DB 升到 head）+ deploy 后断言 alembic current==head 硬失败 + deploy 守门 |
| F002 | codex | L2 真 VM：fresh deploy（dispatch）后 migrations 自动 apply（alembic==head，无需手动）+ price_history 等表存在 + 断言跑过 + signoff（§Finding #1 / S2 resolved）|

---

## 7. 不做的事（YAGNI）

- 不改 migration 内容 / B048 功能码 / 评分逻辑。
- 不动 §12.10.2 / B023 / deploy 用户 sudo。
- 不做 DB 多用户 / 非 sqlite。

---

## 8. 验收门槛汇总

- **F001**：根因诊断记录 + 修使 fresh deploy 后 prod DB alembic==head；deploy.sh 加 alembic==head 后置断言（失败硬报，不静默吞）；deploy dev rehearsal 不崩；backend pytest 不破 / 既有部署路径不破。
- **F002**：L2（真 VM）：(1) dispatch fresh deploy → deploy log 显示 alembic upgrade + **alembic==head 断言跑过**；(2) **prod DB alembic current == head（无需手动 upgrade）**——对比 B048 的需手动；(3) **price_history（0011）等 0007-0011 表存在**；(4) /api/health 200 + risk_panel/recommendations（依赖这些表）正常 + recent-errors=0；(5) HEAD≡main + B026 absent。Signoff: docs/test-reports/B048-OPS1-alembic-deploy-reliability-signoff-2026-MM-DD.md（§Production/HEAD + §Post-signoff Deploy + **§Finding #1 / Soft-watch S2 resolved**）。Framework 候选：alembic-assert-head-after-deploy 若成通用部署规约（同 smoke import check 家族）记 §Framework Learnings。

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 根因真机难复现 | F001 诊断 + 无论根因 alembic==head 断言兜底（响亮失败）；用户授权 generator 真机诊断（同 B044/B045 先例）|
| 修 deploy.sh 破坏既有部署 | alembic 段加断言不动 backend/frontend/trade 安装段；F002 验既有部署不破 |
| prod DB 已缺 5 migration | F001/F002 deploy 一次性补齐（alembic upgrade head 幂等升到 0011）|

---

## 10. 与既有批次的边界 + 后续

- **不改**：B048 功能 / 评分 / 前端。
- **解决**：B048 §Finding #1 + §Soft-watch S2（alembic 未自动升级）。
- **后续**：里程碑 C 路径恢复——BL-B023-S1 闭环冒烟（order 调整后，用真实 diff+真实安全层，deploy 可靠建表）→ HK-China → B042/B047/B049。
