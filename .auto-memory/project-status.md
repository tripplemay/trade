---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B112 → `fixing`**（2026-08-06，fix_rounds=1，0/2）。复验报告 `docs/test-reports/B112-F002-reverification-2026-08-06.md`。
- 首轮 3 High 已修：30×1500 PIT 宇宙、quality 原始路径、缺评估日 fail-open 均通过；空 cache 完整 8 cell 跑通，定向 17/17、ruff/mypy/CI 绿。
- **裁定已收敛**：pure 10万/100万均 **NO-GO**；quality 10万容量档 **GO**、100万机制档 **NO-GO**，故两个 mode 的机制均不放行。
- **Medium F001-4a**：H6 价格 splice 漏披露 3,219,272 行 `prices_newnames.pkl`；指数 1,780 交易日被误标为日历日。
- **Medium F001-5a**：V0 测试仍比较当前默认 config 与显式 `None`，未对拍 pre-B112 `2e81836` golden 基线。
- 下一轮只需修复/复验 F001-4a/5a，重渲染报告；`docs.signoff` 仍为 null。
- **B111 已完成**：签收 `docs/test-reports/B111-signoff-2026-08-01.md`；Production=`55a5f5e`。
- **★生产服务器 = `ssh deploysvr`**（194.238.26.173/root/kolmatrix_new）；旧 GCP IP 已退役（environment.md 已更正）。
- 新信号搜索继续冻结（重开仅限数据类别改变）；`DATA_NO_GO` 不变。

## 遗留 / 跟踪
- **S2（medium）**：workbench-backup.service 清理 /tmp 临时文件权限失败（根因是 F006-2 取证留下的 root 属主副本，已清理）；系统性修复（备份清理鲁棒性）已登记 backlog `BL-B112-OPS1`。
- S1（low）：paper_nav_history 保留 08-01 负现金历史行作事故审计证据（保留不动）；S3（low）：advisor 的 AIGC Gateway 503 跟踪。
- proposed-learnings 待确认队列：B107、B110、B111 条目待 Planner done 阶段处理。
- backlog：BL-B112-OPS1、BL-B112-PRB1 保留；DFG1 已进入当前 B112。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
