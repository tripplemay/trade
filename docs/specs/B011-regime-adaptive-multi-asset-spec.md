# Research Spec B011: 宏观状态自适应多资产组合 (Regime-Adaptive Multi-Asset Allocation)

## 1. 核心理念
结合文献库中最前沿的风险控制思想与机构实战的宏观切换（Regime Switching）模型，在现有的 Risk Parity (B010) MVP 基础上，增加非对称的防守能力与动态调仓宽容度。核心目的是在类似 2022 年的高通胀股债双杀或 2020 年的流动性枯竭期间，提供生存级护盾。

## 2. 策略组件与因子字典 (Factor Dictionary)

### 2.1 资产宇宙 (Universe)
- **风险核心 (Risk Core)**：`SPY`, `QQQ` (美股), `VEA`, `VWO` (非美)
- **稳定器 (Stabilizers)**：`IEF`, `TLT` (美债), `GLD`, `DBC` (黄金与商品)
- **防守池 (Defensive/Cash)**：`SGOV` (短债现金)

### 2.2 因子定义
- **快慢波动率 (Fast/Slow Volatility)**: `20-day` 年化波动率 vs `120-day` 年化波动率。
- **长趋势指标 (Long-term Trend)**: 资产价格是否大于 `200-day SMA`。
- **逆波动率权重 (Inverse Vol)**: $w_i = 1 / vol_i$。

## 3. 三重风控架构 (The Triple Shield)

### L1 防线 - 单资产趋势过滤 (Momentum-Gating)
仅在资产日收盘价 > `200日均线` 时，允许该资产满额参与权重分配。如果跌破该均线，该资产的风险权重被强制归零，释放的资金池流入 `SGOV`。

### L2 防线 - 风险平价自适应 (Volatility Targeting)
使用逆波动率加权。如果组合整体的估计波动率超过了目标波动率（如 `8%`），则执行缩放 `Exposure Scaling = 8% / Est_Vol`。

### L3 防线 - 组合级宏观拨片 (Regime Overriders)
当组合整体触发波动率跳升（VIX Spike）：
`Fast Vol (20d) > Slow Vol (120d) * 1.5`
并且大盘 `SPY` 跌破 `200日均线`，系统启动“**危机模式 (CRISIS REGIME)**”：强行将目标风险敞口砍半（Exposure 减半），将大量剩余资金归入短债防守。

## 4. 动态宽容度调仓 (Dynamic Rebalancing Bands)
为降低真实交易摩擦（如滑点和佣金），放弃固定的“每月初强制调仓”。引入“**阈值调仓（Tolerance Bands）**”：
- 仅当某一资产当前实际权重偏离目标权重绝对值大于 **3%**，或者触发了宏观状态切换（进入危机/熊市）时，才生成真实交易订单。

## 5. 伪代码实现参考 (Pseudocode)

```python
class MacroRegimeShield:
    def __init__(self, fast_vol=20, slow_vol=120, trend_ma=200):
        self.fast_vol = fast_vol
        self.slow_vol = slow_vol
        self.trend_ma = trend_ma
        
    def detect_regime(self, portfolio_returns, spy_price, spy_ma):
        fast_v = calc_vol(portfolio_returns, self.fast_vol)
        slow_v = calc_vol(portfolio_returns, self.slow_vol)
        
        if fast_v > slow_v * 1.5 and spy_price < spy_ma:
            return "CRISIS_REGIME"
        elif spy_price < spy_ma:
            return "BEAR_REGIME"
        else:
            return "NORMAL_REGIME"
            
    def apply_shield(self, target_weights, regime, asset_prices, asset_mas):
        shielded = {}
        if regime == "CRISIS_REGIME":
            # Exposure cut by half
            shielded = {k: v * 0.5 for k, v in target_weights.items()}
        elif regime == "BEAR_REGIME":
            # Individual momentum gating
            for k, v in target_weights.items():
                shielded[k] = 0.0 if asset_prices[k] < asset_mas[k] else v
        else:
            shielded = target_weights.copy()
            
        shielded["SGOV"] = 1.0 - sum(shielded.values() if v else 0 for v in shielded.values())
        return shielded
```

## 6. 测试与验收目标
- **回测基准**：静态 60/40 组合，以及 B010 基础版风险平价策略。
- **验收核心**：在 2022 年（通胀/股债双杀）与 2020 年（流动性危机）的回撤应显著低于基础版策略（如控制在 15% 以内）。周转率因动态宽容度而有所下降。