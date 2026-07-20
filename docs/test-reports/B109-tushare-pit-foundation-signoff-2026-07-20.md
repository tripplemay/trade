# B109 Tushare PIT 数据层 v0 + 巨潮对拍审计 — F003 独立验收 Signoff

> 状态：**FAIL（fixing）** — 四道硬门 G-A..G-D 全通过、五条边界 H1/H2/H3/H5/H6 全守住，
> 但发现 **2 条 MEDIUM 缺陷**（D1 作废数字仍在核心模块 docstring 中被当作设计依据陈述；
> D2 acceptance 明写的「替换 B076」只交付了替代品、未退役旧路径）。
> 另提出 **1 条对门本身的异议**（I1：G-A 的统计效力不足以支撑其字面阈值），此条须 Planner/用户裁定，非 Generator 可修。
>
> 验收方：独立无实现上下文 agent 代 Codex（evaluator 角色）
> 日期：2026-07-20
> 前置：F001 ✅ / F002 ✅（progress.json status=verifying）

---

## 0. 本报告的证据纪律

**每个数字都标注了产生它的命令。** 凡引用 Generator 报告而未自行复算的，一律显式标为
「引用未复核」。本次验收**未引用任何未复核数字作为结论依据**。

- 环境：`.venv/bin/python`（本机 python3=3.9.6 不满足 >=3.11），`tushare` 1.4.29
- 验收脚本与原始产物：`docs/test-reports/B109-holdout/`（10 份 JSON + 9 个可重跑脚本）
- H6：token 全程只经 `vintage_probe.load_token()` 从 `.env.local` 读，未落盘、未打印、未入仓（§5 已验证）

---

## 1. 门禁汇总

| 门 | 条件 | 实测 | 结论 |
|---|---|---|---|
| **G-A** 对拍一致性 | >=60 份样本，一致率 >=99%，不一致项 100% 人工裁定 | 抽样 **119**；可裁定 **22**，一致率 **100.00%（22/22）**；扩展对拍 100 份，**已裁定 Tushare 错 = 0**；5/5 不一致项全部人工裁定完毕 | **PASS**（字面）＋ **I1 异议** |
| **G-B** as-of 正确性 | 修订前后各返回正确版本；注入未来修订后旧形成日**逐字节不变** | 真实修订证券 **74** 只；抽验 **12/12** 修订前后取值不同且各自正确；**12/12** 注入后 sha256 指纹不变；**12/12** 正确置 `superseded_later` | **PASS** |
| **G-C** 分母身份 | 误差 <=0.5% 比例 >=99%，>5% 全部隔离 | 跨 2014–2025 **7 个交易日 / 27,963 证券-日**，**100.0000%** 落在 0.5% 内，**>5% = 0**，中位误差 ~1e-11；与被审计模块 **0 处分歧** | **PASS** |
| **G-D** 覆盖披露 | 逐月/逐层漏斗，`flag=0` 缺口显式量化，不得静默 | 漏斗算术**精确闭合**（usable 2298 + drops 221 = panel_rows 2519）；12 项强制披露字段全部随产物输出 | **PASS** |

> coverage 只报告不设门（spec §5）——本次未把覆盖率作为通过条件。

---

## 2. G-A 对拍审计（最重的一块）

### 2.1 抽样：验收方自选 seed（H3）

```bash
.venv/bin/python docs/test-reports/B109-holdout/f003_select.py
# pool=4833 burned_excluded=246 selected=119
# overlap_with_burned=0
# strata_total=89 quota_unmet=22
```

- **seed = 570193**，`quota_per_stratum = 2`。该值由本次验收方选定；
  已核实**仓库内不存在预置 manifest、`select_audit_sample` 无默认 seed**（§5 H3）。
- **排除 246 份已烧语料**（B108 两轮 holdout manifest + 本地实际下载过的 PDF 文件名并集），
  实测 `overlap_with_burned = 0`。依据：样本内 26.3% vs 样本外 16.7%，在见过的语料上测量高估 57%。
- 22 个层未满配额，**全部为结构性空层或被排除耗尽**，非缺陷：
  科创板 2015/2018 各 4 层（科创板 2019 年才开板，候选池 `available=0`）；
  其余为创业板/深主板小层被已烧语料排除后候选不足。**已逐层留痕，未静默截断**。

### 2.2 ★下载 + `build_pdf_freeze`：F002 标为「未验证」的路径，本次**实际执行成功**

F002 completed_note 明写：「审计器的 **PDF 下载 + build_pdf_freeze 路径未被执行**……
按 B108 E01 教训显式标注为未验证，不得读作可用」。**本次验收执行了该路径：**

```bash
.venv/bin/python docs/test-reports/B109-holdout/f003_download.py
# downloaded_ok=119/119
# freeze: pdf_count=119 missing=0
# manifest_sha256=ecf736e87357c9727ecadef2b496024113489e99edf433a316fef1f72fdd853e
```

- 巨潮 `static.cninfo.com.cn` 可达，**119/119 全部下载成功**，零失败、零重试耗尽。
- `build_pdf_freeze` 正常产出 119 条字节哈希、`missing_count=0`。
- **结论：该路径由「未验证」升级为「已验证可用」。** 冻结产物见 `B109-holdout/pdf-freeze.json`。

> 这是 B108 E01 教训的正向闭环：被规则挡住的路径，换一个有权执行的角色去跑，就能真正验证。

### 2.3 对拍结果与★自欺陷阱的真实呈现

```bash
.venv/bin/python docs/test-reports/B109-holdout/f003_extract.py
# anchor_status: SINGLE_SOURCE_UNCONFIRMED 58 / SOURCE_CONFLICT 22 / CONFIRMED 22 / EXTRACTION_FAILED 17
.venv/bin/python docs/test-reports/B109-holdout/f003_audit.py
# n_total=119  n_adjudicable=22  adjudicable_frac=18.5%  consistency_rate=100.00%
# count_match=22  count_mismatch=0  count_tushare_unresolved=0  count_anchor_unusable=97
```

**可裁定率 18.5%，一致率 100%** —— 这正是 `audit.py` 模块 docstring 预警的自欺形态：
anchor 失败率越高，分母越小，一致率越漂亮。`audit_summary` 强制并排输出
`adjudicable_fraction` 的设计在此**被实测证明有价值**（Generator 前置警告 (1) 属实，
其预估「60 份约剩 10 份可裁定」与本次 119 份剩 22 份同量级）。

### 2.4 把 97 份「不可裁定」榨出信号（分层，效力严格区分）

```bash
.venv/bin/python docs/test-reports/B109-holdout/f003_supplement.py
# [单源支持性证据] n=56 一致=53 (94.6%)
# [冲突项] n=22 Tushare 命中某个候选=20 (90.9%)
```

| 层 | n | 结果 | 计入硬门? |
|---|---|---|---|
| CONFIRMED（交叉确认 anchor） | 22 | 22 一致，0 不一致 | ✅ 计入 G-A |
| SINGLE_SOURCE（单源） | 56 | 53 一致，**3 不一致 → 全部人工裁定** | ❌ 支持性证据（B108 实测单源是错抽高发区） |
| SOURCE_CONFLICT（parser 内部冲突） | 22 | 20 命中候选之一，**2 未命中 → 全部人工裁定** | ❌ 弱证据 |
| EXTRACTION_FAILED | 17 | 无信号 | — |

**可对拍总数 = 100；已确认的 Tushare 错误 = 0。**

### 2.5 ★人工裁定：5/5 不一致项，**全部判 Tushare 正确、巨潮 parser 错**

spec 要求「不一致项 100% 人工裁定归因」。逐份查阅 PDF 原文文本，归因如下：

| # | 证券 / 期 | anchor 读数 | Tushare | 裁定 | 原文依据（`pdftotext -layout` 行号） |
|---|---|---|---|---|---|
| 1 | 600958.SH 2023Q3 | 955,727,300.80 | 2,857,177,459.49 | **Tushare 对**；parser 取错列（单季 vs 累计） | L37 `955,727,300.80 -29.45 2,857,177,459.49 42.71` = 本报告期/年初至报告期末两列；L374 利润表累计列 `2,857,177,459.49` |
| 2 | 002153.SZ 2023FY | 10,264,892.40 | -104,622,631.62 | **Tushare 对**；parser 取到分季度表 Q1 单元格 | L3334 正文「2023 年度归属于母公司股东净利润为 **-104,622,631.62** 元」；L353 分季度 `10,264,892.40 / 12,043,124.88 / -7,890,036.31 / -119,040,612.59`，四季合计 = -104.63M ✓ |
| 3 | 688059.SH 2023FY | 24,108,277.75 | 157,906,595.78 | **Tushare 对**；同上（分季度 Q1） | L519 正文「归属于母公司所有者的净利润 **15,790.66 万元**」；L2876 分红年度归母 `157,906,595.78` |
| 4 | 600143.SH 2023FY | 候选 1,991,899,230.86 / 298,633,388.72 | 316,725,788.87 | **Tushare 对**；parser 取到**上年同期列** | L219 `316,725,788.87 1,991,899,230.86 -84.10 …` = 本年/上年；L3096 分红年度归母 `316,725,788.87` |
| 5 | 000858.SZ 2025FY | 候选 31,853,172,533.98 / 207,537,666.72 | 8,954,257,202.51 | **Tushare 对**；parser 取到**上年同期列**（表头跨行折断） | L472 正文「归属于上市公司股东的净利润 **89.54 亿元**、同比下降 71.89%」；L187 `8,954,257,202.51 31,853,172,533.98 -71.89%` |

**归因分布：口径差异 0 / Tushare 错 0 / 巨潮 parser 错 5。**
两类 parser 缺陷复现：**(a) 上年同期列未排除**（#4 #5，且 #5 因表头「归属于上市公司股东的」
跨行折断导致列模型失效）；**(b) 分季度表/单季列被当作累计值**（#1 #2 #3）。
两者均属 B108 已知缺陷域，spec §6 明确「不继续投入 B108 的 PDF 覆盖率」，故**不作为本批次缺陷记账**。

### 2.6 ★I1 — 对 G-A 门本身的异议（须 Planner/用户裁定）

> 团队 lead 授权：「如实测发现某个门在当前数据条件下无法给出有统计意义的结论，如实写出来比硬凑一个数字有价值」。

**G-A 字面通过，但其字面阈值在本次数据条件下不可被证实。**

| 证据基础 | n | 观测错误 | 95% 置信下可断言的一致率下界 |
|---|---|---|---|
| 硬门（CONFIRMED） | 22 | 0 | **>= 87.27%** |
| 扩展（含支持性 + 弱证据） | 100 | 0 | **>= 97.05%** |
| 门要求 | — | — | **>= 99%** |

```bash
.venv/bin/python -c "... 1-(0.05)**(1/n) ..."   # rule of three，0 失败精确解
# n=22  -> 错误率上界 12.7305%
# n=100 -> 错误率上界  2.9513%
# 要在 95% 置信下断言 >=99%（0 错）需 n >= 299 可裁定样本
```

- 「一致率 100%」背后的**真实样本量是 22，不是 119**。n=22 时**一次不一致即掉到 95.5%**，
  门的通过与否由单份 PDF 决定 —— 这不是稳健判据。
- 要真正**证实** >=99%，需 **>=299 份可裁定**样本；按本次实测可裁定率 18.5%，
  对应需下载约 **1,617 份** PDF。这与 spec §6「不继续投入 B108 的 PDF 覆盖率」直接冲突。

**建议（三选一，请用户/Planner 裁定）：**
1. **重述门**为「>=N 份**可裁定**样本上 0 不一致 + 不一致项 100% 人工裁定」，
   并把「一致率」与 `n_adjudicable` 强制绑定引用（代码层已如此，门的措辞应对齐）；
2. 接受当前证据强度，把 G-A 结论记为「**一致率 >=97.05%（95% 置信，n=100，0 错）**」而非「>=99%」；
3. 若坚持 99% 字面阈值，须追加约 1,500 份 PDF 下载与抽取 —— 需评估是否值得。

**验收方倾向 (1)+(2)**：本次 5/5 人工裁定**全部指向 Tushare 正确、且无一例口径差异**，
方向性结论（Tushare 的 `n_income_attr_p` 可信）证据充分；受限的只是「99%」这个具体数字的可证实性。

---

## 3. G-B as-of 正确性与修订不变性

```bash
.venv/bin/python docs/test-reports/B109-holdout/f003_gb.py
# 20211231: pages=3 rows=10740 consolidated=10740
# 真实修订证券数（同期多 f_ann_date 且值不同）= 74
# 检验证券数 = 12
#   修订前后取值不同           = 12/12
#   注入未来修订后旧形成日不变 = 12/12
#   旧形成日正确置 superseded_later = 12/12
```

- 选 2021FY（F001 标为可信窗口，版本多重度 91.2%），**在真实修订数据上**验证，非构造样本。
- 修订前/修订后形成日各自返回**当时可见的那一版**，12/12 正确。
  例：`002383.SZ` 20220415 见 -92,704,523.84 → 20230831 见 201,841,454.67（跨零反号，as-of 各自正确）。
- **修订不变性**：注入 `f_ann_date=20991231` 的未来修订后，对旧形成日的 `ResolvedFact`
  做规范序列化 sha256，**12/12 指纹完全不变**（上游报告 §12 要求「逐字节不变」）。

**结论：G-B PASS。**

---

## 4. G-C 分母身份 + H2

```bash
.venv/bin/python docs/test-reports/B109-holdout/f003_gc.py
```

★**独立性**：本脚本自己算 `|close*total_share - total_mv| / total_mv`，**不调用**
`marketcap.identity_error` 得结论；随后再与 `build_point` 对拍。

| 交易日 | n | <=0.5% | >5% | 中位误差 | 与被审计模块分歧 |
|---|---|---|---|---|---|
| 20141231 | 2,345 | **100.0000%** | 0 | 0.00 | 0 |
| 20151231 | 2,545 | **100.0000%** | 0 | 2.6e-12 | 0 |
| 20181228 | 3,551 | **100.0000%** | 0 | 9.2e-12 | 0 |
| 20201231 | 4,119 | **100.0000%** | 0 | 8.3e-12 | 0 |
| 20211231 | 4,669 | **100.0000%** | 0 | 8.0e-12 | 0 |
| 20231229 | 5,329 | **100.0000%** | 0 | 1.3e-11 | 0 |
| 20250630 | 5,405 | **100.0000%** | 0 | 1.5e-11 | 0 |
| **合计** | **27,963** | **100.0000%** | **0** | ~1e-11 | **0** |

- 门要求 >=99%，实测 **100.0000%**；>5% 隔离项为 **0**（无需隔离）。
- 残差量级 ~1e-11 = 浮点噪声，即 `total_mv` 与 `close x total_share` **在供应商侧同源**。
- 单位转换独立核对：`point.total_mv_cny == total_mv * 10000` 全量成立（万元 → CNY，H2）。

**结论：G-C PASS，且是四道门中证据最硬的一道。**

---

## 5. 边界逐条审查

### H1 — 不得用 `ann_date` 代 `f_ann_date` ✅ 且**已量化其代价**

代码层：`resolver.resolve_as_of` 只比较 `f_ann_date`（L66/L78-79），`codes.FactVersion`
docstring 明写禁令。**但本次未止于读代码，而是实测替换后的后果：**

```bash
.venv/bin/python docs/test-reports/B109-holdout/f003_h1.py
# 形成日 20220630 / 2021FY，检验 5586 只
#   identical: 5361
#   NOT_YET_PUBLISHED->RESOLVED: 171      ← ★前视泄漏
#   RESOLVED->FACT_VERSION_AMBIGUOUS: 53
#   NOT_YET_PUBLISHED->FACT_VERSION_AMBIGUOUS: 1
```

★**最重要的一条**：改用 `ann_date` 会让 **171 只（3.06%）** 证券在形成日
**凭空「变得可见」** —— 它们当时尚未披露（`NOT_YET_PUBLISHED`），却因修正行的
`ann_date` 沿用首版日期而被判为「当时就知道」。**这是教科书式的前视偏差注入，
且不会报错、不会 fail-closed。** 另有 54 只被打成 `AMBIGUOUS`（fail-closed，危害较小）。

「静默返回错值」实测为 **0** —— 危害形态不是错值，而是**多出 171 条本不该存在的观测**。
H1 这条硬约束**由本次实测独立证成**，非仅照抄 spec。

### H2 — 分母非流通市值、非当前股本×历史价 ✅

- `marketcap.py` 用 `daily_basic.total_mv` + `total_share`，身份复算 `close x total_share`（§4）。
- **实测反证不可互换**：若误用 `circ_mv` 做同一身份校验，仅
  **33.7%（790/2,345，2014）~ 41.6%（2,250/5,405，2025）** 能通过 ——
  即约 **六成证券的流通市值 ≠ 总市值**，二者代入会系统性污染分母。禁令 #6 由实测支撑。
- 未见「当前股本×历史价」用法：`total_share` 逐交易日取自 `daily_basic`，随日期变化。

### H3 — 宇宙含退市名 ✅

```
universe（2014-06-30 截面，panel-201406.json）:
  total_securities=5866  in_universe=2519  count_not_yet_listed=3265
  count_already_delisted=82  in_universe_delisted_later=225
fetch_reports: stock_basic:L=5528 / stock_basic:D=338 / stock_basic:P=0
```

- 全状态 L/D/P 均拉取（D=338 只退市名在册），禁令 #11 已消除。
- **幸存者偏差实测**：2014-06-30 在市 2,519 只中 **225 只（8.93%）日后退市** ——
  只拉 `list_status=L` 会漏掉这 8.93%。（Generator 报 2013-12-31 为 8.91%，
  日期不同不可直接比对，量级一致；本行数字为**本次自测**。）
- 抽样侧 H3：`select_audit_sample` 的 `seed` 为**无默认值必填参数**（实测省略即
  `TypeError: missing 1 required keyword-only argument: 'seed'`）；
  `git ls-files` 确认仓库内**无 B109 预置 manifest**。Generator 未抽取本次评测样本。

### H4 — 覆盖不足结构化呈现，禁止静默 dropna ✅

漏斗算术**精确闭合**，无静默丢弃：

```
universe_size=2519  panel_rows=2519  no_record_at_all=0
usable(2298) + drop_reasons 合计(221) = 2519 = panel_rows        ✓
drop_reasons: TOTAL_MARKET_CAP_MISSING=220, FACT_MISSING=1
usable/universe = 91.2267%（与产物自报 91.2267% 一致）
```

### H5 — 未碰生产代码 ✅

```bash
git log --name-only --pretty=format:"" e9df93f~1..HEAD | sort -u | grep -E "^(trade|workbench)/"
# （空）
```

B109 全部改动落在 `scripts/research/ashare_pit/`、`tests/unit/`、`docs/`、状态机 JSON。
未改策略默认值、未出 E/P 或收益、未动 readiness flag / `DATA_NO_GO`。

### H6 — 凭据边界 ✅

| 检查 | 命令 | 结果 |
|---|---|---|
| `.env.local` 未入仓 | `git ls-files \| grep env.local` | 空 |
| 已被 gitignore | `git check-ignore -v .env.local` | `.gitignore:6:.env.*` |
| 文件权限 | `ls -l .env.local` | `-rw-------`（600） |
| token 从未进入 git 历史 | `git log -S"$TOK" --all` | 空 |
| token 不在工作区任何文件 | `grep -rl "$TOK" .`（排除 .git/.venv/.env.local） | 空 |
| token 不在本次验收产物 | `grep -rl "$TOK" <scratchpad>` `docs/ scripts/ tests/ .auto-memory/` | 空 |
| 读取路径唯一 | `vintage_probe.load_token()` | 只读 `.env.local`，缺失即 raise，无默认回退 |

---

## 6. 跨批次头条发现的独立复核：Tushare 单次调用静默截断

B109 把该发现写进了 `.auto-memory/project-status.md` 与 4 处 docstring，是本批次
影响面最大的结论。**本次未采信 Generator 数字，而在另一个期次上独立复现：**

```bash
.venv/bin/python docs/test-reports/B109-holdout/f003_truncation.py
# 单次调用 rows = 9000   looks_truncated=True
# 分页    rows = 10740   pages=3  failures=[]
# 漏掉 1740 行 (16.20%)
#   update_flag=0: 单次 3709 / 分页 5209 → 漏 28.8%
#   update_flag=1: 单次 5291 / 分页 5531 → 漏  4.3%
```

- **确证**：单次调用返回**恰好 9000 行**，不报错、不抛异常、不置标志位。
- **确证截断非均匀**：本次在 **2021FY**（Generator 用的是 2022FY）实测
  `flag=0` 漏 **28.8%** vs `flag=1` 漏 **4.3%** —— 比 Generator 报的 18.7%/5.2% **更悬殊**。
  被砍掉的确实富集 vintage 记录。
- 旁证：本次 20 个 holdout 期次里 **15 个超过单页**（`fetch-reports.json` 逐期留痕）。

**结论：该发现属实，且严重性不低于 Generator 的描述。`fetch.py` 的分页 + 触顶守卫是必要的。**

---

## 7. 复核过的 Generator 声称（全部自测复现）

| 声称 | 来源 | 本次实测 | 判定 |
|---|---|---|---|
| 2014-06-30 面板可用率 91.23% | F001 | **91.2267%** | ✅ 复现 |
| 2014 有 8.7% 缺 `total_mv` | F001 | **220/2519 = 8.73%** | ✅ 复现 |
| 2014 面板 `NOT_YET_PUBLISHED = 0` | F001 | drop_reasons 中**无该码 = 0** | ✅ 复现 |
| 2014 分子侧只掉 1 只 | F001 | `FACT_MISSING = 1` | ✅ 复现 |
| 报告滞后中位 91 天 | F001 | `median_days = 91`（p90=91, max=273） | ✅ 复现 |
| PIT 单测 73 例绿 | F001 | `73 passed in 0.34s` | ✅ 复现 |
| 全量测试零回归 | F002 | `1620 passed in 175.95s` | ✅ 复现 |
| ruff 净 | F001/F002 | `All checks passed!` | ✅ 复现 |
| 分母身份 100% 通过 | F002 | 27,963 证券-日 **100.0000%** | ✅ 复现（且样本远大于其口径） |
| 可裁定率约 16.7%，G-A 效力弱 | F002 前置警告(1) | 实测 **18.5%**，效力问题属实（见 I1） | ✅ 属实 |
| PDF 下载 + freeze 路径未验证 | F002 前置警告(2) | **本次执行成功 119/119** | ✅ 属实 → **已解除** |
| `select_audit_sample` seed 无默认 | F002 前置警告(3) | `TypeError` 实测确认 | ✅ 属实 |

**Generator 的三条前置警告全部属实**，未发现夸大或掩饰。

---

## 8. 缺陷清单

### D1（MEDIUM）`resolver.py` 模块 docstring 仍把**已作废数字**当作设计依据陈述

**文件：** `scripts/research/ashare_pit/resolver.py:8,13`

```
L8 : 依据：410 个已知修订中 **98.8%** 可用该语义正确还原当时可见的版本；
L13: Tushare 的 f_ann_date 已经承载了「市场可知时间」这一轴，而修订率只有 0.47%–0.88%。
```

**问题：** 同一仓库的 `pipeline.py:259` 明确写着
「F001 原区间 **0.47%-0.88% 已作废** —— 探针走单次调用被静默截断」，
`REVISION_RATE_BOUNDS` 也已更新为 `(0.00515, 0.01325)`。
但 **as-of resolver 这个核心模块的设计理由，至今仍引用被本批次亲手作废的那个区间**。
可重建性 98.8% 亦为旧值（F001 重测为 99.2%）。

**为什么算缺陷而非文字瑕疵：** 这正是 Generator 自己在 F002 里识别并处理过的失败模式 ——
其 completed_note 写道「**撤回**硬编码 `REVISION_RATE_BOUNDS`……留已知偏低的数比留空更危险，
**下游会当已验证事实引用**」。同一判断适用于 docstring，但 `resolver.py` 被漏掉了。
读 `resolver.py` 的人会把 0.47%–0.88% 当作现行实测结论 —— 而它已被证明是截断伪影。

**修复建议：** 把 L8 的 98.8% 更正为 99.2%，L13 的区间更正为 0.515%–1.325% 并附
「只取自可信窗口 2018-2021」的限定（与 `pipeline.py` 口径一致），或直接引用
`REVISION_RATE_BOUNDS` 常量避免二次漂移。

---

### D2（MEDIUM）acceptance 明写的「替换 B076」只交付了替代品，旧违禁路径未退役

**acceptance F002(2) 原文：** 「**替换 B076 的流通市值反推**
(`scripts/research/b076_fetch_pit_marketcap.py:83` 用 `close*volume*100/turn`
反推的是流通市值，违上游禁令 #6)」

**实测现状：**

```bash
git log --oneline -1 -- scripts/research/b076_fetch_pit_marketcap.py
# e6cc2c4 feat(B076-F001): ...        ← B076 时期，B109 全程未触碰
grep -n "deprecat|B109|已替换" scripts/research/b076_fetch_pit_marketcap.py
# （无匹配）
```

- `circ_mv_from_bar()`（`close*volume*100/turn` 反推流通市值）**原样存活**，
  且**仍被 `tests/unit/test_b076_size_fetch.py` 的 6 个断言覆盖并通过**。
- 该脚本**没有任何弃用标记**，不指向 B109 的 `marketcap.py`。
- 后果：违反禁令 #6 的路径在仓库里**可达、有绿色测试背书、且无警示**。
  未来 agent 检索「market cap」会同时命中新旧两条，无从判断哪条被禁。

**「替换」被实现为「新增一个更好的」，而非「让旧的不再可用」。**

**修复建议（二选一，均不违 H5 —— 该脚本是 research 脚本非生产代码）：**
(a) 在 `b076_fetch_pit_marketcap.py` 模块 docstring 与 `circ_mv_from_bar` 上加显式弃用警示，
指明违禁令 #6、指向 `scripts/research/ashare_pit/marketcap.py`；或
(b) 直接删除该脚本与其测试（B076 signoff 已归档，历史可从 git 取回）。

---

### I1（异议，非缺陷）G-A 门的统计效力不足以支撑其字面阈值 → 见 §2.6

**须 Planner/用户裁定，Generator 无法通过改代码解决。**

---

## 9. 未验证项清单（B108 E01 纪律：被挡住 ≠ 已验证）

| 项 | 状态 | 说明 |
|---|---|---|
| `panel_cli` 长区间（多年连续月）运行 | **未验证** | 本次只跑 2014-06 单月（+ Generator 跑过 2023-09/10）。长区间的 API 成本与稳定性未测。 |
| `namechange` / `name_as_of` 前视防护 | **未验证** | 本次宇宙检查覆盖 L/D/P 状态与退市名，但未独立复核 `name_as_of` 的 as-of 正确性（F002 声称实测 `002656.SZ`，本次**引用未复核**）。 |
| 2016/2017/2019/2022 等未抽样年份的对拍 | **未验证** | holdout 候选池只含 2015/2018/2021/2023/2025 五个年份（B108 遗留的池构成），其余年份无对拍证据。 |
| `FACT_VERSION_AMBIGUOUS` 的真实触发 | **未观测** | 本次所有实测截面该计数均为 0，fail-closed 分支只有单测覆盖，未在真实数据上触发过。 |
| `income_vip` 以外接口的截断行为 | **部分** | 仅复核 `income_vip`；`namechange` 的 10000 行截断为**引用未复核**。 |
| G-A 在 >=299 可裁定样本上的结论 | **未验证** | 见 I1，本次证据只支持 >=97.05%（95% 置信）。 |

---

## 10. 结论

**四道硬门 G-A / G-B / G-C / G-D 全部通过；六条边界 H1–H6 全部守住。**
被审计方（Tushare `n_income_attr_p` + `daily_basic.total_mv`）在本次全部
可对拍的 100 份样本上**未被发现任何一处错误**，5 份不一致经人工裁定**全部归因于巨潮 parser**。
as-of 语义与修订不变性在真实修订数据上 12/12 正确。分母身份在 27,963 证券-日上 100.0000% 成立。

**但按 harness 规则判 FAIL → `fixing`**，原因是两条 MEDIUM 缺陷：
- **D1** 核心模块 `resolver.py` 的设计依据仍陈述本批次亲手作废的数字（下游会当已验证事实引用）；
- **D2** acceptance 明写的「替换 B076」未完成 —— 违禁令 #6 的旧路径仍可达、有绿测背书、无警示。

两项均为小改动，建议一轮 fix 后 reverify。**I1（G-A 门的措辞与阈值）须用户/Planner 裁定，
不计入 Generator 的 fix 范围。**

> ★本批次的 `DATA_NO_GO` 裁定未被改变，本报告亦不构成对 A 股纯 E/P 可用性的任何背书。

---

## 附：全部验收产物

`docs/test-reports/B109-holdout/`

| 文件 | 内容 |
|---|---|
| `manifest.json` | seed=570193 抽样结果 119 份 + 逐层覆盖 |
| `pdf-freeze.json` | 119 份 PDF 的字节 sha256（E11 冻结） |
| `audit-summary.json` / `audit-detail.json` | G-A 对拍汇总与逐份明细 |
| `supplement.json` | 单源/冲突层的补充对拍 |
| `gb-results.json` | G-B 修订前后 + 不变性指纹 |
| `gc-results.json` | G-C 七日身份校验 + H2 circ_mv 反证 |
| `h1-decomposition.json` | H1 前视泄漏分解 |
| `fetch-reports.json` | 20 期分页留痕 |
| `panel-201406.json` | G-D 漏斗 + 12 项强制披露 |
| `f003_*.py`（9 个） | 全部可重跑验收脚本 |

**PDF 原文（119 份）留在本机 scratchpad，未入仓**（体积 + 版权；与 B108 `data/research/` 未入仓一致）。
凭 `manifest.json` 的 URL + `pdf-freeze.json` 的 sha256 可完整复现。
