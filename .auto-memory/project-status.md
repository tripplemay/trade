---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B113 → `fixing`**（2026-08-08，fix_rounds=0，1/3）。首轮 Codex 验收退回：`docs/test-reports/B113-blocker-2026-08-08.md`。
- **Blocker：OPS1 未到真实 service**。仓库 `workbench/deploy/backup/workbench-backup.sh` L1 PASS，但生产 `workbench-backup.service` 实际 `ExecStart=/opt/workbench/workbench-backup.sh`；该脚本仍为旧 `rm -f /tmp/wb-*.db /tmp/wb-*.db.gz`，root-owned marker 以 deploy 用户复现 `Operation not permitted`（测试 marker 已清理）。
- **PRB1 已可裁定但不签收整批**：F002 independent verifier PASS；pure 10万/100万均 **NO-GO**；quality 10万容量档 **GO**、100万机制档 **NO-GO**。机制档未放行 → 无接产动作。
- **★生产服务器 = `ssh deploysvr`**（194.238.26.173/root/kolmatrix_new）；旧 GCP IP 已退役。
- 新信号搜索继续冻结（重开仅限数据类别改变）；`DATA_NO_GO` 不变。

## 遗留 / 跟踪
- B113 待修：Generator 需让 `/opt/workbench/workbench-backup.sh` 获得 B113 cleanup 修复，或调整真实 service/runbook；复验必须重跑 root-owned `/tmp/wb-*` marker 跳过验证。
- B112 soft-watch：S1 浮点末位噪声（hash 判据须用数值容差）；S2 spec 措辞「零生产部署」宜写「零生产接线/激活」。
- 低波 first-look（B111）最终 NO-GO；cn_attack 前向 −41% 的观察序列继续（研究态 paper 每日运行）。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
