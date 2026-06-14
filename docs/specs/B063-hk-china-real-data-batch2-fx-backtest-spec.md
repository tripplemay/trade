# B063 — hk_china 真数据 Batch 2：FX 层 + real-data 策略 + 回测对比（决策点）

> **批次类型：** 混合批次（3 generator + 1 codex）。**hk_china 换真数据工程第 2 批 = 决策点**（research-safe）。
> **状态：** planning → building（2026-06-14；B062 数据地基 done 后）。
> **关键定位：** 本批**产出"real-data hk_china vs proxy"回测对比报告 + 建议**——它**闸控 Batch 3（是否上真金 live Master）**。研究态，不碰 live 推荐。

---

## 1. 本批目标与整体定位

```
✅ Batch 1 = B062（数据地基：三市场 lookup + A股港股进 CSV + §8 质量工具）
🔨 Batch 2 = B063（本批）= FX 层 + real-data hk_china 策略 + ★回测对比 → 决策报告
Batch 3（待 B063 报告favorable + 用户确认）= 激活进 live Master（★真金，S3 Master 零回归硬闸）
```

本批回答唯一问题：**"用真 A股+港股替换 US-listed ETF proxy，回测上到底更好吗？值这堆 FX/管道/集中度复杂度吗？"** 输出诚实对比报告，**不预设结论**（很可能 = "没明显更好，停在 proxy"，那也是有效结论，地基不白费）。

---

## 2. ★方法论硬坑：不许用"今天的赢家"回测（决定报告可不可信）

候选大盘股（腾讯/阿里/美团/小米/茅台/五粮液/宁德）是**今天的 mega-cap**。直接拿这 7 个回测 5 年 = **幸存者/事后选择偏差**——等于"假装 5 年前就知道该买这些"，会让 real-data 版**虚高、误导成'值得做'**。proxy ETF（MCHI/FXI/KWEB/ASHR）是规则化指数、**无此偏差**。

**规约（本批硬约束）：** real-data 策略**必须 point-in-time 规则选股**——从一个**较宽的流动性 universe**（~20-30 个 HK+A 大盘，B062 管道扩量拉取）里，**按 momentum+quality 规则、只用当时可得数据**选 top N（复用 hk_china 策略逻辑）；**不许 hand-pick 固定 7 个赢家回测**。残余偏差（宽 universe 本身的选择）报告须诚实标注。**若做不到 point-in-time → 报告必须标'结果有事后偏差、偏乐观、不足以作 Batch 3 go 依据'。**

## 3. ★第二诚实点：对比不止"数据源"，还混了"集中度"

proxy = 分散 ETF；real-data = 集中个股（top N）。两者**风险画像本就不同**。回测对比须**诚实区分**"差异来自数据源/真实标的"还是"来自集中度"——否则把"集中赌大盘股"的高收益误记为"真数据更好"。

---

## 3.5 范围

**做（research-safe）：** S2 §8 质量真跑（入口闸）；FX 层（FRED 历史汇率）；real-data hk_china 策略（point-in-time 规则选股）；回测对比 real vs proxy（USD 口径）；对比报告 + Batch 3 建议。
**不做（Batch 3/延后）：** 激活 live Master / 改 live 推荐 / live 多币种 NAV 聚合（本批 FX 仅供回测 USD 换算）/ 交易规则(T+1/涨跌停)。
**边界：** trade 仍离线（FRED/akshare 在 workbench data_refresh，trade 读 CSV）/ no-broker / §12.10.2 / mypy CI-exact(§19) / **本批不碰 live 推荐**（hk_china 仍 proxy）。

---

## 4. Feature 分解（3 generator + 1 codex）

| id | executor | 标题 |
|---|---|---|
| F001 | generator | FX 层：FRED CNY/USD(DEXCHUS)+HKD/USD(DEXHKUS) 历史汇率进管道（复用 fred_loader，日历对齐 forward-fill）|
| F002 | generator | real-data hk_china 策略：宽 universe point-in-time 规则选股（复用 hk_china 逻辑）+ USD 换算 |
| F003 | generator | 回测对比 harness：proxy-hk_china vs real-hk_china（USD 口径，复用 trade/backtest）+ 偏差感知指标 |
| F004 | codex | ★S2 §8 质量闸(真数据 VM) + 跑对比回测 + 对比报告(诚实偏差) + Batch 3 建议 + signoff |

### F001 — FX 层（generator）
1. 复用 `fred_loader` 拉 **DEXCHUS(人民币/美元)+DEXHKUS(港币/美元)** 日度历史（FRED 央行权威，已集成，含数十年历史）。
2. 进 workbench data_refresh 写 FX 数据（trade 读，离线）；交易日历对齐 + 缺日 forward-fill（FRED 周末/假期空值）。
3. **仅供回测 USD 换算**（live 多币种 NAV 是 Batch 3）。
4. 测试：FX 拉取+对齐+forward-fill+缺值处理。Gates：backend pytest/ruff/mypy CI-exact 0。

### F002 — real-data hk_china 策略（generator）
1. **宽 universe**（~20-30 流动 HK+A 大盘，B062 管道扩量拉取真价格）。
2. **point-in-time 规则选股**（§2 硬坑）：按 momentum+quality（复用 `trade/backtest/hk_china.py` 逻辑）只用当时可得数据选 top N；**不 hand-pick**。
3. USD 换算（用 F001 FX 把 CN/HK 价格/收益转 USD，与 USD proxy 同口径比）。
4. 测试：point-in-time 选股(无未来数据泄漏)+USD 换算+复用 hk_china 逻辑。Gates 同 F001。依赖 F001。

### F003 — 回测对比 harness（generator）
1. 跑两版同期同口径(USD)：(a) proxy-hk_china(MCHI/FXI/KWEB/ASHR) (b) real-hk_china(F002)。
2. 对比指标：CAGR/Sharpe/MaxDD/vol/turnover/换手成本；**偏差感知**（标注集中度差异、universe 选择）。复用 trade/backtest + B050。
3. 测试：对比 harness 双版可跑+指标+同口径。Gates 同 F001。依赖 F002。

### F004 — Codex 闸 + 对比报告 + signoff（codex）
L1 全门禁。L2 真 VM：① ★**S2 §8 质量闸**(跑 B062 runner 真数据)：候选 universe 全历史深度/复权/akshare-baostock 交叉源<0.5%/HK 源——**不达标→报告 = 数据未就绪、不进 Batch 3、重估**(像 B060 NO-GO)；② **跑对比回测**(proxy vs real-data，USD 同口径)；③ **对比报告**(docs/test-reports/)：指标对比 + ★**诚实偏差分析**(point-in-time 是否真做到/残余选择偏差/集中度 vs 数据源归因) + **Batch 3 建议**(值得上真金 go / 不值 no-go / 条件性)；④ **边界**：trade 离线、no-broker、研究态不碰 live 推荐、US/Master 不破；⑤ recent-errors=0+HEAD≡main+演练自清。Signoff（§S2 质量实测 + §回测对比指标 + §★偏差诚实分析 + §Batch 3 建议 + §不破 + §Ops）。

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| ★回测事后偏差(hand-pick 赢家)→误导'值得做' | §2 硬坑：point-in-time 规则选股 + 宽 universe；做不到则报告标'偏乐观不足为 go 依据' |
| 把集中度收益误记为'数据源更好' | §3：对比报告归因区分集中度 vs 数据源 |
| S2 数据质量不达标 | F004 S2 闸先行；不达标=数据未就绪、停、不进 Batch 3 |
| FX 缺值/对齐错 | F001 forward-fill+日历对齐+测试 |
| scope 蔓延成激活真金 | 本批研究态产报告；激活是 Batch 3 闸控于本报告+S3 |

## 6. Core Acceptance（一句话）

S2 §8 数据质量真数据验实(达标否)；FX(FRED 历史汇率)+real-data hk_china 策略(★point-in-time 规则选股避事后偏差)+回测对比 proxy vs real-data(USD 同口径)产出**诚实对比报告**（含偏差/集中度归因 + Batch 3 go/no-go 建议）；**且研究态不碰 live 推荐、trade 离线、US/Master 不破**——本报告是 Batch 3 是否上真金的决策依据，不预设结论。
