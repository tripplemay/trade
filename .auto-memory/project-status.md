---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B111 → `reverifying`**（2026-08-01）。F004/F005 修复交付并部署（HEAD/Production = `ac1340f`，CI 全绿）；F006-2 生产证据已产出；signoff 仍为 null，待 Codex 复验。
- **★生产服务器已迁移**：`ssh deploysvr`（194.238.26.173/root/`~/.ssh/kolmatrix_new`，hostname vmi3430901）；旧 GCP 34.180.93.185 退役（environment.md 已更正，勿再用旧 IP）。
- **F006-1 已修**：统一前向口径（`execution_caliber.py` 单一事实源：5+5bps 双腿、禁同会话成交）；monthly.py 双腿 turnover；paper 同会话 mark 逐只过滤（跳过+次日重试，手动 align 豁免）；统一前 6.67×→后 1.0×，文档含受影响范围。
- **F007-1/2/3 已修**：正式 G2（12 个月日均剔 30%）**+2.846pp**（3157 交易日实拉，3 个停牌潮短表日披露）；B-wide 12.627% vs B-scored 10.840%（差 +1.786pp）；N=100 半年调仓 +2.253pp；冻结分段并排；Markdown 算术+t/NW/CI 同表、时态已修。阈值/判据一律未动，裁定仍归 Codex。
- **F006-2 证据**：02:41 recommendations 成功（persisted Master 快照 momentum=EEM/QQQ 纯 ETF、us_quality 15 只真实持仓、hk 诚实 fallback/mixed）；02:44 paper MTM 成功（rebalanced=0=已在目标无 churn，持仓自 07-23 为新代码目标，账本 07-22 $55.42=post-min-trade 样本）；cn_attack_pure 25 只 A 股按新口径顺延（mark 不晚于信号日），次日自动补——统一时点口径生产可观测。

## 接续（Codex 复验要点）
- 用 `ssh deploysvr`；核对 persisted snapshot/paper 持仓/新账本（数字见 progress.json session_notes.generator）；cn pure 明日应自动补齐成交。
- 复验正式 G2 与 B.1/B.3/B.5 全部冻结输出（产物 docs/audits/B111-F005-low-vol-first-look.{json,md}），独立复算后下裁定并写 signoff。
- 本机 venv 曾缺 vcrpy/pytest-recording（5 个 VCR 测试假红）已装回；全量 1759 root + 1844 backend 绿。
- B110 最终 NO-GO；新信号搜索继续冻结（重开仅限数据类别改变）。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等；`DATA_NO_GO` 不变。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
