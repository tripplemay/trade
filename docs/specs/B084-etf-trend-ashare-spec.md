# B084 — A股 ETF 时序趋势轮动（评审 P2）Spec

> 评审 §3.4 排序 3 / §5 P2。**工作量最小**（`global_etf_momentum` 改 A 股版）+ **数据地基已备**（复用 B082 A 股 ETF 管线）。
> 预研 `docs/research/next-batch-prep-etf-trend-ashare.md`。**first-look 低承诺优先**（同 B083 PEAD 节奏）：先证据一测（趋势胜率/夏普），
> 强 → 推荐建可配策略 + 生产模式；弱/震荡损耗大 → INCONCLUSIVE 归档。

## 0. 设计要点（焊死）

- **信号 = 时序动量/趋势**（每 ETF 自身 N 月动量>0 或 价>MA → 持有，否则退现金）。**非横截面行业轮动**（评审：A 股横截面行业动量弱）。
  参数（回看窗 / MA 长度）**先验定死禁扫参**（研报口径打折，B081/B083 教训）。
- **标的池**：A 股宽基（510300 沪深300 / 510500 中证500 / 588000 科创50）+ 红利低波 512890（与 B082 衔接）。上市时间决定窗口——**诚实标注**。
- **★核心坑（评审焊死）**：**2022 / 2024-02 型震荡切换期假信号损耗**——趋势策略震荡市反复止损。**必分窗口报换手/假信号损耗**，研报年化 18–24% 视样本内上限打折。
- **成本口径**：ETF **无印花税**（复用 B082 dividend-lowvol ETF 成本口径）。
- **引擎修真开关（B081）**：ETF 层多无手数/停牌/退市（流动、不退），开关照带（`price_limit_gating` ETF 极少一字板影响小；纯 ETF 持有可豁免多数）。

## 1. 复用清单

| 复用项 | 来源 | 用于 |
|---|---|---|
| 时序动量引擎骨架 | `trade/backtest/global_etf_momentum.py` | F001/F002 核心 |
| **A 股 ETF 数据管线** | **B082 F001**（akshare `fund_etf_hist_em` fetch 模式） | F001 数据（★最大复用） |
| ETF 成本口径（无印花税） | B082 F002 | F002 成本 |
| forward-return / 趋势胜率 / 夏普 first-look | B077/B083 first-look 模式 | F002 |
| 引擎修真开关 | B081 | 口径 |
| 去偏 / WF / CPCV / 卡片 / trial 登记 | B070/B080 | 验收 |

## 2. Feature 拆解（3：2 generator + 1 codex）

### F001 (g) — A 股宽基/红利 ETF 数据接入（复用 B082 管线扩标的）
- 复用 B082 `fund_etf_hist_em` fetch，扩到宽基（510300/510500/588000）+ 512890。真实 fetch 探针：覆盖/深度/复权/新鲜度落 `docs/test-reports/B084-F001-data-reality.md`（不可得/<3y → NO-GO 停批诚实）。
- bulk 研究快照（first-look，同 B083；日刷 wiring 推迟到策略批若 GO）。Gates 通用 + B082 F004 教训（若接 data_refresh 排 Tiingo 前）。

### F002 (g) — 时序趋势信号 + first-look（胜率/夏普/震荡损耗）
- 时序动量（先验窗，禁扫参）；trend-following 持有/退现金；**分窗口报 2022/2024-02 震荡期假信号损耗 + 换手**；
  full + WF 70/30 CAGR/Sharpe/MaxDD + 与买入持有基线 delta；报告 `docs/test-reports/B084-etf-trend-ic.md` + trial 登记（DSR N，B080 data-migration 模式）。
- **裁定**：趋势夏普显著 > 买入持有 + 震荡期损耗可控 → GO（推荐策略批）；否则 INCONCLUSIVE 归档（震荡损耗吃掉 edge 是常见合法结局）。

### F003 (codex) — 独立验收 + signoff
- Codex 独立：趋势数字从零重实现抽验（不 import 我方脚本）；参数无扫参（grep 单一 bundle）；**2022/2024-02 震荡损耗口径核实**（趋势策略最大陷阱=样本内挑窗）；覆盖/新鲜度探针复核；零回归。signoff `docs/test-reports/B084-etf-trend-signoff.md`；GO/INCONCLUSIVE 确认。

## 3. 验收（通用段）
- Gates：mypy / ruff / 单测（趋势信号 + 分窗口损耗 + 探针）/ 触 backend 则 backend 门禁 / CI 全绿。
- 诚实：first-look = 证据一测非可配资；震荡损耗 / 样本内上限打折显式披露；INCONCLUSIVE 合法。零回归（不触 cn_attack/dividend_lowvol/PEAD 产品码）。
