---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B112 → `done`**（2026-08-06，fix_rounds=2，2/2）。签收 `docs/test-reports/B112-signoff-2026-08-06.md`（PASS）；CI 全绿（`649c22f`）。
- **批次裁定（冻结判据，预注册）**：MA200 防御闸全样本 MaxDD 改善 4/4 档过主门 A（+8.15~+22.05pp），但 OOS 主门 B 仅 quality@10万 过（+5.62pp）。**pure 双档 NO-GO；quality 机制档（100万）NO-GO、容量档（10万）GO**。机制档未放行 → 无接产动作（H1 本批零生产变更）。
- **实质资产**：top-1500 PIT 宇宙构建链（生产同源排序、含退市、剔 .BJ 披露）+ 深历史基本面回填（245k 行/3923 只/98.3%）+ 防御闸实现（默认关、pre-B112 golden 基线对拍）。
- **★生产服务器 = `ssh deploysvr`**（194.238.26.173/root/kolmatrix_new）；旧 GCP IP 已退役。
- 新信号搜索继续冻结（重开仅限数据类别改变）；`DATA_NO_GO` 不变。

## 遗留 / 跟踪
- backlog：BL-B112-OPS1（backup 清理鲁棒性，medium）；BL-B112-PRB1（partial_rebalance A/B，low）。`docs/test-reports/user_report/` 无用户反馈。
- B112 soft-watch：S1 浮点末位噪声（hash 判据须用数值容差）；S2 spec 措辞「零生产部署」宜写「零生产接线/激活」。
- 低波 first-look（B111）最终 NO-GO；cn_attack 前向 −41% 的观察序列继续（研究态 paper 每日运行）。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
