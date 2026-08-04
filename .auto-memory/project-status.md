---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B112 → `fixing`**（2026-08-04，fix_rounds=0，0/2）。首轮验收报告 `docs/test-reports/B112-F002-verification-2026-08-04.md`，正式裁定 **INCONCLUSIVE**。
- **High 1**：A/B 实际使用 799-800 只 B070 研究宇宙，违反冻结的 top~1500/生产同源口径；须明确唯一 PIT 宇宙并清空 cache 重跑 8 cell。
- **High 2**：远端 HEAD quality runner 因 `report_date=str` 首月 TypeError；交付数字依赖未提交本地修补。
- **High 3**：CSI300 月末评估日缺失会静默使用旧日收盘并标 off/on，未 fail-open。
- **Medium**：报告缺 H6 覆盖分母/OOS Sharpe/年化换手；V0 byte 零回归测试未做实际基线比较。
- 独立复算确认现有数字内部一致：pure 10万 GO/100万 NO-GO；quality 两档 NO-GO。但数据/执行缺陷修复前不得形成正式裁定。
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
