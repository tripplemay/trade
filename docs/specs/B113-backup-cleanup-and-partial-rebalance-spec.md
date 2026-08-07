# B113 — backup 清理鲁棒性（OPS1）+ cn_attack partial_rebalance A/B 裁定（PRB1）

**日期：** 2026-08-06
**前置：** B112（done）。backlog `BL-B112-OPS1` + `BL-B112-PRB1`（用户 2026-08-06 选定两条同批）
**性质：** 双工作流。**A = 运维小修**（deploy 脚本，CI + L1 验收）；**B = 裁定批**（回测证据，零生产接线）。

---

## 0. 批次构成

| 条目 | 来源 | 内容 |
|---|---|---|
| OPS1 | B111 signoff soft-watch S2 | `workbench-backup.sh` 的清理段用通配符 `/tmp/wb-*` 且无容错：备份文件本身已生成，却因清理他主文件（root 属主）权限失败导致整个 service 显示 failed（2026-08-01 生产实例） |
| PRB1 | B081 F005（planner 裁定 c772c72）遗留 | `partial_rebalance`（band partial，Option A）实测为**收益改善型**节奏变动（调仓 639→1517、OOS +28.4%→+32.7%），默认 False；按 verdict-gating 纪律须独立 A/B 裁定批才能上线 |

---

## 工作流 A — OPS1：备份清理鲁棒性

### A.0 边界

- 只改 `workbench/deploy/backup/workbench-backup.sh` 的清理逻辑；备份主流程（快照/gzip/存储/保留策略）**一字不动**。
- 修复后须经本地测试 + Codex L1；生产行为变化只有「清理失败不再 fail 整个 service」。

### A.1 冻结要求

1. **清理不再影响退出码**：`trap cleanup EXIT` 的清理失败必须吞掉（备份成功即成功）。
2. **收窄清理范围**：本 run 的暂存文件按精确文件名删；通配清扫只删**当前用户属主**的 `/tmp/wb-*`（`[[ -O ]]`），他主文件一律跳过。
3. **回归测试**（Generator 提供脚本）：清理函数在「通配位被他主/不存在文件占位」时不报错退出、不误删他主文件。

## 工作流 B — PRB1：partial_rebalance 预注册 A/B 裁定

### B.0 冻结口径（先于看到任何结果）

| 项 | 规定 |
|---|---|
| 引擎 | 现 `trade/backtest/cn_attack_momentum_quality/` 引擎，B081 保真开关全开 |
| 数据链 | **完全复用 B112 fix-round 产物**：top-1500 PIT 宇宙（30 块）、拼接价格面板、回填基本面、CSI300——零新 API 成本 |
| 窗口 | **2019-04-01 → 2026-07-31**（与 B112 同，冻结）；IS/OOS 机械 70/30 |
| 本金 | 10 万 + 100 万两档并排（100 万=机制判据、10 万=容量判据） |
| 两 mode | pure / quality 各自独立裁定 |
| V0（对照） | `partial_rebalance=False`（生产现状，全 band） |
| V1 | `partial_rebalance=True`（B081 Option A：per-name 阈值 0.5%，聚合计量带被绕过） |
| 成本 | 现 CnCostModel（印花 5bp 卖出 + 佣金 2.5bp + 滑点 5bp） |
| ★与 B112 的关系 | 防御闸**关闭**（defense_gate=None）——本批只测 partial_rebalance 一个自变量；与 DFG1 不混合归因 |

### B.1 ★预注册判据（裁定归 Codex）

| 判据 | 门槛 | 阈值的独立理由 |
|---|---|---|
| **主判据（收益声明）** | OOS ΔCAGR **≥ +1.0pp**（净成本后） | 沿用 B110 冻结的 1.0pp NO-GO 线——净收益改善低于此不值得改生产节奏 |
| **副判据 A（风险约束）** | OOS ΔMaxDD **≥ −2.0pp** | 节奏加密不得显著加深回撤；2pp 沿用 B112 副判据量级 |
| **副判据 B（成本约束）** | 年化换手倍率（V1/V0）**≤ 3.0×** | B081 实测 2.4×（639→1517）；超过 3× 说明换手失控，成本模型外的摩擦（冲击成本）将主导 |
| **裁定规则** | 主+副全过 → **GO**；任一不过 → **NO-GO**；数据/执行缺陷 → **INCONCLUSIVE** | — |

- 并列披露（不作判据）：全样本/OOS 的 CAGR、Sharpe、MaxDD、年化换手、成本、调仓数、分年收益。
- **H7：Generator 只算不裁**；产物禁词机器判据沿用 B110-B112 族。

### B.2 硬边界

- H1 零生产接线/激活：A/B 只在回测层；GO 后接产另批（改 live 发布 cadence + paper 语义须单独 spec）。
- H2 不动 readiness、`DATA_NO_GO`、不新增 alpha 信号。
- H3 复用 B112 数据链，不重拉数据；任何输入缺口结构化披露（H6 逐段）。

## Feature 拆分

| ID | executor | 内容 |
|---|---|---|
| **F001** | generator | OPS1 备份清理修复 + 回归测试脚本 |
| **F002** | generator | PRB1 A/B 实现 + 全矩阵执行（2 mode×2 臂×2 本金）+ 报告（只算不裁） |
| **F003** | codex | 独立验收：A 的 L1 + B 的零 import 复算与裁定；逐条核对冻结条款；输出 signoff |

## 给 Codex（F003）的前置提醒

1. F002 的产物必须可从空 cache 复跑（runner 与数据链均已在库）。
2. 裁定表逐档陈述（100 万机制 / 10 万容量分开）；OOS 数字与全样本并排读（B070 窗口落位假象前科）。
3. 换手倍率检查的是**年化换手比值**，不是绝对值。
