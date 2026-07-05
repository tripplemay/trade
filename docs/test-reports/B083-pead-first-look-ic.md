# B083 F002 — PEAD 业绩预告 forward-return rank-IC first-look → **INCONCLUSIVE**

> first-look 证据一测（非可配资）。盈余惊喜 = (预测数值 − 上年同期值)/|上年同期值|（先验口径，禁扫参）；
> 事件日 = 公告日（PIT）；进场 = 公告日 **T+1**（前视 rigor，单测锁 entry > announce）；
> rank-IC = spearman(surprise, fwd_ret) via Pearson-of-ranks（scipy-free）。

## 结果（B070 去偏 PIT 宇宙 ∩ 业绩预告事件，8,235 事件定价）

| horizon | IC (all) | IC (可执行=剔 entry 触板) | n |
|---|---|---|---|
| N1 | +0.024 | **+0.021** | 8,172 |
| N5 | −0.020 | −0.021 | 8,172 |
| N10 | −0.077 | **−0.076** | 8,172 |
| N20 | −0.057 | −0.057 | 8,172 |

- entry 一字触板占比仅 **0.8%**（预告是软信号，不像正式财报大惊喜次日常一字板）→ 可执行 IC ≈ 纸面 IC。

## 裁定：**INCONCLUSIVE**（此 naive 口径/宇宙**无正向 PEAD 漂移**）

- **非 drift，是弱 pop + reversal**：N1 弱正(+0.02, <阈值 0.03)后 N5–N20 转负(-0.02..-0.077)。
  高 预告-surprise 名次日小涨后**跑输**——**反转**，非 PEAD 式持续漂移。跨 horizon **不同号 + 不单调** → 不满足 GO 门槛。

## ★诚实 caveats（决定 INCONCLUSIVE 非"PEAD 死"——避免 B081 式过度归因）

1. **宇宙偏差（大）**：B070 = cn_attack 动量/质量宇宙(~1152 名, 事件覆盖仅 23%)——**大盘、定价更有效**。
   PEAD/欠反应经典最强在**小盘**（评审 §3.4 小盘拥挤但欠反应）。本宇宙**系统性低估**了 PEAD——需全 A 宽宇宙重测。
2. **预告 ≠ 实际财报（口径）**：用的是**业绩预告**(forecast)惊喜，非**实际财报/快报**惊喜。经典 PEAD 围绕**实际公告**；
   预告是**预披露**，surprise 在预告日已部分定价 → T+1 进场吃不到主漂移。**快报 `stock_yjkb_em`(实际)口径是更正确的下一步**。
3. **SUE 分母**：用去年同期作基准(zero-extra-data)；分析师**一致预期**(`stock_profit_forecast_em`)是更标准的 SUE 分母，覆盖够时应对照。

## 结论（供 planner / evaluator）

- **本 naive 口径（预告 surprise × B070 宇宙）INCONCLUSIVE**：无正向 drift，弱反转，不推荐直接建策略。
- **不等于 "PEAD 在 A 股无效"**：三条 caveat 各指向 edge 被系统性低估的机制（大盘宇宙/预告非实际/SUE 分母）。
- **建议 backlog follow-up（若续）**：全 A 宽宇宙 prices + **实际财报/快报**惊喜 + 分析师一致预期 SUE，重跑 IC 再判 GO/NO-GO。
- trial_registry 登记本 first-look（config = 预告-surprise/B070/naive, verdict=INCONCLUSIVE）作 DSR N（诚实计入已试配置）。

## 复现
`scripts/research/b083_pead_fetch.py`（events）→ `scripts/research/b083_pead_ic.py`（IC）。前视单测 `tests/unit/test_b083_pead_ic.py`。
