# B108 — 巨潮 PDF parser 自检重构 + 独立样本重评：F003 验收签收报告

- **批次**：B108-cninfo-parser-selfcheck
- **Feature**：F003（`executor: codex`）
- **验收人**：独立无实现上下文 agent（代 Codex，B079-B106 先例）
- **日期**：2026-07-20
- **裁定**：**FAIL** → `progress.json.status = fixing`

---

## 0. 结论摘要

| 项 | 结果 |
|---|---|
| **硬门 confirmed precision ≥99%** | **无法测量（NOT MEASURABLE）** — CONFIRMED 仅 4/76，acceptance 要求随机抽 ≥20 份人工裁定，样本不足 |
| **CONFIRMED 中 10ⁿ 错误 = 0** | **PASS**（4/4 人工核对全对，无数量级错误） |
| confirmed coverage（只报告不设门） | **5.3%**（4/76） |
| 冲突有效性：误报率 | **40%**（5 份冲突中 2 份是误报） |
| H1（无 sec_code / 数值幅度特例分支） | **PASS** |
| H4（判定逻辑不引用 Eastmoney） | **PASS** |
| H5（未触碰 workbench/ 与策略默认值） | **PASS** |
| **★新发现：F002 联网抽样路径崩溃** | **FAIL** — `sample_cli` 的 `--years` 联网模式 100% 不可用 |
| **★新发现：bug ② 未修复** | **FAIL** — 实测到 ×10⁴ 单位错绑（-5.44 万亿元） |
| **★新发现：bug ④ 修复引入回归** | **FAIL** — 标签重连过度合并，把「营业收入」当成「归母净利润」返回 |
| **★新发现：bug ③ 修复在真实版面上大面积失效** | **FAIL** — 44.7% EXTRACTION_FAILED，主因是表头跨物理行导致列模型建不起来 |

**采购结论：免费源 + 自建 parser 当前状态＝不够用，且差距不是「再修几个 bug」的量级。** 详见 §9。

---

## 1. 执行环境与工具链

```
$ pdftotext -v
pdftotext version 26.03.0                        # /opt/homebrew/bin/pdftotext
$ .venv/bin/python -m ruff check .
All checks passed!
$ .venv/bin/python -m pytest tests/unit/test_ashare_ep_extract.py tests/unit/test_ashare_ep_sampling.py -q
40 passed in 0.11s
$ gh run list --limit 5      # 57eca040 Python CI = success（B108 F002 HEAD）
```

CI 绿、单测全过、ruff 净——**这三项都成立，但它们对本批次要证明的事情几乎没有信息量**（见 §7）。

---

## 2. holdout 抽样（acceptance 1）

### 2.1 ★阻断性发现 B108-E01：F002 的联网抽样路径当场崩溃

按 `sample_cli.py` 模块 docstring 里给 Codex 的**原样命令**执行：

```
$ .venv/bin/python -m scripts.research.ashare_ep.sample_cli \
    --seed 4172639 --years 2015,2018,2021,2023,2025 --quota 1 \
    --exclude-manifest docs/test-reports/ashare-as-filed-data-pilot-2026-07-12.json \
    --out data/research/b108/holdout-manifest.json \
    --provenance-out data/research/b108/holdout-provenance.json

  File "scripts/research/ashare_ep/sample_cli.py", line 97, in discover_candidates
    with CninfoClient() as client:
TypeError: 'CninfoClient' object does not support the context manager protocol
```

`CninfoClient`（`scripts/test/ashare_as_filed_data_pilot.py:289`）没有 `__enter__` / `__exit__`。
**F002 唯一一条 F003 必须走的路径，交付时从未被执行过一次。**

这不是偶然：F002 的 `completed_note` 自述「`discover_candidates`(联网路径) 全仓**零调用点**（已 grep 验证）」——
Generator 把「没有调用点」当成 H3 合规的证据，但它同时也意味着**这段代码零执行覆盖**。
H3（Generator 不得抽样）是对的，但它要求的补偿动作是「联网路径必须有 mock/契约测试」，F002 没有做。

**判定：F002 acceptance (1)(3)(4) 的联网部分 FAIL。**

### 2.2 变通与冻结

为不阻塞 F003，Evaluator 自建候选池发现脚本 `scripts/test/b108_holdout_discover.py`（**属 F003 测试域，不是对被验收代码的修改**），
把候选池落盘后仍走 F002 的 `--candidates-json` 离线路径，**保证被验收的分层/seed 抽样逻辑本身仍在测试之中**。

```
$ .venv/bin/python -m scripts.test.b108_holdout_discover 2015,2018,2021,2023,2025 Q1,H1,Q3,FY \
      data/research/b108/candidates.json
2015 Q1: rows=360 eligible=311
...
2025 FY: rows=360 eligible=168
candidates: 4833 -> data/research/b108/candidates.json      # 耗时 4m30s
```

```
$ .venv/bin/python -m scripts.research.ashare_ep.sample_cli \
    --seed 4172639 --quota 1 \
    --candidates-json data/research/b108/candidates.json \
    --exclude-manifest docs/test-reports/ashare-as-filed-data-pilot-2026-07-12.json \
    --out data/research/b108/holdout-manifest.json \
    --provenance-out data/research/b108/holdout-provenance.json
manifest: data/research/b108/holdout-manifest.json
sha256:   aa0a35a6e190ea163c8b51d9b313538d29fdcdb79afbe17b47ff6e633a264856
selected: 76 / 候选池 4833 / 排除 50
```

**冻结记录（评测开始之前落盘）：**

| 项 | 值 |
|---|---|
| seed（Evaluator 自选，未告知实现方） | `4172639` |
| 样本数 | **76**（≥60 ✅） |
| manifest 规范序列化 sha256（CLI 自报） | `aa0a35a6e190ea163c8b51d9b313538d29fdcdb79afbe17b47ff6e633a264856` |
| manifest **文件** sha256（`shasum -a 256`） | `137db270f829b0ba557e46cdda28c4f7ceeae7c8163eae952f725457fb5c1f2d` |
| 与已烧掉 50 份的交集 | **0** ✅（H2 满足） |
| `--exclude-manifest` 解析出的 ID 数 | **50** ✅（独立复核 `load_excluded_ids`，与 F002 自述一致） |

冻结产物入 git：`docs/test-reports/B108-holdout/holdout-manifest.json`、`holdout-provenance.json`。

### 2.3 独立复核 F002 的确定性主张（acceptance 2）

```
$ PYTHONHASHSEED=99 .venv/bin/python -m scripts.research.ashare_ep.sample_cli \
      --seed 4172639 ... --out /tmp/holdout-rerun.json
sha256:   aa0a35a6e190ea163c8b51d9b313538d29fdcdb79afbe17b47ff6e633a264856
$ cmp data/research/b108/holdout-manifest.json /tmp/holdout-rerun.json && echo BYTE-IDENTICAL
BYTE-IDENTICAL ✅
```

**确定性主张成立**（跨进程、不同 `PYTHONHASHSEED`，逐字节相同）。

### 2.4 抽样层面的诚实披露（不掩盖）

1. **候选池被翻页上限截断。** 每个 (年份 × 报告类型) 窗口 `rows_seen` 全部恰好 = 360 = 12 页 × 30，
   说明 **20 个窗口全部撞到翻页上限**，候选池是巨潮返回顺序的前 360 条而非全集。
   层内抽样是 seed 化随机的，但**层的候选池本身带有巨潮返回顺序的选择偏差**。
   （F002 自身的 `_MAX_QUERY_PAGES = 8` 只会更严重：8 页 = 240 条。）
2. **空层被静默跳过。** 期望 5 年 × 4 板块 × 4 类型 = 80 层，实得 76 层。缺失 13 层里
   8 层是「科创板 2015/2018 尚不存在」（合理），另 5 层（2015/2018 创业板 Q3、2021 创业板 FY/H1、2021 深主板 H1）
   是候选池截断所致。`coverage_report` 只遍历 `candidates ∪ selected` 中出现过的层，
   **候选数为 0 的层根本不会进入报表，因此「未达配额」告警一条都没打印**。
   F002 自称的 no-silent-caps 保证对「整层缺失」这一最严重的缺口失效。
3. **`board=UNKNOWN` 有 9 份（11.8%）**，是 B 股（`200xxx`/`900xxx`）与北交所（`839680`）。
   `classify_board` 返回 `UNKNOWN` 后，它们**仍被当作一个独立板块参与分层**，
   等于凭空多出第 5 个板块。对本次验收反而有利（B 股旧版面正好压测 bug ④），但属未预期行为。

### 2.5 冻结样本构成

| 维度 | 分布 |
|---|---|
| 年份 | 2015: 14 / 2018: 13 / 2021: 14 / 2023: 17 / 2025: 18 |
| 板块 | 沪主板 20 / 深主板 19 / 创业板 16 / 科创板 12 / UNKNOWN(B股+北交所) 9 |
| 报告类型 | Q1: 21 / Q3: 19 / FY: 18 / H1: 18 |

---

## 3. 评测结果（acceptance 2 — 分层报告）

76 份全部下载成功、`pdftotext -layout` 全部成功，**PIPELINE_ERROR = 0**（无因限流/超时导致的缺失）。

```
$ .venv/bin/python -m scripts.test.b108_holdout_eval \
      data/research/b108/holdout-manifest.json data/research/b108/eval-results.json
$ .venv/bin/python -m scripts.test.b108_holdout_report data/research/b108/eval-results.json
```

### 3.1 状态分布

| 状态 | N | 占比 |
|---|---|---|
| EXTRACTION_FAILED | 37 | **48.7%** |
| SINGLE_SOURCE_UNCONFIRMED | 30 | 39.5% |
| SOURCE_CONFLICT | 5 | 6.6% |
| **CONFIRMED** | **4** | **5.3%** |
| MAGNITUDE_IMPLAUSIBLE | 0 | 0% |

failure code：`EXTRACTION_FAILED` 34 / `SINGLE_SOURCE_UNCONFIRMED` 30 / `SOURCE_CONFLICT` 5 / `LABEL_NOT_FOUND` 3。

### 3.2 按年份

| 年份 | N | CONFIRMED | SINGLE | CONFLICT | FAILED |
|---|---|---|---|---|---|
| 2015 | 14 | **0** | 6 | 0 | 8 |
| 2018 | 13 | 1 | 8 | 2 | 2 |
| 2021 | 14 | 1 | 6 | 0 | 7 |
| 2023 | 17 | 1 | 5 | 3 | 8 |
| 2025 | 18 | 1 | 5 | 0 | 12 |

### 3.3 按板块

| 板块 | N | CONFIRMED | SINGLE | CONFLICT | FAILED |
|---|---|---|---|---|---|
| 沪主板 | 20 | **0** | 8 | 2 | 10 |
| 深主板 | 19 | 2 | 9 | 2 | 6 |
| 创业板 | 16 | 2 | 6 | 0 | 8 |
| 科创板 | 12 | **0** | 3 | 1 | 8 |
| UNKNOWN | 9 | **0** | 4 | 0 | 5 |

### 3.4 按报告类型

| 类型 | N | CONFIRMED | SINGLE | CONFLICT | FAILED |
|---|---|---|---|---|---|
| Q1 | 21 | 3 | 11 | 0 | 7 |
| H1 | 18 | 1 | 4 | 2 | 11 |
| Q3 | 19 | **0** | 12 | 3 | 4 |
| **FY（年报）** | 18 | **0** | 3 | 0 | **15（83.3%）** |

**★ 年报（FY）零 CONFIRMED、83.3% 抽取失败。而年报正是 E/P 研究最需要的报告类型。**
沪主板、科创板、B 股、2015 全年——四个维度上各自零 CONFIRMED。

---

## 4. confirmed precision 人工裁定（acceptance 3）★本批次唯一正确性判据

### 4.1 样本量不足——acceptance 要求无法满足

acceptance (3) 要求「对 CONFIRMED **随机抽 ≥20 份**」。**全体 CONFIRMED 只有 4 份。**
因此改为**全量人工裁定 4/4**（100% 普查，已是可做到的上限），并如实标注统计效力不足。

### 4.2 逐份裁定（Evaluator 直接读 `pdftotext` 文本，不经 parser）

| # | 证券 | 期间 | parser 值 | 原文核对 | 裁定 |
|---|---|---|---|---|---|
| 1 | 300063 广东天龙 | 2018-H1 | `77,113,928.99` | 合并利润表 L2908 = `77,113,928.99`；主要会计数据 L273 = `77,113,928.99`；所有者权益变动表 L6746 同值 | ✅ 正确 |
| 2 | 300495 美康生物 | 2021-Q1 | `20,850,270.43` | 主要会计数据 L106 = `20,850,270.43`；MD&A 变动表 L346 同值（跨行标签「归属于母公司股/东的净利润」已正确重连） | ✅ 正确 |
| 3 | 000046 泛海控股 | 2023-Q1 | `-1,307,800,923.63` | 合并利润表 L684「1.归属于母公司所有者的净利润」= `-1,307,800,923.63`；主要会计数据 L60 同值 | ✅ 正确 |
| 4 | 000002 万科A | 2025-Q1 | `-6,246,208,543.03` | 合并利润表 L586 = `(6,246,208,543.03)`；主要会计数据 L49 同值。**括号负数被正确解析** | ✅ 正确 |

原文摘录见 §附录 A（本报告随附 `docs/test-reports/B108-holdout/eval-results.json` 含每份的 `line_index`，可逐一复查）。

### 4.3 指标

- **confirmed precision = 4/4 = 100.0%**
- **CONFIRMED 中 10ⁿ 数量级错误 = 0** ✅（硬门的这一半 PASS）
- **单位解析正确性**：4 份的 `unit` 全部为「元」，与原文一致；括号负数、千分位均正确。

### 4.4 ★为什么这不能判 PASS

`n = 4` 时，「4/4 全对」的 95% 单侧置信下界只有 **47.3%**（`0.05^(1/4)`）：

```
$ python3 -c "import math; print(0.05**(1/4)); print(math.ceil(math.log(0.05)/math.log(0.99)))"
0.4729...
299
```

**要以 95% 置信断言 precision ≥ 99%（零错误），需要 CONFIRMED 样本 n ≥ 299。**
按本次实测 5.3% 的 coverage 反推，须评测约 **5,681 份文档**才能凑齐。

**因此硬门判定为 `NOT MEASURABLE`，不是 PASS。** 观测到的 100% 与「precision 很高」相容，
也与「precision 只有 60%」相容——本次数据无法区分。把 4/4 写成「达标 ≥99%」会是 B104/B105 式的幻觉结论。

---

## 5. 冲突有效性检查（acceptance 4）

全部 5 份 `SOURCE_CONFLICT` 逐条人工裁定：

| # | 证券 | 期间 | 两个候选值 | 真值（人工读原文） | 裁定 |
|---|---|---|---|---|---|
| 1 | 002605 姚记科技 | 2018-H1 | S2=`44,423,937.08`（L229，主要会计数据）<br>S2=`5,132.83`（L1266） | `44,423,937.08` | **❌ 误报**。主值正确；第二个命中来自**业绩预告叙述段**「2017 年 1-9 月归属于上市公司股东的净利润（**万元**）」——既非本期、又非同口径、单位还是万元 |
| 2 | 002382 蓝帆医疗 | 2018-Q3 | S2=`260,606,202.35`（L86，年初至报告期末）<br>S2=`20,086.43`（L1818） | `260,606,202.35` | **❌ 误报**。同上：第二个命中是「2017 年度归属于上市公司股东的净利润（万元）」业绩预告文字 |
| 3 | 600900 长江电力 | 2023-H1 | S1=`81,875,582,795.77`（L7216）<br>S2=`30,974,895,019.62`（L195） | `8,882,067,760.22` | **✅ 真抓到**。**两个源都错**：S1 把「调整后期初未分配利润」的 818.8 亿当成归母净利润；S2 把「营业收入」309.7 亿当成归母净利润。交叉验证阻止了两个错值出厂 |
| 4 | 603027 千禾味业 | 2023-Q3 | S2=`48.45`（L36）<br>S2=`106.61`（L190） | `387,129,258.14` | **✅ 真抓到**。两个候选**都是百分比**（48.45%、106.61%），被当成元金额 |
| 5 | 688185 康希诺 | 2023-Q3 | S2=`92.93`（L42）<br>S2=`-70.49`（L132） | `-985,029,654.47` | **✅ 真抓到**。同上，两个候选都是增减幅度百分比 |

### 5.1 指标

- **真抓到 parser 错误：3/5 = 60%**
- **误报（两源本就不该比 / 主值原本正确）：2/5 = 40%**

### 5.2 解读

40% 的误报率**不是「S1/S2 会计口径本就不同」造成的**（spec §8 风险登记预想的那种），
而是**同一个来源 S2 在文档里命中了叙述性文字**（业绩预告、MD&A 说明段），
被 `crosscheck.py:83` 的「同一来源内部多行取值不一致」判为冲突。
这两份的主值本来是对的，是交叉验证**把正确抽取毁掉了**。

反过来说，3 份「真抓到」里有 2 份（603027 / 688185）暴露的是同一个严重缺陷：
**百分比列没有被排除**——`%` 在表头里而不在单元格里时，`Cell.is_percent` 为 False，
而表头因为跨物理行没能被识别，`_EXCLUDED_HEADERS` 也拦不住。
这两份是「碰巧两个错值互相不等所以被拦下」，**不是设计有效，是运气**。

---

## 6. 边界检查（acceptance 6）

### 6.1 H1 — 无针对具体 sec_code / 数值幅度的特例分支 → **PASS**

```
$ grep -rnE "6[0-9]{5}|0[0-9]{5}|3[0-9]{5}|sec_code\s*==" scripts/research/ashare_ep/*.py
scripts/research/ashare_ep/sample_cli.py:11:  --seed 20260720 --years 2015,2019,2023,2025   # docstring 示例，非逻辑
```

判定代码（`codes/layout/sources/crosscheck`）中**零 sec_code 特例**。全部数值常量：

| 常量 | 值 | 性质 | 裁定 |
|---|---|---|---|
| `_UNIT_SCALE` | 元/千元/万元/百万元 = 1/1e3/1e4/1e6 | 语言事实 | ✅ |
| `DEFAULT_TOLERANCE` | `0.001` | spec §3.2 明文规定的 0.1% | ✅ |
| `_MIN/_MAX_PLAUSIBLE_SHARES` | `1e6` / `1e12` | 作用在**推算股本**上 | ✅ 见 §7.1 |
| `_MIN_SENTINEL_EPS` | `0.01` | 除零保护 | ✅ |

四类 bug 的修法判据确实全部锚在表头文字与字符列区间上，没有出现「数值太小就跳过」这类幅度阈值。
**H1 合规。**（H1 合规 ≠ 修对了，见 §7。）

### 6.2 H4 — 判定逻辑不引用 Eastmoney → **PASS**

```
$ grep -rniE "eastmoney|east_money|raw_reports|em_|akshare|baostock" scripts/research/ashare_ep/
  (none)
```

本报告的 PASS/FAIL 判据同样只来自「Evaluator 直读 PDF 文本」，未引入任何外部对照物。

### 6.3 H5 — 未触碰生产代码 → **PASS**

```
$ git diff --name-only HEAD~2 HEAD
.auto-memory/project-status.md
features.json
progress.json
scripts/research/ashare_ep/{codes,crosscheck,layout,manifest,sample_cli,sampling,sources}.py
tests/unit/test_ashare_ep_{extract,sampling}.py
```

`workbench/` 零改动，策略默认值零改动，readiness flag 零改动。**H5 合规。**

---

## 7. ★对三处「实现方偏离 spec」的独立裁定（团队要求第七步）

### 7.1 偏离 (1)：S3 哨兵用 `|利润| / |基本EPS| → 推算股本 ∈ [1e6, 1e12]` 取代 spec §3.1 的「基本EPS × 期末股本」

**裁定：设计方向 ACCEPT，但实现位置 REJECT（是本批次最严重的浪费之一）。**

**(a) 是不是变相的「数值幅度阈值」（H1 禁止）？→ 不是。**
H1 与 spec §3.4 禁止幅度阈值，针对的是**附注列识别**（禁止「数值太小就当附注」）。
而 spec §3.1 本身就把 S3 定义成「**仅作数量级哨兵**」——数量级判断天然就是幅度判断。
关键在于判据作用在**推算股本**（一个有外部结构约束的量）上，而不是作用在利润值本身，
且区间来自 A 股股本宇宙的结构性事实，与本批次任何样本无关。**不构成 H1 违规。**

**(b) 实际能抓住多少真实错误？→ 已实测量化（注入式变异测试）。**
取 76 份中能抽到基本 EPS 且基线判 plausible 的 **16 份**，对其注入 10ⁿ 单位错误：

| 注入倍数 | 放大方向检出率 | 缩小方向检出率 |
|---|---|---|
| ×10 | 1/16 = **6%** | 0/16 = **0%** |
| ×100 | 2/16 = 12% | 1/16 = 6% |
| **×10³（千元误绑）** | 3/16 = **19%** | 13/16 = 81% |
| **×10⁴（万元误绑）** | 15/16 = **94%** | 14/16 = 88% |
| ×10⁸（亿元误绑） | 16/16 = 100% | 16/16 = 100% |

结论：对 pilot 里 `601113` 那类 **×10⁴ 错误检出率 88-94%**，对 `688981`/`688235` 那类
**×10³ 错误只有 19%（放大方向）**。相比 spec 原设计（用真实期末股本，可捕捉 ×10 级偏差），
实现版**确实降低了灵敏度**，但降低的区间（×10 / ×100）在中文财报里不是自然发生的单位混淆，
**实务损失有限**。理由（季报正文常无期末股本）成立。

**(c) ★但实现位置是错的——哨兵对 39.5% 的语料结构性不可达。**
`crosscheck.py:92` 在 `if not s1_values or not s2_values:` 处**提前返回** SINGLE_SOURCE_UNCONFIRMED，
S3 哨兵（L117-129）**只在已经 CONFIRMED 的路径上运行**。
也就是说：**最需要独立校验的单源结果（30/76 = 39.5%，无任何交叉确认），恰恰完全没有哨兵保护。**

实测代价——若把现成的 S3 应用到单源结果，**当场就能抓到 6 份错抽**：

| 证券 | 抽出值 | 推算股本 | 判定 |
|---|---|---|---|
| 002670 | `-5,442,728,186,300.00` | 1.94e13 | 区间外 → 会被否决（真值 `-544,272,818.63`，×10⁴ 错误） |
| 688159 | `77.92` | 9.05e-7 | 区间外 → 会被否决（百分比误抽） |
| 603027 | `48.45` | 6.28e-1 | 区间外 → 会被否决 |
| 688185 | `92.93` | 1.24e-7 | 区间外 → 会被否决 |
| 600171 | `-30.85` | 9.26e-1 | 区间外 → 会被否决 |
| 688065 | `51.46` | 2.92e+0 | 区间外 → 会被否决 |

**Generator 造了一个有效的哨兵，然后把它装在了唯一不需要它的地方。**

### 7.2 偏离 (2)：manifest 不含生成时间，拆成 `provenance.json` 旁文件

**裁定：ACCEPT（合理的实现精化）。**

理由成立且实测验证：时间戳与 acceptance (2)「同 seed 两跑逐字节相同」在逻辑上不可兼得，
硬塞进去只会逼出「比较除时间戳外的部分」这种自我放水的验收口径。
拆分后 acceptance (2) 字面成立（§2.3 已独立复现），acceptance (5) 要求的「生成时间」字段
仍然存在于 `provenance.json`，信息零丢失。这是把两个冲突的要求正确分解，不是降低标准。

### 7.3 偏离 (3)：manifest 不含 `pdf_sha256`

**裁定：ACCEPT，但附带一条必须补的缺口。**

「抽样阶段不下载 PDF 所以 sha256 不可得」属实，且 acceptance (5) 原文写的就是 `pdf_sha256(如可得)`，
偏离在字面授权范围内。

**但缺口是真实的**：spec §4「输出冻结 manifest：… `pdf_sha256`」的目的是**锁定被评测的字节**，
防止「同一 announcement_id 指向的 PDF 被替换后无人察觉」。目前**没有任何环节**冻结 PDF 字节——
F002 说属于 F003，而 F003 的 acceptance 里没写这一条，于是它掉进了两个 feature 的缝里。
本次 Evaluator 已把 76 份 PDF 落盘保留（`data/research/b108/pdf/`，未入 git 因体积），
**建议在 fixing 阶段补一条：评测 harness 下载后须产出带 `pdf_sha256` 的二级冻结 manifest。**

---

## 8. ★bug ④（旧模板断行）到底修没修好（团队要求第八步）

实现方明确自认这一项**本批次内无法自证**。本次 holdout 给出了证据——**答案是：修过头了，引入了比原 bug 更危险的回归。**

### 8.1 直接证据：标签重连把两行不同的表格行合并成一行

`300432 2023-Q3` 原文：

```
  47| 营业收入（元）        1,856,031,630.20    -8.37%    4,178,189,526.43    -11.54%
  48| 归属于上市公司股东
  49|                  -79,024,133.16    -132.14%    -402,092,072.05    -167.04%
  50| 的净利润（元）
```

`build_rows` 的产出：

```
Row(line=47) label='营业收入（元）归属于上市公司股东的净利润（元）'
             cells=['1,856,031,630.20','-8.37%','4,178,189,526.43','-11.54%',
                    '-79,024,133.16','-132.14%','-402,092,072.05','-167.04%']
```

标签被拼成 `营业收入（元）` + `归属于上市公司股东的净利润（元）`，两行的单元格被**合并进同一个 Row**，
且**营业收入的单元格排在前面**。`_matches` 看到标签里含「归属于上市公司股东的净利润」→ 判为 S2 命中；
`_row_value` 在目标列取 `candidates[0]` → 拿到 **营业收入的 `4,178,189,526.43`**，
而不是归母净利润的 `-402,092,072.05`。

**这正是本批次立项要消灭的「自信的错值」——而且比原 bug 更隐蔽：
返回的是一个数量级完全合理、符号也可能合理的营业收入。**

### 8.2 这个回归的规模

在 30 份 SINGLE_SOURCE_UNCONFIRMED（这些是**会带值返回给调用方**的）中，
仅从匹配行即可判定为错的至少 **13 份（43%）**：

| 错误类型 | 样本 | 数量 |
|---|---|---|
| 返回**营业收入**而非归母净利润 | 601788、002506、300432、000595、300472、600847、000656 | 7 |
| 返回**百分比**而非金额 | 688159(`77.92`)、600171(`-30.85`)、688065(`51.46`) | 3 |
| 返回**利润总额/净利润**（未归母） | 900953 | 1 |
| **×10⁴ 单位错绑** | 002670(`-5,442,728,186,300.00`) | 1 |
| 从会计政策变更附注取数 | 300028 | 1 |

### 8.3 旧模板 / 繁体 / B 股专项（团队指定重点）

holdout 中 2015 年 14 份 + B 股/北交所 9 份：

- **2015 全年：CONFIRMED = 0**，8/14 EXTRACTION_FAILED。
- **B 股（`200xxx`/`900xxx`）+ 北交所：CONFIRMED = 0**，5/9 EXTRACTION_FAILED。
- `200054`（重庆建设 2015 年报，旧版面）：标签**确实被成功重连**为
  `'归属于上市公司股东的净利润（元）'`，cells 也取到了 4 个数——
  **bug ④ 想修的「断行导致失配」这一步确实修好了**，但随后死在表头识别（见 §8.4）。

**裁定：bug ④ 的「重连断行标签」目标达成了（`200054`/`300495` 都是正面证据），
但重连缺少「不得跨越已完成的表格行」的边界条件，导致过度合并，净效果是负的。**

### 8.4 连带发现：bug ③ 的修法在真实版面上大面积失效

对 37 份 EXTRACTION_FAILED 逐份归因：**92%（34/37）不是找不到标签，而是找到了行却取不出值。**

| 归因 | 出现次数 |
|---|---|
| **找不到表头行（`find_header_columns` 要求同一物理行内 ≥2 个表头词）** | **76** |
| 行内无可用数值（数字在别的物理行 / 被 `%` 吃掉） | 39 |
| 目标列内无数值（列区间对不齐） | 1 |
| 表头存在但无一列匹配目标语义 | 1 |

根因：**真实财报的表头本身就是跨物理行的。** `000410 2025-H1`：

```
 176|                          上年同期              本报告期比上年同期增减
 177|          本报告期
 178|                     调整前          调整后          调整后
```

`find_header_columns` 只认 L176，得到 `headers=['上年同期','本报告期比上年同期增减']`——
**真正需要的「本报告期」在 L177，从未进入列模型**。`select_target_column` 于是全被 `_EXCLUDED_HEADERS`
排除 → 返回 None → `COLUMN_AMBIGUOUS`。

**bug ③ 把「硬编码列号」换成了「表头文字匹配」，方向正确，但表头识别器只处理单物理行，
比它替换掉的硬编码方案更脆。这是 48.7% 抽取失败率的第一主因。**

---

## 9. ★采购结论：免费源 + 自建 parser 够不够用

### 9.1 结论：**不够用。且当前证据不足以判断「修好之后够不够用」。**

| 维度 | 实测 | 研究可用性 |
|---|---|---|
| 可用数据产出率（CONFIRMED） | **5.3%** | 每 100 份年报/季报只拿到 5 个可信数字 |
| **年报（FY）产出率** | **0/18** | **E/P 研究最核心的报告类型，零产出** |
| 沪主板 / 科创板 / B 股 / 2015 年 | 各 0 CONFIRMED | 存在系统性的整块盲区，不是随机缺失 |
| 带值返回但实际错误（SINGLE_SOURCE 中） | ≥13/30 = **43%** | 若下游误用单源值，污染率 4 成 |
| 交叉验证误报率 | **40%** | 交叉验证本身在毁掉正确抽取 |
| precision 硬门 | **无法测量**（n=4） | 需 ~5,681 份文档才能达到统计效力 |

### 9.2 差距量化（作为采购论证的直接输入）

1. **数量差距**：要以 95% 置信断言 precision ≥99%，需 **CONFIRMED n ≥ 299**。
   按当前 5.3% coverage，须评测约 **5,681 份 PDF**。按本次实测速率
   （76 份 ≈ 22 分钟下载+解析，候选池发现另需 4.5 分钟/20 窗口），
   5,681 份约需 **28 小时**纯机时——**这还只是「测一次 precision」的成本，不含修 parser 的迭代**。
2. **质量差距**：即便 coverage 修到 100%，本次暴露的三个缺陷（表头跨行、标签过度合并、单位跨表）
   都属于「返回**看起来合理**的错值」，而不是「返回空值」。这类错误**无法靠提高覆盖率消除**，
   只能靠更强的版面理解。
3. **本批次核心命题的验证结果**：立项假设是「13 份失败里 ≥10 份是本仓 parser bug，修好就能过」。
   本次在**全新 holdout** 上的实测说明：**parser bug 的真实规模远大于原估计**，
   原 pilot 的 65.789% 一致率是在 38 份「能抽出值可比」的子集上算的，
   而本次 76 份里能被交叉确认的只有 5.3%——**原 65.789% 这个数字本身建立在一个高度筛选过的分母上，
   不能代表 parser 的真实能力。**

### 9.3 建议（不越权，仅供用户决策）

- **不建议**据此直接判「免费源天花板已到、必须采购」——本次测的是**这一版实现**，不是免费源的上限。
  三个主缺陷都有明确、结构化的修法，且都不需要外部数据。
- **建议**在 fixing 阶段先修 §10 的 E02/E03/E04 三条，再用**同一份冻结 holdout（seed `4172639`）复评**。
  复评是零边际成本的（PDF 已落盘），能直接给出「修好之后够不够用」的答案。
- **在拿到复评数字之前采购 Tushare，等于用钱买一个还没有被测量的差距。**
  ★同时提醒：`.auto-memory` 记载 **Tushare 在本仓从未实测**（零集成、无 token），
  采购论证目前同样缺少一手证据——**两边都还没测过**。

---

## 10. 缺陷清单（交 fixing 阶段）

| ID | 严重度 | 缺陷 | 证据 |
|---|---|---|---|
| **E01** | **阻断** | `sample_cli` 联网抽样路径崩溃：`with CninfoClient()` 但该类无上下文管理器协议 | §2.1 |
| **E02** | **严重** | `build_rows` 标签重连跨越已完成的表格行，把「营业收入」等相邻行的单元格并入目标行，返回**看似合理的错值** | §8.1、§8.2（≥13/30 单源结果错误） |
| **E03** | **严重** | `find_header_columns` 只识别单物理行表头，真实财报表头跨行 → 列模型建不起来 → 48.7% EXTRACTION_FAILED | §8.4（76 次命中） |
| **E04** | **严重** | `resolve_unit` **没有在表边界处停止**：`_TABLE_SCOPE_LOOKBACK_LINES=12` 只用于给 `unit_source` 打标签，搜索范围实际是全文档向上；`_row_value` 又完全忽略 `unit_source`，照常乘倍数 | §10.1 |
| **E05** | **严重** | S3 数量级哨兵只在 CONFIRMED 路径运行，对 39.5% 的单源结果结构性不可达；若接上可当场抓到 6 份错抽 | §7.1(c) |
| **E06** | 中 | 百分比列未被排除：`%` 在表头而不在单元格时 `is_percent=False`，`_EXCLUDED_HEADERS` 又因表头跨行失效 → 把增减幅度当金额 | §5.2（603027 / 688185 / 688159 / 600171 / 688065） |
| **E07** | 中 | S1/S2 会命中业绩预告、MD&A 等**叙述性文字**，触发「同一来源内部多行不一致」→ 40% 冲突误报，毁掉本来正确的抽取 | §5（002605 / 002382） |
| **E08** | 中 | `coverage_report` 不报告「候选数为 0 的整层」，no-silent-caps 保证对最严重的缺口失效 | §2.4(2) |
| **E09** | 低 | `write_manifest` 写文件时补了 `\n`，但返回的 sha256 是不含 `\n` 的规范串哈希 → CLI 打印的 sha256 与 `shasum -a 256 <file>` **不相等**，恰好在「冻结后核验」这个场景上误导 | §2.2 |
| **E10** | 低 | `classify_board` 把 B 股/北交所归为 `UNKNOWN` 后，`UNKNOWN` 仍作为独立板块参与分层，凭空多出第 5 个板块 | §2.4(3) |
| **E11** | 低 | `pdf_sha256` 冻结在 F002/F003 之间掉缝，目前无任何环节锁定被评测的 PDF 字节 | §7.3 |

### 10.1 E04 复现（Evaluator 直接构造，非样本依赖）

```python
$ .venv/bin/python -c "
from scripts.research.ashare_ep.layout import resolve_unit, unit_scale
lines = ['三、其他重要事项', '   单位：万元', '项目  本期金额  上期金额', '营业收入  1,234.00  1,100.00']
lines += ['', '说明性文字若干。'] * 30
lines += ['合并利润表', '项目  本期金额  上期金额']
print(resolve_unit(lines, len(lines)-1), unit_scale(resolve_unit(lines,len(lines)-1)[0]))"
('万元', 'document', False) 10000
```

单位声明在 **64 行之外、隔着 30 个空行和另一张表**，仍被绑定到本表，×10⁴ 照常生效。

真实样本印证 —— `002670 2018-FY`：

```
 4239|  1．归属于母公司股东的净利润（净亏损以"-"号填列）   -544,272,818.63    580,642,470.28
 header_line=4200 ；最近的「单位：万元」在 line 3588，距表头 612 行
 抽出 value = -5,442,728,186,300.00 元   ← 真值 -544,272,818.63 元，放大 10⁴ 倍
```

**spec §3.4 要求「单位声明只在本表边界内向上就近搜索，遇到表边界即停」。
实现没有实现这个停止条件，只是把越界的情况改了个标签叫 `document`，然后照用不误。
bug ② 未修复。**

---

## 11. 本次验收的限制（诚实披露）

1. **Evaluator 与 parser 共用同一 `pdftotext -layout` 文本层**（spec §8 已预先接受）。
   本批暴露的缺陷全部是**选择错误**（选错行/列/单位），不是文本抽取错误，故该限制不影响结论。
   但需注意：若某份 PDF 的文本层本身就有问题，本次方法学**看不见**。
2. **precision 的统计效力严重不足**（n=4 vs 要求 20）。§4.4 已量化。
3. **候选池被翻页上限截断**，20 个查询窗口全部撞顶（§2.4）。层内抽样可复现，
   但层的候选池带巨潮返回顺序偏差，**76 份不能宣称是全 A 股的无偏样本**。
4. **SINGLE_SOURCE 的 43% 错误率是「从匹配行即可判定」的下界**，只做了逐行核对，
   未对全部 30 份做像 CONFIRMED 那样的全文取证。真实错误率可能更高，不会更低。
5. **未复现 pilot 原 13 份失败样本**（属已烧掉的 50 份，H2 禁止）。
   bug ①（附注列）在本次 holdout 上**没有观察到反例，也没有观察到正例**——
   76 份里没有一份是因附注列误认而失败的，故 bug ① 的修复本次**既未证实也未证伪**。
6. **未评估 `600787` / `601992`**（spec §7 列为用户人工事项，不在 feature 内）。

---

## 12. 逐条 acceptance 判定

| acceptance | 判定 | 依据 |
|---|---|---|
| (1) 自选 seed、`--exclude-manifest` 排除 50 份、抽 ≥60 份、先冻结再评测 | **PASS**（含变通） | §2；seed `4172639`，76 份，交集 0，manifest+hash 评测前落盘。★但暴露 E01 |
| (2) 跑抽取器、逐份结果 + failure code 分布、按年份/板块/报告类型分层 | **PASS** | §3；76/76 无 PIPELINE_ERROR |
| (3) 对 CONFIRMED 随机抽 ≥20 份人工裁定 precision | **FAIL（无法执行）** | §4.1；CONFIRMED 仅 4 份，全量普查 4/4 |
| (4) 全部 SOURCE_CONFLICT 裁定、给出误报率 | **PASS** | §5；5/5 全裁定，误报率 40% |
| (5) 硬门 precision ≥99% 且 CONFIRMED 中 10ⁿ 错误 = 0 | **NOT MEASURABLE / 部分 PASS** | §4.3-4.4；10ⁿ 错误 = 0 ✅；precision 无统计效力 |
| (6) H1 / H4 / H5 边界检查 | **PASS** | §6 |
| (7) 输出 signoff + 采购结论 | **PASS** | 本文件；§9 |
| (8) 写明与 parser 共用文本层的限制 | **PASS** | §11(1) |

---

## 13. 最终裁定

**FAIL** → `progress.json.status = fixing`，`fix_rounds` 保持 0（首轮验收）。

**不判 PASS 的三条硬理由：**

1. **acceptance (3) 无法执行**——CONFIRMED 只有 4 份，达不到要求的 20 份，硬门无统计效力。
2. **F002 的联网抽样路径 100% 不可用（E01）**——这是 F003 唯一必须走的路径。
3. **spec §3.4 承诺修复的 bug ② 实测未修复（E04），bug ④ 的修复引入了更危险的回归（E02），
   bug ③ 的修法在真实版面上大面积失效（E03）。** 四类 bug 里三类没有真正解决。

**给 fixing 阶段的建议顺序**：E01（阻断）→ E03（覆盖率第一主因）→ E02（错值第一主因）
→ E04 / E05（数量级防线）→ E06 / E07（冲突质量）。修完后**用同一 seed `4172639` 的冻结 holdout 复评**，
PDF 已全部落盘（`data/research/b108/pdf/`），复评零下载成本，可直接对比。

---

## 附录 A — 证据文件

| 文件 | 内容 |
|---|---|
| `docs/test-reports/B108-holdout/holdout-manifest.json` | 冻结 holdout（76 份），文件 sha256 `137db270…5f1c2d` |
| `docs/test-reports/B108-holdout/holdout-provenance.json` | seed / 查询诊断 / 逐层覆盖 / 生成时间 |
| `docs/test-reports/B108-holdout/eval-results.json` | 逐份评测结果（含 `line_index`，可逐条回溯原文） |
| `docs/test-reports/B108-holdout/stratified-report.txt` | 分层汇总原始输出 |
| `scripts/test/b108_holdout_discover.py` | Evaluator 候选池发现（因 E01 而必须自建） |
| `scripts/test/b108_holdout_eval.py` | 下载 + `pdftotext` + `cross_check` harness |
| `scripts/test/b108_holdout_report.py` | 分层统计 |
| `data/research/b108/pdf/` (76 份，未入 git) | 原始 PDF，供复评 |
