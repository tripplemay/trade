# B109 — Tushare PIT 数据层 v0 + 巨潮对拍审计（规格）

> 批次类型：混合（2 generator + 1 codex）
> 上游：`docs/audits/tushare-three-question-probe-2026-07-20.md`（三问探针实测）
> 更上游：`docs/audits/ashare-pure-ep-data-foundation-implementation-handoff-2026-07-13.md`
> 前置：B108（转向收尾，F003 superseded）
> 当前裁定：A 股纯 E/P 仍为 `DATA_NO_GO`，**本批次不改变该裁定**

## 1. 背景

三问探针（¥500，15 分钟）改变了数据路线的判断：

| 问题 | 实测 |
|---|---|
| 归母净利润真实修订率 | **0.712%**（7 个年报期、38,207 股票-期、272 个被改） |
| `update_flag` vintage 能力 | **有**（`flag=0` 保留首次披露值，`flag=1` 的 `f_ann_date` 标出修正何时可知），**但 `flag=0` 保留率随期间波动 10.5%–95.4%** |
| `total_mv` 身份校验 | **100.000%** 在 0.5% 内，中位误差 0.00000% |
| 退市名 | 338 只（263 只在 2013 年后） |

**两个结论：**

1. 上游 handoff 报告用「90.83% 记录在 120 天后仍更新」论证的**重装三时钟 bitemporal 底座，
   其必要性未被实测支持**——那个指标衡量的是记录被 touch 的时间，不是数值被改的比例。
   实测 0.712%。但修订**稀有不等于可忽略**：61% 幅度 >1%，22% >10%。
2. **自建 PDF parser 就「获取归母净利润」而言性价比输了**（B108 三轮后年报仅 1/34）。
   巨潮的正确角色是 **truth anchor**（上游报告 §8.1 给它定的 P0 定位），不是 bulk 来源。

**用户 2026-07-20 裁定：** (1) B108 转向审计工具 ✅ (2) 追加探针 ✅ (3) 许可证**允许**内部长期归档。
第 (3) 条解锁了上游报告 §10 的 snapshot / hydrate / 离线复现契约的合规基础。

## 2. 目标

建立**能回答 as-of 问题的 Tushare PIT 数据层 v0**，并用巨潮原文对它抽样验真。
不建全量底座，不算 E/P，不出收益。

## 3. 硬约束（H）

- **H1 分子的 as-of 语义只用两个字段**：`f_ann_date <= formation_date` 中取 `f_ann_date` 最大的一条。
  不得用 `ann_date` 代替（`ann_date` 是原始公告日，修正行的 `ann_date` 不变）。
- **H2 分母冻结为 `CN_SECURITY_TOTAL_MV`**：`daily_basic.total_mv`，且必须与
  `close × total_share` 同 basis 复算。**禁止流通市值**（上游禁令 #6）、**禁止当前股本×历史价**（#7）。
  单位为**万元**，schema 层必须显式转 CNY。
- **H3 宇宙必须含退市名**：`stock_basic` 拉全 `L/D/P`，禁止只拉 `L`（上游禁令 #11）。
- **H4 覆盖不足必须结构化呈现**：沿用 B108 的 failure code 风格，禁止静默 dropna
  （上游报告 §13；B108 F002 的 no-silent-caps 教训）。
- **H5 research-only**：不改生产代码、不动策略默认值、不出 E/P / 收益，不改 readiness flag。
- **H6 凭据**：token 只从 `.env.local` 读，禁止硬编码、禁止入仓、禁止出现在日志与报告里。

## 4. 功能列表（`features.json` 权威）

### F001（generator）追加 vintage 探针

回答探针报告 §3.1 的未决问题——**这条的答案决定 F002 的 resolver 设计**：

1. `flag=0` 行的保留率为何随期间波动 10.5%–95.4%？是否与数据入库时间相关？
2. 季报 / 半年报（`report_type` 全集）的修订率与 vintage 保留情况？（探针只测了年报）
3. 量化：**按形成日可重建的 as-filed 覆盖率**——即任意历史月末，有多少比例的股票能拿到
   「当时可见的那一版」归母净利润。这是 PIT 分子能否落地的直接指标。

交付：测量报告 + 对 F002 的设计裁定（重装 vs 轻量）。**不实现 resolver。**

### F002（generator）Tushare PIT 数据层 v0

1. **分子**：`income_vip` 拉取 + 规范化（Decimal CNY，保留原始值/单位）+ **as-of resolver**
   （按 H1 的两字段语义），带结构化失败码。
2. **分母**：`daily_basic` 的 `total_mv` + `total_share`，月末取值，**身份复算**
   `close × total_share`，误差 >0.5% 的行隔离并报告。**替换 B076 的流通市值反推**。
3. **宇宙**：`stock_basic` 全状态 + `namechange`，含退市名。
4. **审计工具**：把 B108 的 `scripts/research/ashare_ep/` 多源交叉验证框架改造为
   **Tushare 值 vs 巨潮原文的抽样对拍器**——复用其 seed 化分层抽样、PDF 冻结、
   结构化 failure code；巨潮作 truth anchor，Tushare 作被审计方。

### F003（codex）独立验收 + 对拍审计 + signoff

1. 用 F002 的审计工具，自选 seed 抽 **≥60 份**巨潮原文，与 Tushare 的
   `n_income_attr_p` 逐份对拍，**人工裁定不一致项**（是 Tushare 错、巨潮 parser 错，还是口径差异）。
2. **as-of 正确性**：构造若干「修订前 / 修订后」形成日，验证 resolver 返回的是**当时可见的那一版**。
   注入未来修订后，旧形成日的结果必须不变（上游报告 §12「修订不变性」）。
3. **分母身份校验**：独立复算 `total_mv` vs `close × total_share`，报告误差分布。
4. 边界：H1/H2/H3/H5/H6 逐条审查（特别是 token 未入仓、未出现在任何产物里）。
5. 输出 `docs/test-reports/B109-tushare-pit-foundation-signoff-YYYY-MM-DD.md`。

## 5. 验收门槛

| 门 | 条件 |
|---|---|
| **G-A 对拍一致性** | Tushare 与巨潮原文的归母净利润在 ≥60 份样本上一致率 **≥99%**；不一致项 100% 人工裁定归因 |
| **G-B as-of 正确性** | 修订前后形成日各自返回正确版本；注入未来修订后旧形成日结果**逐字节不变** |
| **G-C 分母身份** | `total_mv` vs `close × total_share` 误差 ≤0.5% 的比例 **≥99%**，>5% 的行全部隔离 |
| **G-D 覆盖披露** | 逐月/逐层输出覆盖漏斗，`flag=0` 保留造成的 as-filed 缺口显式量化，不得静默 |

**coverage 只报告不设门**（沿用 B108 的教训：覆盖率低只是少拿数据，正确性错才污染研究）。

## 6. 本批次明确不做

- 不建上游报告 Phase B-G 的全量底座（raw object store、filing/fact 双层版本、公司行动闭环等）
- 不计算 E/P、IC、收益、财富曲线
- 不改变 `DATA_NO_GO` 与三个 readiness flag
- 不解决 `stock_st` 2013-2015 缺口（已知，与本批次无关）
- 不继续投入 B108 的 PDF 覆盖率（`S2 内部多行不一致` 等已知缺陷保持原样，
  巨潮此后只作 truth anchor，抽样使用，不需要高覆盖）

## 7. 从 B108 带过来的纪律（硬性）

1. **最终测量必须在全新 seed 的 holdout 上做。** B108 两轮都出现「在已看过的语料上调参」。
2. **Generator 不得抽取最终评测样本**（B108 H3）。
3. **无法执行的路径必须显式标注为未验证。** B108 E01：联网路径因规则禁止而零执行，却被标了 done。
   **被规则挡住不等于被验证过。**
4. **每一轮修复都可能引入同类新缺陷**（B108 fix1 把 ×10⁴ 修成 ×10⁻³，fix2 放大已知冲突）。
   跨模块相互作用只有独立 holdout + 对拍旧实现才暴露。
