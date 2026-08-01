---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B111 → `done`（fix_rounds=1）**。F001-F007 全部完成；signoff：`docs/test-reports/B111-signoff-2026-08-01.md`。
- **★生产服务器 = `ssh deploysvr`**（194.238.26.173/root/kolmatrix_new）；旧 GCP IP 退役，勿用。
- **F006 PASS**：F006-3 的 min-trade 后现金可行 sizing、`buy_scale_factor` 告警和 fail-loud postcondition 均通过；paper+现金不变量 79/79，生产只读重放逐数字匹配。
- **生产恢复留痕**：Master cash `-$18.944156` → **`+$332.248912`**，账本 cost `$0.351545`；5/5 paper 账户 cash≥0；已验证产品 SHA `fa1c6fe`，签收提交/生产 release `55a5f5e`（仅增测试/状态/报告），health 200/DB ok。
- **F007 最终裁定 NO-GO**：G1 `+2.2098pp`、正式日均 G2 `+2.8457pp` 过硬门，但仅 11 个可评年份且 bootstrap P=`0.862<0.90`，不满足冻结双判据。

## 接续（Planner done）
- 登记独立 ops 项：backup 文件已生成但清理 `/tmp/wb-ro.db` 权限失败；advisor 因 AIGC Gateway 503 失败，均与 B111 diff 无关。
- 下一 MTM 日确认 Master 新历史行 cash 继续非负；08-01 负现金行保留为事故审计证据。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等；`DATA_NO_GO` 不变。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
