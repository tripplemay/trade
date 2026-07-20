# B108 — 巨潮 PDF parser 自检重构 + 独立样本重评（规格）

> 批次类型：混合（2 generator + 1 codex）
> 上游：`docs/audits/ashare-pure-ep-data-foundation-implementation-handoff-2026-07-13.md`
> 现状裁定：A 股纯 E/P `DATA_NO_GO` — **本批次不改变该裁定**
> 采购决策：**先不花钱**。先验证「免费源 + 自建 parser」的天花板，再决定是否采购 Tushare/商业源。

## 1. 背景与目标

`ashare-as-filed-data-pilot-2026-07-12` 给巨潮 PDF 抽取判了 `NO_GO`，依据是 38 份可比样本中只有
25 份（65.789%）与对照值在 0.5% 内一致。本批次起因于对该结论的复核，发现两件事：

**(a) 13 份失败里至少 10 份是本仓 parser 自身的 bug，不是数据源缺陷。**

| 失败样本 | 表现 | 根因（`scripts/test/ashare_as_filed_data_pilot.py`） |
|---|---|---|
| `600436` 抽出 1 元 / `603885` 抽出 11 元 | 附注列误认 | `_non_percent_numbers` 抓走标签后全部数字，`extract_parent_profit` 取 `numbers[0]`，命中「附注」列的注释编号 |
| `601113` 差 10⁴ / `688981`·`688235` 差 10³ | 单位跨表错绑 | `_unit_scale` 在 before(1600 字符)+after(60 字符) 里取 `matches[-1]`，可能抓到**上一张表**的单位声明；且 `_split_consolidated_row` 回看 35 行、`_label_context` 回看 1600 字符，两条路径窗口不一致 |
| `000100`·`000800`·`688515` 抽到 2 / 4.01 | 列位选错 | `selected_index = 2 if report_key == "q3" ...` 硬编码列号，模板列数浮动即偏移 |
| `600843`·`600639`·`600688` 抽不出 | 旧模板断行 | `_split_consolidated_row` 在**单行内**找「归属于母公」，`pdftotext -layout` 断行即失配 |

四类同源：**抽取器没有任何自检，抽错和抽对返回的数据结构完全一样。**

**(b) 65.789% 的对照物是 Eastmoney 当前快照，不是人工真值**（pilot 报告 AF-005 自述）。
拿它当靶心调参数会拟合到一个本身不可靠的目标上。

### 目标

1. 把抽取器从「猜一个值」改成「**多源交叉验证，不一致就承认不知道**」。
2. 用**独立新抽样本**重新测量，得到一个可以据以决策采购的数字。
3. 输出结论：免费源 + 自建 parser 是否够用；不够则量化差距，作为采购论证输入。

## 2. 硬约束（H）

- **H1 不得针对已知 13 份失败样本加特例。** 修的必须是 bug **类别**，判定依据必须与具体样本无关。
  （依据：pilot 报告 L110-111 明确禁止，会造成样本内过拟合。）
- **H2 原 50 份样本已被 Generator 上下文看过 = 样本内，不得用于最终评测。** 最终数字必须来自
  F003 新抽的、Generator 从未见过的 holdout。
- **H3 Generator 不得抽取或运行最终评测样本。** F002 只交付抽样**工具**；抽样动作与评测由
  Codex 在 F003 执行（铁律 #4；对齐上游报告 §8.3「holdout 由 Evaluator 封存、不向 Generator 公开」）。
- **H4 不得引入任何外部对照物作为正确性判据。** 一致性判定只能来自文档内部。Eastmoney 快照
  仅可作为**诊断性参考列**输出，不得进入 PASS/FAIL 逻辑。
- **H5 research-only。** 不改生产代码、不改策略默认值、不产出 E/P 或收益、不动 readiness flag。
- **H6 不采购任何数据源。** 本批次零花费。

## 3. 核心设计：多源交叉验证

### 3.1 三个独立来源

| 源 | 位置 | 角色 |
|---|---|---|
| **S1** | 合并利润表 `归属于母公司所有者的净利润` 行 | 主源 |
| **S2** | 主要会计数据 / 主要财务数据表 `归属于上市公司股东的净利润` | 独立确认源 |
| **S3** | `基本每股收益 × 期末股本` | **仅作数量级哨兵**，不单独确认 |

S3 只用于卡 10ⁿ 错误：基本 EPS 用的是加权平均股本，与期末股本有真实偏差，因此 S3 **永远不能**
作为 CONFIRMED 的唯一依据，只能否决（发现数量级不符时降级为冲突）。

### 3.2 判定规则

```text
S1 与 S2 都抽到且相对误差 <= 0.1%   → CONFIRMED（返回值）
仅一个源抽到                        → SINGLE_SOURCE_UNCONFIRMED（返回值，但不计入 confirmed）
S1 与 S2 都抽到但超出容差           → SOURCE_CONFLICT（返回 None + 全部候选值供人工裁定）
S3 与已 CONFIRMED 值数量级不符      → MAGNITUDE_IMPLAUSIBLE（撤销 CONFIRMED，降为冲突）
无源抽到                            → EXTRACTION_FAILED
```

关键语义：**冲突时返回 `None` 而非猜测值。** 失败模式从「静默错误」变为「诚实的不确定」，
对齐上游报告 §13 结构化 failure code 的要求。

### 3.3 结构化 failure codes（本批次实现）

```text
LABEL_NOT_FOUND          目标标签在文档中不存在
EXTRACTION_FAILED        标签在但无法解析出数值
COLUMN_AMBIGUOUS         无法按表头确定目标列
UNIT_AMBIGUOUS           无法把单位绑定到本表
SOURCE_CONFLICT          多源不一致
SINGLE_SOURCE_UNCONFIRMED 仅单源，未获交叉确认
MAGNITUDE_IMPLAUSIBLE    EPS×股本 哨兵否决
```

### 3.4 四类 bug 的结构化修法（均不依赖样本）

| bug | 修法 | 为何不是过拟合 |
|---|---|---|
| 附注列误认 | 用 `pdftotext -layout` 保留的列对齐把行切成单元格，**按表头文字**（`附注`/`注`）识别并跳过附注列 | 判据是表头文字与列结构，与任何具体数值无关。**禁止**用「数值太小」这类幅度阈值 |
| 单位跨表错绑 | 单位声明只在**本表边界内**向上就近搜索，遇到表边界即停；两条抽取路径共用同一窗口逻辑 | 判据是表边界，与具体倍数无关 |
| 列位选错 | 按**表头文字**（`本报告期`/`年初至报告期末`/`上年同期`）匹配所需期间语义，取消硬编码 `selected_index` | 判据是表头语义，与列数无关 |
| 旧模板断行 | 匹配前先做标签规范化，重连跨行标签 | 判据是文本规范化，与具体文档无关 |

## 4. 功能列表（`features.json` 权威，此处为设计说明）

- **F001（generator）** 多源交叉验证抽取器 + 结构化 failure codes。含单测（合成 fixture，不用真样本）。
- **F002（generator）** 确定性分层抽样 CLI。**只交付工具，不产出评测样本。**
- **F003（codex）** 独立抽 holdout、跑评测、人工裁定冲突样本、出 signoff。

### F002 抽样器的关键要求

现有 `select_regular_sample` 取「巨潮返回顺序的前 4 个」，**不可用于 holdout**：巨潮返回顺序
会随时间变化，且非随机 → 样本不可复现、且系统性偏向某类公司。新抽样器必须：

- `--seed` 确定性伪随机抽样，同 seed 同参数必须复现同一份 manifest
- 分层：年份 × 交易所板块（沪主板 / 深主板 / 创业板 / 科创板）× 报告类型（Q1/H1/Q3/FY）
- `--exclude-manifest` 排除指定 manifest 中的公告 ID（用于排除已烧掉的 50 份）
- 输出冻结 manifest：`announcement_id` / `sec_code` / `report_period` / `url` / `pdf_sha256`
- **只输出 manifest，不下载、不抽取、不评测**

## 5. 验收标准（F003）

### 5.1 门槛设计理由

上游报告 §8.3 的供应商门是「准确率 ≥99%」，但那是判定**供应商**是否值得采购。对自建 parser，
真正致命的不是覆盖率低（少几条数据而已），而是**自信地给出错误值**——那会污染整个研究。
因此本批次把指标拆成两个，只对后者设硬门：

| 指标 | 含义 | 门槛 |
|---|---|---|
| **confirmed coverage** | 达到 CONFIRMED 的文档占比 | **报告，不设门** |
| **confirmed precision** | CONFIRMED 中实际正确的占比 | **≥99% 硬门** |
| **magnitude errors among CONFIRMED** | CONFIRMED 中的 10ⁿ 错误数 | **必须为 0** |

### 5.2 F003 执行要求

1. 用 F002 工具、**自选 seed**、`--exclude-manifest` 排除原 50 份，抽 **≥60 份** holdout；
   manifest 与 hash 先冻结落盘，再开始评测。
2. 跑 F001 抽取器，输出逐份结果 + failure code 分布，**按年份/板块/报告类型分层**报告。
3. **人工裁定**：对 CONFIRMED 随机抽 ≥20 份，Codex **直接读 PDF 文本**（不经 parser）独立判断
   真值，据此计算 confirmed precision。这是本批次唯一的正确性判据。
4. **冲突有效性检查**：对 `SOURCE_CONFLICT` 全部裁定，区分「真的抓到了 parser 错误」（好）
   与「两个源本就应该不同 / 误报」（坏）。误报率过高说明交叉验证本身有缺陷。
5. 输出 `docs/test-reports/B108-cninfo-parser-selfcheck-signoff-YYYY-MM-DD.md`：逐条证据 +
   PASS/FAIL + **明确结论：免费源+自建 parser 是否够用，不够则差距量化。**

### 5.3 边界检查

- H1：审查 F001 实现中是否出现针对具体 `sec_code` / 具体数值幅度的特例分支 → 有即 FAIL
- H4：审查 PASS/FAIL 逻辑是否引用了 Eastmoney 对照 → 引用即 FAIL
- H5：`git diff` 确认未触碰 `workbench/` 生产代码与策略默认值

## 6. 本批次明确不做

- 不建 PIT 数据地基（上游报告 Phase A-G 全部不在本批次）
- 不计算 E/P、IC、收益、财富曲线
- 不采购 Tushare 或任何商业源
- 不改变 `DATA_NO_GO` 裁定与三个 readiness flag
- 不解决 `stock_st` 2013-2015 缺口（与 parser 无关）

## 7. 用户侧人工事项（不在 feature 内）

`600787`（误差 0.87%）与 `601992`（误差 29.28%）需人工翻原始 PDF 裁定属真实修订、口径差异
还是 parser 错误。这两份无法自动化，结论回写本 spec 或 F003 signoff。

## 8. 风险登记

| 风险 | 应对 |
|---|---|
| 交叉验证误报率高（S1/S2 本就常不等） | F003 §5.2(4) 专门量化；误报率高则调整容差或降 S2 为参考源，**在 signoff 中记录而非静默改门槛** |
| 巨潮接口不稳 / 限流 | 沿用现有 `CninfoClient` 重试与分页逻辑；HTTP 200 空响应须失败留痕（现有实现已有） |
| 新抽样本仍撞上已看过的公司 | `--exclude-manifest` 按 `announcement_id` 排除；同公司不同期视为不同样本（可接受） |
| Codex 读 PDF 文本裁定，与 parser 共用同一文本层 | 可接受：本批次 bug 类别全是**选择**错误（选错列/行/单位），不是文本抽取错误。此限制须在 signoff 中写明 |
