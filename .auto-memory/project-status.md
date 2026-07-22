---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）
type: project
---

## 当前状态
- **B111 → `fixing`**。Codex F006/F007 首轮验收 FAIL；报告 `docs/test-reports/B111-F006-F007-verification-2026-07-21.md`，signoff 仍为 null。
- HEAD/Production 均为 `279de7a`，Python CI、Backend CI、Deploy 全绿；L1 3099/3100 smoke 通过，B111 定向测试 180 passed。
- **F001-F003 真数据行为通过**：当前 release 在生产统一 CSV 上只读评分得到 Momentum=EEM/QQQ（仅 ETF）；US Quality 五因子各 27/27 非 NaN、15 个股票目标；all-NaN/pure-defensive 会标 fallback+warning/mixed；regime as_of 已从 2026-05-29 前进到 2026-06-30，45 天告警可触发。
- 生产已发布 Master snapshot/paper 仍来自部署前旧运行（CAT/HD+SGOV）；F004 部署后 paper 调仓 0 次，实际持仓与 min-trade 前后成本须下轮真机复验。
- **F004 high finding**：未完成 spec 的 paper/回测执行与成本假设统一，只量化仍存在的 3bps 单边/T+1 open vs 10bps 双边/当日 close = 6.67x。激活后实测 9 次调仓/$429.7968/0.4298% 初始 NAV。
- **工作流 B 当前裁定 NO-GO**：Codex 零 import 独立重算 60 个无条件样本及全部五 variant，交付汇总全匹配；主 +3.0859pp、sigma 比 0.8573，但 bootstrap P=0.862<0.90，且只有 11 个可评估年份，未证明 11/12。
- **F005 high findings**：G2 用形成日单日 amount 而非冻结的日均；缺 B-wide+差值、N=100/半年调仓、分段并排；Markdown 未把算术超额/CI 与主结果同表，且执行后仍写“尚未执行”。

## 接续
- Generator 修 F004/F005 证据与口径，不得调参追求翻转 NO-GO；部署后让 recommendations 与 paper MTM 各正常跑一轮，转 `reverifying`。
- Codex 复验 persisted snapshot/paper holdings、min-trade 成本前后、正式日均 G2 与全部 B.1/B.3/B.5 冻结输出；全 PASS 才创建 signoff。
- 测试基础设施 soft-watch：AGENTS 要 3099，但 setup 默认 backend 8723/frontend 3000；下轮统一默认值。
- B110 最终 NO-GO；新信号搜索继续冻结（重开仅限数据类别改变）。

## 永久边界
- research-safe / no-broker / no-AI 预测 / no 自动下单；A 股 PIT 禁 latest-wins 等；`DATA_NO_GO` 不变。
- Generator 不裁自己代码（铁律 #4）；被规则挡住≠被验证过；Generator 不得抽评测样本。
