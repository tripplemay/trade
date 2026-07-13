# A 股独立宽基纯 E/P 数据地基实施交接报告（2026-07-13）

> 文档类型：策略研究到数据工程的实施交接，不是正式 batch spec
> 面向角色：Planner / Generator / 后续 Evaluator
> 资金口径：人民币 2,100,000 元，收益优先，现金纯多头
> 当前裁定：`DATA_NO_GO`
> 当前就绪标志：`ep_signal_data_ready=false`、`ep_execution_data_ready=false`、
> `cny_2_1m_portfolio_backtest_allowed=false`

## 1. 执行摘要

下一条值得建设的数据路线是**独立、宽基、月频的 A 股纯 E/P**，不是继续修改旧复合价值策略，
也不是给现有 `fundamentals.csv` 增加一列。理论上的信号定义很短：

```text
E/P(i, t) = PIT_TTM_归属于母公司所有者的净利润(i, t)
            / 月末总市值(i, t)
```

真正耗时的是证明分子和分母在历史形成日当时确实可见，并且可以在任意 fresh clone 上重放。
开发必须新建一套**追加式、三时钟、可追溯到公告原文**的数据底座：经济时间描述事实属于
哪个期间，市场可知时间和系统时间共同构成双时间版本模型。当前仓库已有数据只能复用部分下载、
月末取值、哈希和 as-of 机制，不能直接作为纯 E/P 真值。

建议开发按以下顺序推进：

1. 冻结 schema、交易日历和证券永久 ID，建立不可变原始对象归档。
2. 用至少 200 份双人标注公告和 20 条更正链验收候选供应商，不先做全市场昂贵回填。
3. 建立公告版本、财务事实版本和统一 as-of resolver，再计算 PIT TTM。
4. 接入历史总股本、总市值、原始行情、行业、交易状态和公司行动。
5. 生成 2013 年至今逐月宽基 E/P 面板及完整 lineage。
6. 通过覆盖、准确率、修订不变性和 fresh-clone 复现门后，才允许进入信号收益研究。

**最重要的工程裁定：**不得在现有 latest-wins 基本面文件上演进。需要独立的新数据域；旧数据
只能做交叉核验或架构 pilot。

## 2. 本批冻结的研究口径

### 2.1 目标宇宙

- 范围：上海、深圳交易所全部历史普通 A 股，包含后来退市、吸收合并、改名、改代码的证券。
- 起点：信号面板固定从 2013-01 的最后一个沪深共同交易日开始，不得因数据不足向后滑动；财务
  事实从 2011-01-01 起回取，给首批 TTM 留出 warm-up；行情、股本和公司行动从 2012-01-01
  起回取，给收益与 ADV60 留出 warm-up。
- 暂不纳入：北京证券交易所、B 股、基金、ETF、债券、优先股、存托凭证。
- 不因 ST、停牌、亏损、负 E/P 或后来退市而从原始数据层删除；这些状态必须作为 PIT 字段保留，
  由后续研究协议决定是否过滤。
- 新股四个单季不足时保留在母体并标记 `NON_CONTIGUOUS_TTM`，不得年化、不静默删除。

这是一条**宽基纯 E/P**路线。此前红利低波研究所需的 H30269 历史成分和权重，不是本项目的
前置依赖；也不得用 H30269 当前成分替代宽基历史宇宙。

### 2.2 形成时点

- `formation_session`：每个自然月最后一个沪深共同开市日，收盘后形成信号。
- v1 分母冻结为 `market_cap_basis=CN_SECURITY_TOTAL_MV`：供应商明确文档化的证券级 A 股
  `total_mv`，且必须与该 A 股 `raw_close * PIT_total_share` 同 basis 复算。不得在实现中切换为
  流通市值或各股份类别市值求和。
- A+H、A+B 等标记 `multi_share_class=true`，保留供应商 `total_share_scope`；正式研究必须额外
  报告排除多股类后的敏感性，但 v1 主值仍使用上述 `CN_SECURITY_TOTAL_MV`。
- 原始收盘价用于市值，复权价只供未来收益计算。
- 财报知识截止：只有 `available_session <= formation_session` 的已验收财务事实可以进入分子。
- v1 保守规则：公告只有日期或即使有时分秒，都统一在公告日后的第一个沪深交易日才可用。
- 下单、成交、费用、整手和流动性约束属于后续组合协议，不得反向改变财务事实。

不能用 `pandas.BusinessDay` 推导公告可用日。周末、法定节假日、临时休市和沪深日历差异必须由
中国交易所日历显式解析。

### 2.3 财务分子

- 唯一主概念：合并报表“归属于母公司所有者/上市公司股东的净利润”。
- 单位：统一为 `Decimal` CNY，同时保留原始字符串、原始单位和原始币种。
- 口径：最近四个在同一知识截止日可见、连续、均为合并报表、使用同一 fiscal calendar 且累计
  期间可比的单季值之和。正常收购导致的合并范围经济变化不是自动排除理由。
- 亏损和零利润是合法值；缺失不是零。
- 不使用 EPS、PE 的倒数、扣非净利润、预测利润或母公司单体报表替代。

### 2.4 本数据批不做什么

- 不决定最终持仓数、行业中性方法、换手约束或再平衡成交算法。
- 不计算 IC、分组收益、CAGR、Sharpe、最大回撤或 210 万元财富曲线。
- 不改变任何生产策略默认值，不接券商，不自动下单。
- 不把架构 pilot 的成功解释为策略收益成功。

## 3. 为什么现有数据不能直接扩展

| 现有资产 | 可复用内容 | 不能作为纯 E/P 真值的原因 |
|---|---|---|
| B068 `fundamentals.csv` | CSV loader、字段校验思路 | `report_date` 是法定截止日；`earnings_yield` 是累计 EPS/附近价格；没有真实公告版本、归母净利润或总市值 |
| Eastmoney `raw_reports.csv.gz` | 公告日覆盖诊断、字段名称、parser QA 对照 | 每个证券-报告期只有当前历史值，后续修订覆盖旧值；不能把当前值回填到首次公告日 |
| B070 PIT 宽基并集 | 历史成员切片、退市路径、as-of loader | 仅沪深 300/中证 500/上证 50 季度并集，不是全部 A 股；`market_cap` 等列是 0 占位 |
| B070 日线 | 1,310 个历史标的的抓取、停牌路径处理 | 仅 2018 年起，`close==adj_close`，缺原始/复权分离、总股本、总市值、涨跌停和公司行动闭环 |
| B076 市值 | 月末 downsample、on-or-before 查询和覆盖报告 | 由原始价、成交量、换手率反推的是**流通市值**，不能作全公司归母利润的分母 |
| B065 当前行情 | 当前幸存证券交叉检查 | 不是历史总股本/总市值真值，缺退出证券 |
| 巨潮 50 份 PDF pilot | 公告 ID、时间、URL、哈希、PDF 防护与原始档案流程 | 自动抽取只有 25/38，即 65.789% 在 0.5% 误差内，当前 parser 为 `NO_GO` |

仓库中已有两条直接证据：

- [`scripts/backfill_fundamentals.py`](../../scripts/backfill_fundamentals.py#L205) 以
  `(ticker, fiscal_quarter)` 去重并让“latest computation wins”，会销毁历史版本。
- [`scripts/research/b076_fetch_pit_marketcap.py`](../../scripts/research/b076_fetch_pit_marketcap.py#L83)
  通过 `close * volume * 100 / turn` 计算流通市值，语义不等于总市值。

现有审计还测得：B068 与 B070 的历史成员逐期可见覆盖仅 20.75% 至 31.75%；Eastmoney 当前
历史快照中，90.83% 的记录在公告 120 天以后仍有更新时间，更新时间中位数约 365 天。具体证据见
[`ashare-dividend-ep-data-readiness-2026-07-12.md`](ashare-dividend-ep-data-readiness-2026-07-12.md)
和 [`ashare-as-filed-data-pilot-2026-07-12.md`](ashare-as-filed-data-pilot-2026-07-12.md)。

因此，新实现不得 import 这些文件作为正式分子或分母；它们只能用于 adapter 参考、覆盖对照、
异常抽样和 Phase-1 架构 pilot。

## 4. 必须准备的八类数据

### 4.1 证券主数据与身份历史

目标是摆脱 ticker 作为永久主键。至少需要：

| 字段 | 说明 |
|---|---|
| `security_id` | 永久证券 ID；代码变化后不变 |
| `issuer_id` | 永久上市公司/发行人 ID；支持一发行人多证券 |
| `ticker`、`exchange`、`board`、`share_class` | 带有效起止日的标识历史 |
| `name`、`name_effective_from/to` | 证券简称历史，用于 ST 和公告映射复核 |
| `list_date`、`delist_date`、`delist_reason` | 上市、退市和退出原因 |
| `identifier_known_from_session` | 当时何时可知，防止用今天的映射回填 |
| `predecessor_id`、`successor_id` | 代码迁移、吸收合并或证券替换关系 |

验收时必须覆盖：代码/简称变更、暂停上市、恢复上市、吸收合并、终止上市、A+H 或多类别证券。
同一 ticker 在不同时间指向不同实体时必须产生结构化冲突，不能按字符串自动拼接。

### 4.2 中国交易日历

至少保存 `exchange`、`calendar_date`、`is_open`、`previous_open_session`、
`next_open_session`、`session_close_at` 和数据源版本。所有时间使用 `Asia/Shanghai`，系统抓取时间
另存 UTC。

日历承担三项职责：

1. 找出月末形成日。
2. 把公告日映射到保守的 `available_session`。
3. 给停牌、涨跌停和下一可交易日成交逻辑提供真实 session 序列。

### 4.3 不可变公告原始档案

每一份财报、摘要、更正、补充和撤回公告都先作为原始对象保存，之后才抽取字段。原始内容、抓取
行为和归一化运行必须分开：

| 实体 | 必要字段 | 责任 |
|---|---|---|
| `raw_source_object` | `raw_object_id`、`source_name`、`source_object_id`、`media_type`、`byte_length`、`sha256`、`storage_uri` | 只描述不可变内容；同一公告 ID 换 hash 必须保留并报警 |
| `source_fetch_event` | `fetch_event_id`、URL、脱敏 request signature、`retrieved_at_utc`、HTTP 状态、page/cursor、retry log、`raw_object_id` | 描述每次联网获取及分页完整性 |
| `normalization_run` | 输入 manifest、parser/schema/code 版本、运行时间、输出表/hash | 描述离线解析，不污染 raw object |
| `fact_source_evidence` | canonical fact version、raw object、页码/表格/单元格、抽取方法 | 允许多个来源共同证明同一事实 |

公告原始披露时间及其精度可以从原始对象中解析，但必须在 filing 层保存并能追回原文。两个来源
给出相同 canonical 值时合并为多条 evidence，不生成互相竞争的 fact version。

HTTP 200 但正文为空、页码缺失、同一公告 ID 返回不同哈希都必须失败并留痕。不得把 live endpoint
当作可复现档案。Phase A 还必须实测对象数、PDF/响应字节 p50/p95、预计全量存储、API 调用量和
回填时间，形成容量与配额计划，不能用未经测量的固定估算上线。

### 4.4 财报版本与财务事实版本

公告层和事实层必须分离。一份更正公告可能只改一个字段；不能替换整份历史报表。

财报版本至少包含：公告 ID、标题、发行人、报告期、报告类型、合并/单体口径、公告时间及精度、
`available_session`、来源对象哈希，并显式保存：

```text
filing_event_type = UPSERT | RETRACT
supersedes_filing_id
withdraws_filing_id
```

撤回在其 `available_session` 起使被撤事实不可用，直到后续替代版本出现。部分更正只覆盖明确列出的
fact key，不能撤掉整份公告的其他未变字段。

财务事实至少包含：

```text
fact_key = issuer_id
         + concept
         + statement_scope
         + period_start
         + period_end
         + currency
```

每个 `financial_fact_version` 还需保存 `filing_id`、`fact_action=UPSERT|RETRACT`、原始值、原始单位、
规范化 Decimal CNY、YTD/FY/单季类型、`ingested_at_utc`、`supersedes_fact_version_id` 和结构化
失败码。来源页码、表格和单元格通过 `fact_source_evidence` 多对一关联。

QA 也不能原地改状态。另建追加式 `fact_qa_decision`，保存 decision ID、fact version、
`ACCEPTED|REJECTED|NEEDS_REVIEW`、规则/人工 reviewer、决定时间和证据。发布 snapshot 显式冻结
采用的 QA decision IDs。

所有版本、证据和 QA 决策只追加，不允许 UPDATE/DELETE。`known_to` 应在查询或发布快照时由下一
版本推导，不得通过修改旧记录实现。

### 4.5 每日证券市场状态

为了同时支持信号分母和后续可交易性，需要从至少 2012 年开始保存：

- 原始 `open/high/low/close/pre_close`、成交量、成交额。
- 复权因子；复权价可派生，但不得覆盖原始价格。
- PIT 总股本、流通股本、总市值、流通市值，四者语义和单位分开。
- 停牌状态、停复牌时间、涨停价、跌停价、ST 状态、上市板块。
- 数据日、源端发布时间、抓取时间、源快照 ID、QA 状态。

总市值采用 §2.2 冻结的 `CN_SECURITY_TOTAL_MV`，并只在相同 `total_share_scope` 下用
`raw_close * PIT_total_share` 独立复算。供应商若以万元给值，必须在 schema 层显式转为 CNY。
A+H、多股本类别或股本跳变不能靠猜测；无法文档化 basis 的记录不得进入主信号。

月末停牌证券也应由供应商给出可审计的当日状态和估值字段。缺少总市值时不得自行把上一次值
forward-fill；应输出 `TOTAL_MARKET_CAP_MISSING`。

### 4.6 PIT 行业分类

纯原始 E/P 可以先生成，但行业/规模中性残差是必要的稳健性对照，因此完整研究数据门仍需要
历史行业。至少保存：

- `issuer_id`、分类体系、体系版本、层级、行业代码和名称。
- `effective_from/to` 与 `known_from_session`。
- 来源对象和快照版本。

正式 spec 和发布 snapshot 必须冻结唯一的 `taxonomy + taxonomy_version + level`。采购阶段可以在
有历史授权的中证一级行业与明确版本的申万体系之间评估，但进入 Phase E 前必须择一，不能在同一
主面板混用申万 2014/2021 或把今天的行业标签回填到 2013 年。行业缺失时原始 E/P 可保留，但
residual E/P 必须为 null 并标记 `PIT_INDUSTRY_MISSING`。

### 4.7 公司行动和退出处置

至少覆盖现金分红、送股、转增、拆并股、配股、增发导致的股本变化、换股吸收合并、代码变更、
暂停/恢复上市、退市现金处置。每条记录至少保存公告日、股权登记日、除权除息日、支付日、
实际生效日、比例/金额、币种、来源和版本。

这一层主要决定后续收益和 210 万元组合能否真实执行。每一个曾经持有的证券退出，都必须能解释
最终现金或替代证券去向；未知处置不能默认收益为 -100%，也不能让持仓消失。

### 4.8 月末宇宙与 E/P 派生面板

最终需要发布两张月频表：

1. `monthly_universe_snapshot`：形成日全部历史普通 A 股、上市状态、结构性不可用原因和各数据域
   是否覆盖。
2. `monthly_ep_feature`：TTM 分子、总市值分母、E/P、行业、规模、流动性、数据年龄、资格状态、
   QA 状态和 snapshot ID。

另建 `ep_feature_component`，逐条记录四个单季事实版本、市场状态版本、行业版本和证券映射版本。
任何一个最终 E/P 都必须能从一行 feature 追到四个财报原文哈希及形成日总市值来源。

## 5. 三个时间轴与 as-of 规则

每条事实至少同时具有三个时间概念：

| 时间轴 | 示例 | 用途 |
|---|---|---|
| 经济时间 | 财报期间、交易日、公司行动生效日 | 描述事实属于哪个期间 |
| 市场可知时间 | `published_at`、`available_session` | 决定历史形成日能否使用 |
| 系统时间 | `ingested_at_utc`、snapshot ID | 证明本系统何时取得和发布 |

标准 resolver 必须同时固定形成日和数据快照，不能只传形成日：

```text
resolve(requested_fact_key, formation_session, data_snapshot_id)

candidate = data_snapshot manifest 明确列出的 fact/evidence/QA decisions
  where available_session <= formation_session
    and fact_key == requested_fact_key
    and snapshot 内最后一条 QA decision == ACCEPTED

active = 按 UPSERT / RETRACT / supersedes 链重放到 formation_session
selected = active 中可验证版本链的终端事实
```

manifest 必须同时冻结 `source_cutoff_utc`、`qa_cutoff_utc` 和采用的 QA decision IDs。这样后来新增
的解析结果、人工 QA 或供应商回填不会在重建旧 snapshot 时偷偷进入结果。

附加规则：

- 更正公告只改变其 `available_session` 及以后形成的快照；以前发布的月末快照哈希必须不变。
- `available_session` 只决定资格。同一 session 内先沿可验证的 `supersedes` 链选终端版本；没有明确
  链时，才可用具备可靠精度的 `published_at` 排序。
- 日期精度相同、没有可验证先后且同一 fact key 值不同，返回 `DUPLICATE_VERSION_CONFLICT`，禁止
  按行序、抓取顺序或供应商优先级静默挑一个。
- `RETRACT` 从其可用日起移除被撤事实；没有替代时返回 `FACT_RETRACTED_NO_REPLACEMENT`。
- 两个来源值相同可以保留双来源 lineage；值不同必须人工裁定。
- 当前财报披露的前期比较数是一个在当前公告时才可知的新版本，不能把它的值回写到原历史日期。
- 公告日期无法确定、公告与报告期映射歧义、版本链断裂时 fail closed。

## 6. PIT TTM 的唯一算法

令同一知识截止日下已验收的累计归母净利润为：`C_Q1`、`C_H1`、`C_Q3`、`C_FY`。先还原单季：

```text
SQ1 = C_Q1
SQ2 = C_H1 - C_Q1
SQ3 = C_Q3 - C_H1
SQ4 = C_FY - C_Q3
TTM = 最近连续四个 SQ 之和
```

可用等价式做交叉验证：

```text
Q1 锚点: FY(y-1) + Q1_YTD(y) - Q1_YTD(y-1)
H1 锚点: FY(y-1) + H1_YTD(y) - H1_YTD(y-1)
Q3 锚点: FY(y-1) + Q3_YTD(y) - Q3_YTD(y-1)
FY 锚点: FY(y)
```

算法约束：

- 所有组成事实都必须用同一个 `(formation_session, data_snapshot_id)` 重新 as-of 选择。
- 四季必须连续、币种一致、单位明确、均为合并报表、fiscal calendar 一致且累计期间可比。
- 正常并购造成的合并范围变化是有效经济事实，不得自动置空；只有报表范围、会计期间或重述基准
  使累计差分不可比时才失败。
- 财年变更、IPO 历史不足、报告缺失或累计期间不可比时返回 null 和原因码。
- 不允许用最新年报、分析师预测、线性插值或季度年化填补。
- 保留 TTM 锚点、四个 `fact_version_id`、数据年龄和公式版本。
- 用 Decimal 运算，最终研究导出前才转浮点；零市值或非正总市值一律拒绝。

## 7. 建议的逻辑数据模型

实现可以映射到 Parquet、SQLite/PostgreSQL 或其他存储，但以下逻辑表和主键语义必须保留：

| 逻辑表 | 主键/唯一键 | 核心责任 |
|---|---|---|
| `security_master` | `security_id` | 永久证券与发行人关系 |
| `security_identifier_history` | `security_id + id_type + valid_from` | 代码、名称、交易所和板块历史 |
| `exchange_calendar_version` | `exchange + date + snapshot_id` | 中国交易 session 解析 |
| `raw_source_object` | `raw_object_id`；内容 hash 唯一 | 不可变原始响应/PDF |
| `source_fetch_event` | `fetch_event_id` | 请求、分页、重试和取得对象的证据 |
| `normalization_run` | `normalization_run_id` | parser/schema/code 版本与输入输出 manifest |
| `filing_version` | `filing_id` | 公告、报告期、版本和可用日 |
| `financial_fact_version` | `fact_version_id` | 追加式 canonical 财务事实 |
| `fact_source_evidence` | `fact_version_id + raw_object_id + locator` | 多来源原文定位 |
| `fact_qa_decision` | `qa_decision_id` | 追加式接受、拒绝或待复核决策 |
| `daily_security_state_version` | `security_id + trade_date + snapshot_id` | 行情、股本、市值和交易状态 |
| `industry_assignment_version` | `issuer_id + taxonomy + level + effective_from + snapshot_id` | PIT 行业 SCD |
| `corporate_action_version` | `action_id + version_id` | 公司行动与退出处理 |
| `monthly_universe_snapshot` | `formation_session + security_id + snapshot_id` | 月末宽基母体及覆盖漏斗 |
| `monthly_ep_feature` | `formation_session + security_id + feature_version` | 最终 E/P 及资格状态 |
| `ep_feature_component` | `feature_id + component_role + component_id` | 四季利润、总市值等 lineage |

不能以 `(ticker, report_period)` 作为唯一财务主键；不能把供应商当前响应直接当“最终表”。

## 8. 数据源采购与资格验收

### 8.1 推荐的源组合

| 优先级 | 候选源 | 建议用途 | 当前限制 |
|---|---|---|---|
| P0 | [巨潮资讯公告检索](https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search) | 官方公告 ID、时间、原文 PDF、原始/更正版本 truth anchor | 公开网页内部接口无 SLA，不宜每次 live 重建 |
| P1 | [Tushare income](https://tushare.pro/document/2?doc_id=33) | `ann_date`、`f_ann_date`、`n_income_attr_p`、`report_type`、`update_flag` 的结构化试用 | 文档字段不等于完整永久 vintage 契约，必须样本验证 |
| P1 | [Tushare daily_basic](https://tushare.pro/document/2?doc_id=32) | `total_share`、`total_mv`、`circ_mv` | `total_mv/circ_mv` 文档单位为万元，必须规范化和身份复算 |
| P1 | [Tushare daily](https://tushare.pro/document/2?doc_id=27) / [adj_factor](https://tushare.pro/document/2?doc_id=28) | 原始 OHLCV、成交额、复权因子 | 需验证退市、长期停牌和缺页 |
| P1 | [Tushare stk_limit](https://tushare.pro/document/2?doc_id=183) / [suspend_d](https://tushare.pro/document/2?doc_id=214) | 历史涨跌停价、停复牌 | 不可用固定百分比自行回算历史规则 |
| P1 | [Tushare stock_basic](https://tushare.pro/document/2?doc_id=25) / [namechange](https://tushare.pro/document/2?doc_id=100) | 上市、退市、代码/名称历史 | 必须拉取 L/D/P/G 等全部状态，不只当前 L |
| P1 | [Tushare stock_st](https://tushare.pro/document/2?doc_id=397) | 历史 ST 日状态 | 官方页面明确只从 2016-01-01 起，2013-2015 必须另找来源 |
| P1 | [Tushare index_member_all](https://tushare.pro/document/2?doc_id=335) / [index_classify](https://tushare.pro/document/2?doc_id=181) | 申万行业版本和进出日期 | 需验证版本切换与无区间重叠 |
| P1 | [Tushare dividend](https://tushare.pro/document/2?doc_id=103) | 分红、送转、登记和除权日 | 需与股本跳变、复权因子联检 |
| P1 可选 | [Tushare anns_d](https://tushare.pro/document/2?doc_id=176) | 公告 URL、接收时间的冗余源 | 单独权限；不能替代自有原文档案 |
| P2 | [深证信商业 API](https://webapi.cninfo.com.cn/#/apiDoc)、Wind、Choice | 若 P1 版本或历史覆盖失败，参加同一 RFP | 不能依据品牌宣传直接判定 PIT 合格 |

[Tushare 积分/权限说明](https://tushare.pro/document/1?doc_id=290)在 2026-07-13 显示：
`income` 单股历史接口至少 2,000 积分，全市场期间接口 `income_vip` 需要 5,000 积分；常规积分
购买为 1:10，专业用户群是另一条单独路径。采购前应在实际账户核对积分、接口权限、频率、历史
深度和内部归档许可，不按名义积分推定可用性。

### 8.2 供应商必须回答的问题

向每个候选源发送同一份 RFP，要求书面和样本证明：

1. 是否保留首次披露和每次更正的旧值，而不是只返回当前历史快照。
2. 每个版本是否有稳定公告 ID、原文 URL、公告时间、报告期、合并口径和版本顺序。
3. `n_income_attr_p` 是累计/YTD 还是单季，单位、币种和金融企业模板如何表达。
4. 历史数据后续回填或修正时，如何让客户识别“新版本”而不是静默改旧行。
5. 是否完整覆盖已退市、暂停上市、改代码、吸收合并和 A+H 公司。
6. `total_share` 和 `total_mv` 的股本类别、单位、复权状态和停牌日语义是什么。
7. 许可证是否允许内部长期保存原始响应、生成快照、哈希和离线复现。
8. 全量回填、日增量、限流、分页、空响应和失败重跑的 SLA 是什么。

### 8.3 冻结的 200 份资格样本

全市场回填前，先构建至少 200 份双人独立标注的**供应商资格/开发样本**。该集合会交给
Generator，因此不能冒充最终 held-out：

- 年份覆盖 2011-2012 至少 20 份、2013-2015 至少 40 份、2016-2019 至少 40 份、
  2020-2023 至少 50 份、2024-当前至少 50 份。
- 上交所主板、深交所主板/原中小板、创业板、科创板均覆盖。
- Q1、H1、Q3、FY 四种报告均衡。
- 银行、保险、券商、工业企业、亏损企业、复杂控股集团和 A+H 公司均覆盖。
- 至少 20 条原始/更正版本链，其中至少 5 条确实改变归母净利润。
- 每份标注公告 ID、公告时间、报告期、报表范围、原始字符串、单位、规范化值、页码和单元格。

另由 Evaluator 在开发开始前封存至少 100 份不同公告/发行人的独立 acceptance holdout，manifest
和 hash 预先冻结但不向 Generator 公开；其中至少 5 条是版本链。不得针对 holdout 失败文档追加
特例后再把同一集合称作留出集。

供应商资格门：

- 100% 样本可关联到公告 ID、URL、时间和原文哈希。
- 归母净利润覆盖率和按披露精度规范化后的数值准确率均至少 99%。
- 符号错误、列位错误和 10/1000/10000 倍数量级错误必须为 0。
- 20 条更正链版本顺序 100% 正确，旧版本仍可取。
- 未四舍五入准确率 `>=99%` 才 PASS；`[95%, 99%)` 只能标记
  `PARTIAL_NOT_RESEARCH_READY`；低于 95% 为 `NO_GO`。

供应商资格集决定是否值得全量采购；独立 acceptance holdout 决定 G2 能否通过。两者不能合并。

当前巨潮 pilot 的 65.789% 只能证明原文归档可行，不能证明 parser 可用于研究。

## 9. 实施阶段与依赖

本报告不替代 harness 的正式 planning。开发 agent 应先由 Planner 把以下阶段转成 batch spec 和
`features.json`，再由 Generator 分 feature 实现；Generator 不负责写 evaluator 的测试。

### Phase A：源资格和契约 spike

交付：200 份资格集 manifest、双人真值、20 条更正链、独立 holdout 封存证据、Tushare/候选
商业源的结构化对账、许可/接口能力矩阵，以及实测容量、调用配额和回填计划。只有源资格达到
门槛，才批准全市场回填。

### Phase B：证券身份、日历和不可变档案

交付：永久 `security_id/issuer_id`、历史标识映射、沪深交易日历、raw object store、分页完整性、
哈希校验、断点续传和 snapshot manifest。

### Phase C：财报/事实版本与 as-of resolver

交付：`filing_version`、`financial_fact_version`、版本链、UPSERT/RETRACT、公告可用日、追加式
QA decision、同键冲突处理，以及带 `data_snapshot_id` 的任意形成日查询。该阶段不得计算最终 E/P。

### Phase D：PIT TTM 与 lineage

交付：累计值还原单季、四季连续性、四种锚点公式交叉验证、修订前后快照不变性、TTM 组成事实
表和结构化缺失原因。

### Phase E：市场状态、行业和公司行动

交付：原始行情、复权因子、总/流通股本与市值、停牌、涨跌停、ST、行业 SCD、公司行动和退出
处置。总市值只与同 basis 的 `raw_close * PIT_total_share` 做身份复算。

### Phase F：宽基月末面板

交付：2013 至今每个月末的母体漏斗、原始 E/P、行业/规模中性所需字段、所有 component lineage、
覆盖报告和 readiness flags。此阶段仍不输出收益。

### Phase G：可复现发布

交付：冻结 snapshot、canonical manifest、对象/表哈希、schema hash、parser/calendar/library 版本、
fresh-clone 的 hydrate 与离线 reproduce 两步命令，以及两次独立重建一致性证据。

### 建议的代码边界

具体路径由 Planner 决定；为贴合现有工程，可考虑：

```text
trade/data/ashare_pit/                 # provider-neutral schema、resolver、TTM、manifest
scripts/research/ashare_ep/            # 联网 fetch/backfill CLI 和离线发布 CLI
$WORKBENCH_DATA_ROOT/research/ashare_ep/
  raw/                                 # 不可变对象，按 source/object/hash 存储
  normalized/                          # 追加式标准表
  snapshots/<snapshot_id>/             # 冻结月末面板、QA 和 manifest
```

正式实现应提供等价于以下能力的命令，命令名可以调整：

```text
fetch-source-sample
fetch-backfill --snapshot-id ... --from ... --to ...
hydrate-snapshot --snapshot-id ... --artifact-store ...
normalize-offline --raw-manifest ...
build-monthly-ep --snapshot-id ... --formation-from 2013-01-01 --formation-to ...
verify-snapshot --snapshot-id ...
reproduce-snapshot --snapshot-id ... --offline
```

网络抓取和纯计算必须可分离。`normalize-offline`、`build-monthly-ep` 和 `verify-snapshot` 不得访问
互联网。`hydrate-snapshot` 只允许从许可允许的不可变 artifact store 取 manifest 已列对象并验
hash，不得回源供应商或 live webpage；hydrate 完成后，`reproduce-snapshot --offline` 在断网环境
重建，缺一个 blob 就失败。

## 10. Snapshot 与 fresh-clone 契约

每个发布 manifest 至少包含：

```text
schema_version
snapshot_id / parent_snapshot_id
source_cutoff_utc
qa_cutoff_utc
git_commit
parser_version / calendar_version / library_lock_hash
raw_objects[]: source, object_id, URL, bytes, sha256, retrieved_at
qa_decisions[]: qa_decision_id, fact_version_id, decision, decided_at
normalization_runs[]: run_id, input_manifest_sha256, parser/schema/code version
normalized_tables[]: path, schema_hash, primary_key, rows, date_range, sha256
coverage: base_count, structural_ineligible, data_missing, final_eligible
exclusions[]: security_id, formation_session, reason_code
qa_report_sha256
license_distribution_class
```

发布规则：

- 快照从冻结 object store 和 manifest 物化，不从“当前网页”重新发现对象。
- 排序、编码、时区、Decimal 字符串和压缩参数固定；同一输入必须产生逐字节相同发布物。
- raw hash、schema hash、对象数量或分页不一致时 fail closed。
- 失败运行保存报告但不移动 `latest`，也不损坏上一份 good snapshot。
- clean checkout 先 hydrate 指定对象并验 hash，再断网离线归一化并验最终表 hash；两步证据分开。
- 大体量和受许可限制的数据不必进入 Git，但 Git 中必须有版本固定的轻量 manifest 引用和重建代码。

## 11. 分层验收 Gates

| Gate | 硬性通过条件 | 失败动作 |
|---|---|---|
| G0 源资格 | 财务 2011 起、行情/股本/行动 2012 起、面板 2013-01 起，含退出证券；200 份资格集；20 条更正链；旧版本可取；许可允许内部归档 | 不做全量回填 |
| G1 原始归档 | 100% 对象有稳定 ID/URL/时间/hash；分页完整；HTTP 200 空响应被识别；重复抓取幂等 | `NO_GO` |
| G2 财务抽取 | 独立 acceptance holdout >=100；归母净利润覆盖和准确率均 >=99%；0 符号/数量级错误；版本顺序 100% | `[95%,99%)` 为 partial，<95% 为 `NO_GO` |
| G3a 信号支撑 | 历史证券映射无歧义；逐月财务+同 basis 总市值+冻结行业联合覆盖 >=95% | signal 未就绪 |
| G3b 执行支撑 | 全基础母体所需 session 均有 OHLCV/amount/复权/停牌/涨跌停/ST/板块规则；仅预先枚举的 `OFFICIAL_SUSPENSION/NOT_YET_LISTED/DELISTED_EFFECTIVE/EXCHANGE_CLOSED` 可替代 bar，供应商缺失、解析失败或状态未知一律 FAIL | execution 未就绪 |
| G4 市值身份 | 全部可比行运行同 basis 身份校验；至少 99% 误差 <=0.5%；所有 >0.5% 行隔离，>5% 标严重异常 | 分母 `NO_GO` |
| G5 TTM/lineage | 至少 100 个证券-形成日人工复算 100% 一致；每行可追到四个事实版本和原文 hash | 信号 `NO_GO` |
| G6 修订不变性 | 插入未来更正/撤回/QA 决策后，旧 data snapshot 重建 hash 不变；新 snapshot 只从事件可用日起改变 | 信号 `NO_GO` |
| G7 公司行动/退出 | 全宇宙事件清单完整；冻结行动/退出样本 100% 可解释；未来实际持仓路径另在组合 gate 要求 100% | execution 未就绪 |
| G8 可复现 | 两个 clean checkout 各自 hydrate 后断网重建逐字节一致；offline 缺一个 blob 必须失败且不能回源 | 不得标记 ready |
| G9 连续面板 | 固定从 2013-01 月末至最新完整月无断档；逐月披露母体、市场不可用、结构性不可用、供应商缺失和最终可用数 | 不得开始收益研究 |

覆盖率分母固定如下，不能循环收缩：

```text
base_count = 仅由证券主数据和 formation_session 决定的全部在市普通 A 股
market_information_unavailable = 官方档案证明当时尚未公开四个连续季度
structural_ineligible = 仅限预先枚举的 fiscal-calendar/期间不可比等经济原因
supplier_missing = 官方应有事实或市场状态，但供应商/解析链缺失
expected_feature_count = base_count - market_information_unavailable - structural_ineligible
joint_signal_coverage = validated_feature_count / expected_feature_count
```

ST、停牌、负利润、后来退市或字段缺失都不能成为缩小 `base_count` 的理由。上述各桶逐证券逐月
输出；`market_information_unavailable` 必须由完整官方公告档案证明，不能用供应商没有返回来冒充。
95% 是最低研究门，不是允许选择性删除最难证券的额度。

## 12. 后续 Evaluator 必测边界

以下是验收契约，不要求 Generator 自己编写测试：

### 公告与版本

- 原始公告、更正未改目标值、更正确实改目标值、撤回无替代、撤回后有替代和补充公告。
- 公告在形成日前、形成日、周末、长假最后一天；只有日期与有精确时间两种输入。
- 年报和一季报同日披露；同日原报/更正有 supersedes 链、无链；同一 fact key 相同值和冲突值。
- 在历史运行后注入未来更正、撤回或 QA 决策，验证旧 `data_snapshot_id` 的 hash 不变。

### 财务事实与 TTM

- Q1、H1、Q3、FY 四个锚点及跨年四季。
- 负数、零、括号负数、逗号、元/千元/万元/百万元和币种歧义。
- 合并报表与母公司报表同页；归母净利润与扣非归母净利润相邻。
- 前期比较数重述、财年变更、新股历史不足、缺一季和报告期不连续。
- 正常收购改变合并范围但累计期间仍可比时必须保留；真正不可比的期间必须 fail closed。
- 金融企业、A+H、复杂控股集团和旧版 PDF 模板。

### 市值、行情与身份

- raw/qfq/hfq 混淆、总市值/流通市值混淆、总股本单位混淆和 basis 不一致。
- 送转、配股、拆并股后的股本跳变；一发行人多证券类别。
- A+H/A+B 主值固定 `CN_SECURITY_TOTAL_MV`，不得隐式切换为类别市值求和；排除敏感性单列。
- ticker/简称变化、ticker 复用、吸收合并和退市后代码消失。
- 月末停牌、下一交易日仍停牌、开盘涨跌停、历史 ST 和板块规则变化。

### 抓取与复现

- HTTP 200 空正文、漏一页、重复一页、乱序分页、限流和中断续跑。
- 同一 source object ID 内容 hash 变化、manifest 篡改、schema drift、缺对象。
- 两次全新 checkout 各自 hydrate 后断网重建；offline 缺 blob 时不得回源。
- Generator 可见资格集与 Evaluator 封存 holdout 不重叠；模拟把 holdout 泄露给 parser 调参应失败。
- mutation：把当前成员、当前行业、当前总股本或当前修订值塞入历史，测试必须失败。

## 13. 结构化失败码和运行状态

至少实现以下 failure codes，禁止只输出自由文本：

```text
SOURCE_UNAVAILABLE
RAW_HASH_MISMATCH
SCHEMA_DRIFT
SECURITY_MAPPING_AMBIGUOUS
ANNOUNCEMENT_TIME_AMBIGUOUS
VERSION_CHAIN_BROKEN
DUPLICATE_VERSION_CONFLICT
FACT_SCOPE_AMBIGUOUS
UNIT_AMBIGUOUS
FACT_QA_FAILED
SNAPSHOT_QA_DECISION_MISSING
FACT_RETRACTED_NO_REPLACEMENT
NON_CONTIGUOUS_TTM
TOTAL_MARKET_CAP_MISSING
MARKET_CAP_BASIS_AMBIGUOUS
MARKET_CAP_IDENTITY_FAILED
PIT_INDUSTRY_MISSING
TRADING_STATUS_MISSING
CORPORATE_ACTION_UNRESOLVED
DELIST_DISPOSITION_MISSING
COVERAGE_BELOW_GATE
FRESH_CLONE_UNREPRODUCIBLE
```

整次 run 只允许：

- `READY`
- `PARTIAL_NOT_RESEARCH_READY`
- `NO_GO`

任何 partial 都不得被上层当作空列表或成功。readiness 至少拆成：

```text
ep_signal_data_ready
ep_execution_data_ready
cny_2_1m_portfolio_backtest_allowed
```

只有 G0、G1、G2、G3a、G4、G5、G6、G8、G9 全通过后才能置
`ep_signal_data_ready=true`。在共享主数据与复现门通过的基础上，G3b、G7 通过后才可置
`ep_execution_data_ready=true`。两者均为 true 且后续策略协议冻结后，才允许第三个标志为 true。

## 14. 禁止的实现捷径

1. 禁止以 `(ticker, fiscal_quarter)` latest-wins 去重。
2. 禁止用法定披露截止日代替实际公告日。
3. 禁止用当前快照数值回填历史公告日。
4. 禁止用 generic `BusinessDay` 代替沪深交易日历。
5. 禁止用累计 EPS/价格、`1/PE` 或预测利润冒充 PIT TTM E/P。
6. 禁止用流通市值替代总市值。
7. 禁止用当前总股本乘历史价格。
8. 禁止用复权价计算市值。
9. 禁止对缺失财务值填 0、线性插值、forward-fill 或年化。
10. 禁止删除负利润证券来美化 E/P 分布。
11. 禁止只拉当前 `list_status=L` 的幸存证券。
12. 禁止把当前行业标签回填历史。
13. 禁止遇到同键冲突时按抓取顺序任选一行。
14. 禁止重新访问 live endpoint 来“复现”旧 snapshot。
15. 禁止用 B070 的 800 股架构 pilot 声称完成全 A 股宽基。
16. 禁止在任一数据 gate 未通过时输出收益、财富曲线或可交易结论。
17. 禁止旧 snapshot 重建时读取后来新增的 fact、QA decision 或 parser 输出。
18. 禁止把 Generator 已看过的资格集当作独立 acceptance holdout。
19. 禁止对 A+H/A+B 在不同日期或供应商间静默切换市值 basis。
20. 禁止把撤回实现为删除旧行或继续永久选中被撤事实。

## 15. Developer Definition of Done

开发交付只有满足以下全部条件才算数据工程完成：

- 正式 spec 明确冻结本报告第 2、5、6 节的语义以及唯一行业
  `taxonomy + taxonomy_version + level`，feature 有依赖顺序。
- 新数据域不读取旧 `fundamentals.csv` 作为正式事实源。
- raw object、fetch event、normalization run、标准表和发布快照责任分离，旧版本不可变。
- 任意财务事实可追到公告 ID、原文 hash、页码/位置、parser 版本和冻结 QA decision。
- 任意 E/P 可追到四个单季事实版本和一个月末总市值版本。
- 全部缺失、冲突和覆盖不足以结构化原因码呈现。
- 全量回填支持断点、幂等、分页完整性和不移动 last-good snapshot。
- 固定从 2013-01 月末至今逐月输出完整覆盖漏斗，不静默 dropna、不向后滑动起点。
- hydrate 和断网 reproduce 有独立命令入口及 hash 证据。
- README/运行文档写清凭据、数据许可、数据根、配额、增量更新和灾难恢复。
- Generator 不修改生产策略默认值，不生成收益结论，不自行把 readiness 置为 true。
- 资格集与 Evaluator 封存 holdout 的 manifest/hash 在实现前固定且不重叠。
- 交付给独立 Evaluator 后，G0-G9（含 G3a/G3b）和第 12 节边界测试全部有机器证据。

## 16. 建议给开发 agent 的首个任务

不要一开始下载 2013 至今全市场。首个实现任务应限制为：

> 建立 provider-neutral 的证券 ID、交易日历、raw object manifest、filing/fact version schema 和
> 带 `data_snapshot_id` 的 as-of resolver；接入冻结的 200 份供应商资格/开发样本及至少 20 条
> 更正链；由 Evaluator 另行封存独立 holdout；生成供应商资格报告。不得生成 E/P 收益，不得覆盖
> 旧版本。只有源资格达到 G0-G2，才规划全量回填。

Phase A 可另外用 B070 的 2019 年以后约 800 股 PIT 宇宙验证 loader 和月末 join 的工程形状，
但最高只能标记 `PILOT_READY`。它不是全 A 股研究样本，也不能绕过 2013 年以来的财报、退出证券
和总市值采购。

## 17. 最终研究裁定

纯 E/P 仍是下一条理论先验较高、且适合 210 万元现金纯多头账户继续投入的数据路线；但它的
先验优势不允许降低 PIT 标准。当前仓库同时缺少可靠 as-filed 财务版本、历史总市值、全 A 股
身份历史、PIT 行业、2013 起执行状态和 fresh-clone 档案，因此仍为 `DATA_NO_GO`。

开发的正确目标不是“先算出一个 E/P”，而是建设一个可以回答以下问题的数据系统：

> 在任意历史月末，市场当时知道哪一版归母净利润、公司当时有多少总股本和总市值、证券当时
> 属于哪个实体和行业，以及这些答案能否从冻结原文重新得到？

只有这个问题得到机器可复核的肯定答案，下一轮才进入可交易策略的收益检验。
