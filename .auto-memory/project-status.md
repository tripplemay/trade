---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B111 → `reverifying`（fix_rounds=1）**。F006-3（min-trade 负现金）已修复并部署（HEAD/Production = `fa1c6fe`，CI 绿），生产 Master 账户已恢复非负现金；F007 已定 done（维持 NO-GO = 有效完成态）；signoff 仍 null，待 Codex 复验 F006-3。
- **★生产服务器 = `ssh deploysvr`**（194.238.26.173/root/kolmatrix_new）；旧 GCP IP 退役，勿用。
- **F006-3 修复**：引擎三段式——先定全部成交（含 min-trade 跳过）→ 现金可行性（买单上限 =(cash+实际卖单×(1−rate))/(1+rate)，超出按比例缩买腿，`buy_scale_factor` 入 plan+service 告警，绝不 clamp）→ 建册；postcondition `new_cash<−1e-6` 即 raise。起始现金为负时 dust 卖单豁免 min-trade（不变量修复优先），新增 `paper.cli align` 恢复通道。
- **生产恢复留痕**：align master → cash −$18.94 → **+$332.25**（含成本准备金），账本行 2026-08-01 $0.35；全账户 cash≥0。cn_pure build_complete=0 系统一口径顺延，次日自动补。
- 此前已交付：统一口径（5+5bps 双腿、禁同会话成交）、正式 G2 +2.846pp、B-wide/N100/分段、S1 端口。

## 接续（Codex 复验要点）
- 只需复验 F006-3：`test_paper_min_trade.py` 10/10（含 evaluator 对抗用例 + 3 个 generator 回归）、生产 align 留痕与现金恢复（上文数字）、buy_scale_factor 告警语义。
- F006-1/2、F007-1/2/3 首轮已验过；F007 NO-GO 为最终裁定。
- 本机 venv 已装回 vcrpy/pytest-recording（此前 5 个 VCR 测试假红）。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等；`DATA_NO_GO` 不变。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
