# B065 — A股 策略数据地基（进攻模型数据前置）Spec

**批次定位：** A股 进攻模型(动量+质量)的**数据前置批**。把 A股 从「能 lookup 查」推进到「能喂策略回测」——三件数据工程:① A股 CAS 基本面接进**策略数据管道**;② A股 数据质量对齐(qfq 复权口径);③ 宽 point-in-time A股 universe(自建 top-N,避幸存者偏差)。**顺带解锁 hk_china 重测 Batch 2.5**(qfq 对齐是共享前置)。

**来源：** 2026-06-18 用户讨论确认 A股 进攻模型方向(B055 风格落 A股),拍板:**路线 A(动量+质量)+ 拆数据批→策略批 + 先 A股 + universe=自建 top-N(市值+成交额)**。这是 3 步路线图的第 ① 步。

**愿景路线图（记录，本批只做①）：** ① 数据批(本批 B065) → ② A股 动量+质量 进攻策略批(B055-A股,独立账户+独立回测+walk-forward) → ③ 港股扩 + 实盘 surface。

---

## 1. 目标与边界

**目标：** A股 真实基本面进 trade 策略数据管道(同 SEC US schema)+ qfq 数据质量交叉源对齐 + 宽 point-in-time A股 universe,让下一批的「动量+质量」引擎有可信数据可建。

**核心洞察(地基已半就位)：** trade 的 `fundamentals.csv` schema = `[report_date, ticker, fiscal_quarter, fiscal_quarter_end, roe, gross_margin, fcf_yield, debt_to_assets, pe, pb, ev_ebitda, earnings_yield]`,且 `us_quality_momentum.quality_score`(rank(roe)+rank(gross_margin)+rank(fcf_yield)−rank(debt_to_assets),按 `report_date<=cutoff` point-in-time 过滤)**已就绪**。本批把 A股 CAS 基本面按**同一 schema** 写进**同一 fundamentals.csv** → 现成质量因子直接对 A股 生效。

**红线边界（硬性）：**
- **数据先行,非策略承诺**：本批只建数据地基,**不建策略、不出推荐、不碰回测策略逻辑**(策略是下一批)。
- **research-safe / 不碰 live**：A股 数据只为研究/回测;hk_china 仍 proxy,Master/live 推荐零回归。
- **no-broker**：只 akshare/baostock,不接券商 SDK(safety banlist 守门,§26.2 exact import-root)。
- **§12.10.2 / §12.10.3**：akshare 在 workbench data_refresh 侧(非 trade);trade 引擎离线读 CSV;请求路径不 import trade;wheel 自包含。
- **US 零回归(铁律)**：fundamentals.csv 的 US 行(SEC EDGAR)+ prices CSV 的 US 行 + Master/策略/lookup 全不破。CN 行**追加**,不改 US 行(参 refresh.py 现有 `price_rows + cn_hk_rows` 模式)。
- **避幸存者偏差(B063 方法学硬坑)**：universe 成员 point-in-time(只用当时可得数据排名),fetch 取宽 superset 减少幸存者偏差,残余偏差诚实标注。
- **§23 端点须实跑(framework v0.9.45)**：akshare CAS 基本面/历史市值成交额函数走与价格不同的端点,实施前必须 VM 实跑验可达+shape,选已验者;不可达诚实降级。

**不做（下一批/延后）：** A股 动量+质量选股引擎、独立账户、独立回测、推荐/执行 surface(=策略批);港股选股 universe(港股已有 lookup,策略后扩);A股 交易规则(T+1/涨跌停/手数/ST,回测保真度,留策略批按需);领域因子(龙虎榜/北向,P3)。

---

## 2. 复用清单（核过源码）

| 复用资产 | 位置 | 本批用法 |
|---|---|---|
| fundamentals.csv schema + point-in-time 质量因子 | `trade/strategies/us_quality_momentum/factors.py`(`quality_score` L146、`_latest_fundamentals_row_per_ticker` L71 按 report_date 过滤)| CN CAS 基本面映射到**同 schema** → 质量因子直接复用 |
| data_refresh 双 CSV 写入 | `workbench_api/data_refresh/refresh.py`(prices `price_rows+cn_hk_rows` L272、fundamentals US-only loop L283-306、`FUNDAMENTALS_HEADER` L117)| CN 基本面行**追加**进 fundamentals.csv(US 行不动) |
| CN_HK_UNIVERSE(现 5 A股名硬编码) | `refresh.py` L82 | 扩展为**自建 top-N point-in-time** universe builder(替换硬编码小集) |
| B064 akshare CAS 基本面取数逻辑 | `workbench_api/symbols/cn_provider.py` / `fundamentals.py`(B064 lookup 层)| 取数逻辑参考,移植/适配到 data_refresh 历史季度拉取 |
| §8 数据质量工具 | `workbench_api/symbols/data_quality.py` + `scripts/test/ashare_quality_check.py`(B062/B063,26 universe cross-source)| qfq 对齐 + §8 质量闸复用 |
| CN provider qfq 价格 | `cn_provider.py`(akshare `stock_zh_a_hist` adjust=qfq)+ baostock fallback | qfq canonical 对齐基准 |
| §23 / 铁律 9 / §26.2 | framework v0.9.45 | 新 akshare 端点实跑 + banlist exact import-root |

**最新 alembic head：** `0026`（B064）→ 本批若需新表从 **0027** 起(基本面进 CSV 无需新表;universe 成员史若落库才需)。

---

## 3. Feature 拆解（4 features：3 generator + 1 codex）

### F001 — 宽 A股 流动 universe + point-in-time 自建成员（executor: generator）

**做什么：**
1. **§23 前置**：实跑验 akshare 能否取**历史**市值 + 成交额(用于 point-in-time 排名)——候选:`stock_zh_a_spot_em`(当前市值/成交,非历史)、总股本×历史收盘算历史市值、`stock_individual_info_em`(总股本)。取不到历史市值 → fallback:用历史成交额(price CSV volume×close)+ 期初总股本近似,诚实标注。
2. **point-in-time universe builder**：每个 rebalance 日按**当时可得**的 trailing 市值 + 成交额(如过去 N 日均额)排名取 **top-N(P1 建议 ~200-300)**;只用当时数据,无未来泄漏。
3. **fetch superset**：data_refresh 拉取集用**宽 superset**(如曾进过 top-N 的并集 / 当前 top-500 流动)减少幸存者偏差;残余偏差诚实文档。
4. **预算/时长感知**：扩 universe 后 data_refresh 拉取量 + 时长可接受(akshare 限速)。
5. **测试**：point-in-time 排名**无未来数据泄漏**(给定 as_of 只用 ≤as_of 数据)+ top-N 选取 + superset 构造 + 边角(数据缺/不足 N)。

**Acceptance（正面证据）：** universe builder 给定历史 as_of 产出当时 top-N(可验只用当时数据);fetch superset 覆盖;§12.10.2/§26.2 守门;无 US 回归。Gates：backend pytest/ruff/mypy CI-exact 0;改 trade/ 则本地 `mypy trade`(§19/B050)。

### F002 — A股 CAS 基本面接进 fundamentals.csv（同 schema，平行 SEC）（executor: generator）

**做什么：**
1. **§23 前置**：实跑验 akshare CAS **历史季度**财务函数可达 + shape——候选:`stock_financial_abstract`(财务摘要)、`stock_financial_analysis_indicator`(财务指标含 ROE/毛利率/负债率,历史季度)。确认能取**多季度历史**(point-in-time 需 report_date 序列)。
2. **映射 CAS → `FUNDAMENTALS_HEADER`**：roe / gross_margin / debt_to_assets 直接映射;pe / pb 用市值+收盘计算;fcf_yield / ev_ebitda / earnings_yield 能算则算、不能则诚实 null(质量因子 quality_score 只用 roe/gross_margin/fcf_yield/debt_to_assets,前三关键)。每季一行带 `report_date`(point-in-time)。
3. **写进同一 fundamentals.csv**：CN 行**追加**(US SEC 行不动,零回归;同 refresh.py CN prices 追加模式);CAS 口径诚实标注(source 列 / data_source)。
4. **§12.10.3 wheel 自包含**：akshare 仅在 workbench data_refresh 侧;trade 读 CSV 离线。
5. **测试**：CAS→schema 映射 + 历史季度 report_date 序列 + US 行不动(zero-regression assert)+ 缺字段 null 处理。

**Acceptance（正面证据，§29 实测）：** data_refresh 跑后 fundamentals.csv 含 A股 CN 行真值(如 600519.SH roe/gross_margin/debt_to_assets 非空,多季度 report_date);US 行逐行不变(zero-regression);`us_quality_momentum.quality_score` 能对含 A股 的 frame 算出排名(验质量因子对 A股 生效)。Gates 同 F001。

### F003 — A股 数据质量对齐(qfq) + §8 质量闸（executor: generator）

**做什么：**
1. **qfq 复权口径对齐**：B063 发现 akshare-baostock 交叉源偏差 2-60%(qfq 口径不一致)。定 **akshare qfq 为 canonical**(与 CN provider 价格一致),核 baostock 对齐方式(后复权 vs 前复权口径),对齐到 **cross-source <0.5%**(或诚实记录不可对齐的口径差 + 选定 canonical)。
2. **§8 质量闸**：复用 `ashare_quality_check` / `data_quality.py`,对宽 universe 跑深度(全历史)/覆盖/cross-source/缺口检查,产质量报告。
3. **解锁 hk_china 重测**：qfq 对齐同时覆盖 hk_china 26 universe → Batch 2.5 重测的数据前置就绪(重测只剩 200D warmup + 重跑)。
4. **测试**：qfq 对齐逻辑 + cross-source 阈值检查 + §8 质量指标计算。

**Acceptance（正面证据，§29 实测）：** 对 A股 样本(如 600519.SH + 宽 universe 抽样)akshare-baostock cross-source **<0.5%**(或诚实记录口径差 + canonical 选定理由);§8 深度/覆盖达标报告;hk_china 26 universe qfq 对齐确认。Gates 同 F001。

### F004 — Codex L2 真机验收 + signoff（executor: codex）

**做什么（真数据批次——signoff 必含「实测证据」硬段,evaluator §29）：**
- L1 全门禁(backend pytest+mypy CI-exact workbench_api+tests+ruff;trade pytest+`mypy trade`;frontend 若动)。
- **L2 真机实测(VM,贴真返回数字)：**
  - F001:universe builder 给定历史 as_of 产 point-in-time top-N,**无未来泄漏**(抽查一个历史日只含当时数据);fetch superset 覆盖。
  - F002:data_refresh 真跑 → fundamentals.csv 含 A股 真值(600519.SH 等 roe/gross_margin/debt_to_assets 真数字 + 多季 report_date);**US 行零回归**(pre/post 逐行对比)。
  - F003:akshare-baostock cross-source **<0.5%** 实测数字(或诚实口径差结论);§8 质量报告真指标;hk_china qfq 对齐确认。
  - US/Master/lookup 零回归;recent-errors=0;HEAD≡prod。
- **边界 adversarial**:no-broker、research-safe(数据未进任何 live/推荐路径)、§12.10.2 守门。
- signoff `docs/test-reports/B065-...-signoff-*.md`,**实测证据硬段逐条贴真观测**(无真值=不得 done)。

---

## 4. 状态流转 + 风险

- 混合批次：`planning → building(F001→F002→F003)→ verifying(F004 Codex)→ done`。
- **风险与缓解：**
  - **akshare 历史市值/成交额可达性**(F001 最大未知,§23)→ 实跑验,不可达 fallback 成交额近似 + 诚实标注。
  - **akshare CAS 历史季度财务可达性**(F002,§23)→ 实跑验能否取多季历史;只取到当前快照则 point-in-time 受限,诚实标注 + 缩范围。
  - **qfq 口径不可完全对齐**(F003)→ 选定 canonical + 诚实记录残余口径差,不强行造 <0.5% 假象(B063 诚实精神)。
  - **幸存者偏差**→ fetch superset + point-in-time 排名 + 残余偏差文档(决策报告可信前提)。
  - akshare 非官方源失效 → 多源 fallback(akshare↔baostock)+ 优雅失败。

## 5. 不变量清单（Codex 回归核）

1. fundamentals.csv 的 US SEC 行零回归(逐行不变);prices CSV US 行不破。
2. Master/策略/回测/推荐/lookup/账户路径零回归(本批只加数据,不碰策略/live)。
3. §12.10.2 请求路径无 trade;§12.10.3 wheel 自包含;§26.2 banlist exact import-root。
4. no-broker / research-safe(数据未进 live)。
5. hk_china 仍 proxy(本批不激活、不碰 live 推荐)。
