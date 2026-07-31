---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B111 → `fixing`**。F004/F005 修复已交付并部署：**HEAD/Production = `ac1340f`**，Python/Backend CI 全绿；signoff 仍为 null。
- **F006-1 已修**：统一前向口径落地——`trade/backtest/execution_caliber.py`（5+5bps/腿、双腿、禁同会话成交）为单一事实源；monthly.py 单边 haircut → 双腿 turnover（+`prior_weights`/+`cost_amount`）；paper 侧 PriceMark 带日期、目标带 as_of_date，**同会话 mark 逐只过滤**（引擎按缺价跳过、build_complete=False、次日重试），手动 align 豁免。对账文档含统一前(6.67×)/后(1.0×)表 + 受影响范围；fixture 工作流钉 legacy 保 provenance。
- **F007-1/2/3 已修**：正式 G2 = 12 个自然月日均成交额剔 30% → **+2.846pp**（σ 比 0.843、11/11、P 0.841；3157 交易日/2694 调用；2015-07 停牌潮 3 个短表日跳过并披露）；单日代理 +4.106pp 仅并排。B-wide 12.627% vs B-scored 10.840%（差 +1.786pp）；N=100 半年调仓 +2.253pp（22 窗）；冻结分段 2014-2017/2018-2021/2022-2024 并排；Markdown 几何+算术+t/NW/CI 同表、时态已修。
- **工作流 B 裁定仍归 Codex**：修复只补证据/口径，未动任何阈值与判据。
- **S1 已修**：codex-setup/wait 默认端口 3099/3100。

## 接续
- **F006-2 待证**：修复轮部署后 recommendations 与 paper MTM 须各正常跑一轮（今晨 03:00/03:45 CEST timer 自动跑新代码即满足）；Codex 复验收 persisted snapshot（momentum 无 CAT/HD）、paper 持仓、新调仓账本、min-trade 前后成本。**本机 SSH 连不上 VM**（22 通、banner 超时，疑 fail2ban/源 IP）——SSH 恢复后可手动 `systemctl start workbench-recommendations.service / workbench-paper-mtm.service` 提前产出。
- 确认两轮运行成功 → 转 `reverifying`。
- B110 最终 NO-GO；新信号搜索继续冻结（重开仅限数据类别改变）。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等；`DATA_NO_GO` 不变。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
