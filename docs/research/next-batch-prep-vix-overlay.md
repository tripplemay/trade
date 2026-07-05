# Next-batch prep — VIX tail-risk overlay (BL-B013-D2, feasibility confirmed)

> **状态：DRAFT / 立项前勘查（B088 verifying 期间）。** backlog `BL-B013-D2`（low, Phase 4 长尾）。**判断=可测机械**（tail-loss/carry 客观），
> 同 B088 vol-targeting 一样是安全自主 win（非 subtle-edge）。**数据 gate 已解除**（下方实测）。

## 可行性：**GO（数据 + 前提均实测确认）**

- **数据可得**（akshare `stock_us_daily` Sina US, 绕 Eastmoney 限流）：**SPY 6411 行 2001–2026 / VIXY 3896 行 2011–2026**，覆盖 2020+2022 stress window。
- **★前提实测确认**：2020 covid 崩盘 **SPY −34% / VIXY +278%**——VIXY 对股灾的负相关对冲**极显著**（这正是 overlay 的价值来源）。

## 设计（tight, 可测客观, 避 subtle-edge）

- **overlay = SPY + 静态 X% VIXY**（先验 X=5%/10%，禁扫参），月度再平衡回到目标权重。baseline = 纯 SPY。
- **可测指标（客观非主观 edge）**：
  1. **tail-loss 减**：2020/2022 stress window 的 max drawdown（overlay vs 纯 SPY）——应显著减。
  2. **negative carry 代价**：全期 CAGR（overlay vs 纯 SPY）——VIXY 长期负 carry 拖累，**必量化诚实披露**（对冲不免费）。
  3. 综合：tail-loss 减是否值 carry 代价（无免费午餐，诚实两面）。
- **★诚实焊死**：VIXY 长期巨亏（roll cost），overlay 必**牺牲长期收益换尾部保护**——报告须显式量化两面，不吹"对冲免费"。
- **零回归**：新研究模块 `trade/analysis/vix_overlay.py` + 研究脚本，**不碰策略/flagship/生产**；SPY+VIXY 走 akshare Sina（同 B084/B086 fallback 思路，US 用 stock_us_daily）。

## Feature 拆解（2：1g + 1c）
- **F001 (g)**：fetch SPY+VIXY（Sina）→ overlay 构造（静态 X% VIXY 月度再平衡）→ tail-loss（2020/2022 MaxDD）+ negative carry（全期 CAGR）对比 vs 纯 SPY + 单测（overlay 权重/再平衡机械）+ 报告。零回归。
- **F002 (codex)**：独立验收（overlay 数字重算/tail-loss 减真/carry 代价诚实量化/无扫参/零回归）。

## 复用
`scripts/research/ashare_market_source` fallback 思路（US 用 `stock_us_daily`）+ B088 vol_targeting 的可测对比 + us_quality metrics（MaxDD/CAGR）。**scope 中等**（fetch + 静态 overlay + 2 指标对比）。
