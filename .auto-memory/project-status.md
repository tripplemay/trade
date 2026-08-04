---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B111 → `done`**（2026-08-01，fix_rounds=1，7/7）。签收 `docs/test-reports/B111-signoff-2026-08-01.md`（PASS）；Production = `55a5f5e`（与已验证产品实现 `fa1c6fe` 等价，仅多测试/报告/状态产物）。
- **批次成果**：三个生产 P0 修复并实证（momentum 纯 ETF / us_quality 真实持仓+fallback 诚实化 / regime 解冻+监控扩到 USD）；统一成本/执行口径（5+5bps 双腿、禁同会话成交，6.67×→1.0×）；min-trade + F006-3 负现金修复（生产恢复留痕 −$18.94→+$332.25，独立重放逐位吻合）；低波 first-look 双硬门过、双判据不过 → **最终 NO-GO（有效完成态）**。
- **★生产服务器 = `ssh deploysvr`**（194.238.26.173/root/kolmatrix_new）；旧 GCP IP 已退役（environment.md 已更正）。
- 新信号搜索继续冻结（重开仅限数据类别改变）；`DATA_NO_GO` 不变。

## 遗留 / 跟踪
- **S2（medium）**：workbench-backup.service 清理 /tmp 临时文件权限失败（根因是 F006-2 取证留下的 root 属主副本，已清理）；系统性修复（备份清理鲁棒性）已登记 backlog `BL-B112-OPS1`。
- S1（low）：paper_nav_history 保留 08-01 负现金历史行作事故审计证据（保留不动）；S3（low）：advisor 的 AIGC Gateway 503 跟踪。
- proposed-learnings 待确认队列：B107 退役判据、B110 裁定逻辑（6 条）、B111 新增 4 条——done 阶段提交用户确认。
- backlog.json：BL-B112-OPS1（backup 清理鲁棒性，medium）；BL-B112-DFG1（cn_attack 防御闸预注册 A/B 批，用户 08-04 同意登记，暂停开批裁定不变）；BL-B112-PRB1（partial_rebalance A/B，low）。`docs/test-reports/user_report/` 无用户反馈。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
