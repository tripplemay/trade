# B089 F001 — VIX tail-risk overlay(SPY + X% VIXY）→ 有效但有代价的尾部对冲（done）

> BL-B013-D2：静态 VIXY overlay 减尾部损失。**零策略/flagship 改动**：新研究模块 `trade/analysis/vix_overlay.py`（纯 numpy/pandas）。
> 数据：SPY + VIXY（akshare `stock_us_daily`/Sina, 绕 Eastmoney 限流），3894 日 2011–2026。overlay = (1−X) SPY + X VIXY，月度再平衡（先验 X=5%/10% 禁扫参）。

## 结果（可测客观, 两面诚实）

| 变体 | full CAGR | full MaxDD | 2020 covid MDD | 2022 bear MDD |
|---|---|---|---|---|
| pure SPY | 12.13% | −34.1% | −34.1% | −25.4% |
| +5% VIXY | 11.80% | −24.9% | −24.9% | −22.8% |
| **+10% VIXY** | **11.09%** | **−20.9%** | **−15.2%** | −20.3% |

## 结论（诚实两面, 与文献一致, 可测非主观 edge）

- **★tail-loss 减显著（尤其急跌）**：10% VIXY 把 **2020 covid 急跌 −34.1% → −15.2%（近腰斩）**，full MaxDD −34.1% → −20.9%。5% 亦有效（−34%→−25%）。
- **★negative carry 代价（对冲不免费, 焊死量化）**：full CAGR **12.13% → 11.80%（5%）→ 11.09%（10%）**——10% overlay 年化拖累 ~1.0%/yr（VIXY roll cost）。
- **★急跌 vs 慢熊差异**：2020 急跌对冲**极好**（VIXY 暴涨 +278%）；**2022 慢熊对冲弱**（−25.4%→−20.3%，VIXY 慢熊少暴涨）——VIXY 对冲的是**急跌 tail**非慢熊。
- **月度再平衡效率**：尽管 VIXY 长期巨亏，月度再平衡（涨后卖/跌后买）令 overlay carry 代价**温和**（~1%/yr）——比 buy-hold VIXY 高效。
- **净判断**：10% VIXY overlay = **有效急跌尾部对冲**（2020 −34%→−15%），代价 ~1%/yr CAGR + 慢熊帮助有限——**诚实两面, 非免费午餐**。真策略集成（叠 Master/cn_attack）留 follow-up。

## 验收：**done** — 4 单测(overlay 加权/月度再平衡/MaxDD/CAGR) pass + ruff + mypy clean + 零回归(不改策略/flagship/生产).
复现：`python -m scripts.research.b089_vix_overlay_demo`（fetch SPY+VIXY Sina + 对比）。
