# B045-OPS1 — trade wheel deploy 可靠性（自动装 + smoke import check）

> **状态：** planning（2026-06-07 起草）。
> **批次类型：** 运维/部署卫生修复（横切，非产品 roadmap 序列；同 B037-OPS1 插入先例）。
> **来源：** B045 signoff §Soft-watch S4 + §Framework Learnings（已沉淀 README §经验教训「venv 多包安装」+ CHANGELOG v0.9.36）。
> **命名：** 独立前缀 `B045-OPS1`，不占产品序号。

---

## 1. 目标

让 `trade/` wheel 在 deploy 时**可靠自动装入 VM venv**（无需手动 force-reinstall），并加 **deploy 后 smoke import check** 把静默安装失败转为响亮失败。根治 B044/B045 的两个部署坑（Finding #2 `--upgrade` 同版本 skip；S4 `--force-reinstall` 首次 deploy 仍停旧版需手动）。

---

## 2. 根因现状（待 generator 诊断确认）

- CI **确实**构建 trade wheel（`workbench-deploy.yml` line 127 `python -m build --wheel`）+ 下发到 `${STAGE_DIR}/trade-dist/`（line 180-181）→ wheel 在 release tree 内。
- deploy.sh line 72 **已用** `--force-reinstall`（B045 F004 Finding #2 修）。
- **但 S4：首次 deploy 后 VM venv 仍 0.1.0，需手动 force-reinstall 才到 0.2.0。** 根因未确证，候选：
  - (a) 构建出的 wheel 版本号实际仍 0.1.0（version bump 进错文件 / build 用了 stale/cache）；
  - (b) `--force-reinstall` + `--quiet` 在 deploy 用户下静默失败（sudo/venv pip path / dep 解析 offline）；
  - (c) pip 对同名 wheel 缓存。
- F001 须真机诊断确认根因，对症修。

---

## 3. 决策（2026-06-07 用户已批，★=拍板）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 优先级 | ★ **先修 S4 再 B046** | trade/ 自动装仍坏是可靠性债，未来 trade/ 改动会撞 |
| 防线 | **deploy 后 smoke import check（铁律，v0.9.36）** | 无论根因，静默失败→响亮失败 |
| 命名 | **独立前缀 B045-OPS1** | 不占产品序号 |

---

## 4. 永久硬边界（继承）

- §12.10.2：trade/ 入 venv 供 precompute（job）；请求路径仍禁 trade import（AST 守门不破）。
- 不改评分逻辑 / 不改 trade 业务代码 / 仅动 deploy + 打包 + smoke check。
- deploy 用户 narrow-sudoers 原则延续（不扩 sudo）。

---

## 5. 技术架构

### 5.1 诊断 + 修复 trade wheel 自动装（F001）

- 真机诊断 S4 根因（version bump 是否进构建 wheel / `--force-reinstall` 在 deploy 用户实际行为 / pip cache）。
- 对症修，确保 **fresh deploy 后 VM venv 的 trade version == 构建 wheel version**（无需手动）。候选修法（按诊断）：
  - 确保 version bump 进入 build 的权威 pyproject（repo-root，trade wheel build 源）；
  - `--force-reinstall --no-deps`（trade 依赖已在 venv，避免 offline dep 解析失败）+ 去 `--quiet` 或捕获非零退出；
  - 清 pip cache / 用 wheel 绝对路径。

### 5.2 deploy 后 smoke import check（F001，核心 durable 防线）

- deploy.sh 在 trade install 后加 smoke check：在 VM venv 内跑 `python -c "import trade.backtest.master_portfolio; import trade.data.data_root"`（precompute 真实依赖的关键模块）。
- **失败 → deploy 硬失败 / `::error::` 响亮告警**（不被 `--quiet` 吞）；不能只靠 pip 返回 0 当成功。
- 同理可加 workbench_api precompute 模块 import 校验。

### 5.3 测试 / 守门

- deploy.sh smoke check 段可 dev rehearsal（venv 缺 trade 时 best-effort warn 不崩）。
- 若有 deploy 脚本守门测试（grep/结构），加 smoke check 存在断言。

---

## 6. Feature 拆分

| ID | executor | 标题 |
|---|---|---|
| F001 | generator | 诊断+修 trade wheel deploy 自动装可靠性 + deploy 后 smoke import check（import trade 关键模块，失败硬报）+ deploy 守门 |
| F002 | codex | L2 真 VM：fresh deploy（dispatch）后 trade version==wheel version 无需手动 + smoke check 跑过 + precompute import 正常（recommendation_snapshot 可生成）+ signoff |

---

## 7. 不做的事（YAGNI）

- 不改 trade 评分 / 业务逻辑 / B045 数据 pipeline。
- 不改 §12.10.2 enforcement / 请求路径守门。
- 不做 regime/current_weight（B046）/ disk 扩容（S1 另议）。
- 不扩 deploy 用户 sudo。

---

## 8. 验收门槛汇总

- **F001**：S4 根因诊断记录 + 修复使 fresh deploy 后 trade version 自动匹配 wheel；deploy.sh 加 smoke import check（trade 关键模块，失败硬报，不被 `--quiet` 吞）；deploy dev rehearsal 不崩；backend pytest 不破 / 既有部署路径不破。
- **F002**：L2（真 VM）：(1) dispatch fresh deploy → deploy log 显示 trade install + **smoke check 跑过**；(2) **VM venv trade version == 构建 wheel version（无需手动 force-reinstall）**；(3) `python -c "import trade.backtest.master_portfolio; import trade.data.data_root"` 在 venv OK；(4) workbench-recommendations.service trigger → recommendation_snapshot 正常生成（precompute import 不再 ModuleNotFoundError）；(5) health 200 + recent-errors=0 + HEAD≡main + B026 absent。Signoff: docs/test-reports/B045-OPS1-trade-wheel-deploy-reliability-signoff-2026-MM-DD.md（§Production/HEAD + §Post-signoff Deploy + **§Soft-watch S4 标记 resolved**）。Framework 候选：若 smoke-check-after-install 成通用部署规约可记。

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| S4 根因真机难复现 | F001 诊断 + 无论根因 smoke check 兜底（响亮失败）；用户授权 generator 真机诊断（同 B044/B045 先例）|
| smoke check 误报阻断正常 deploy | 仅 import 校验（不跑业务）；dev rehearsal best-effort；失败信息明确指向 trade install |
| 修 deploy.sh 破坏既有 backend/frontend 部署 | smoke check 加在 trade install 后、不动 backend/frontend 段；F002 验既有部署不破 |

---

## 10. 与既有批次的边界 + 后续

- **不改**：B045 数据 pipeline / B044 评分 / 前端 / trade 业务码。
- **解决**：B045 §Soft-watch S4（trade wheel 自动装）。
- **后续**：B046（regime reconcile + account current_weight）；disk S1（84%）另议；S2/S3 留 B046。
