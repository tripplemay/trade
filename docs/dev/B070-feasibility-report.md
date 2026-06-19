# B070 F001 — 去幸存者偏差 数据 feasibility 报告（§23 三关口实测证据）

**批次：** B070（A股 进攻策略 去幸存者偏差重验）F001。
**结论：** §23 三关口 = **GO**。**免费源（baostock）能拿到去偏所需的两样东西**——
真历史 point-in-time 成分（含已退市名，回溯到 **2007**）+ 退市名在册期间真实价格。
spec §1 对「很可能 NO-GO（去偏=付费数据商卖钱的东西）」的悲观先验，被实测**证伪**：
baostock 的 *dated* `query_{hs300,zz500,sz50}_stocks(date=)` 免费提供逐日真实指数成分，
且含后来退市的输家。**F002/F003 GO，可建真去偏宇宙重跑。**

> **GO 但有诚实边界（见 §4）：** 去偏宇宙的口径是**指数成分**（HS300+ZZ500+SZ50，
> PIT 至多 800 名），与 B068「自建 mcap+成交额 top-N」口径不同；F003 对比须同口径
> （建议在 PIT 成分内再按 mcap+成交额 取 top-N，使唯一变量是「是否去幸存者偏差」）。
> 去偏只消除**幸存者偏差**这一个高估来源，**不**触及另一来源 2024Q4 顺风——披露续挂。

---

## 0. 探针与运行

- 探针：`scripts/research/b070_feasibility_probe.py`（spike 工具，非产品代码；HARD BOUNDARY：仅 akshare/baostock，无 broker）。
- 本机实跑：`.venv/bin/python scripts/research/b070_feasibility_probe.py --label local-2026-06-19 --out data/research/b070/feasibility_probe_local.json`，耗时 ~4m19s，`exit 0`。
- 原始 JSON 证据：`data/research/b070/feasibility_probe_local.json`（gitignored，同 B068 范式）。
- **本机可达性要点：** baostock 走自有 host（非 akshare 的 eastmoney *push* host），**本机直接连通**（B068 的 push-host 本机 SSL-fail 教训不适用 baostock）。Codex F004 在 VM `34.180.93.185` 复跑确认（同 B068 L2 范式）。

---

## 1. Gate A — 历史 PIT 成分（baostock dated）= REACHABLE & 真 point-in-time ✓

baostock `query_hs300_stocks(date=)` / `query_zz500_stocks(date=)` / `query_sz50_stocks(date=)` 真返回（每行 `updateDate, code, code_name`）：

| 指数 | 端点 | 最早探测可得日 | 各档真返回 | 跨期成员变动（首档→末档） |
|---|---|---|---|---|
| 沪深300 | `query_hs300_stocks` | **2007-01-29** | 8 档（2007/10/13/16/19/22/25/26 年 1 月）均 **300** 名，1.5–3.2s/档 | **226/300 离开**、226 加入 |
| 中证500 | `query_zz500_stocks` | **2007-01-29** | 8 档均 **500** 名 | **451/500 离开**、451 加入 |
| 上证50 | `query_sz50_stocks` | **2007-01-29** | 8 档均 **50** 名 | **38/50 离开**、38 加入 |

> 「最早探测可得日」= ladder 最早一档（请求 2007-01-31，实得 updateDate 2007-01-29），**非已证历史下界**：每一档都满返 300/500/50，**未出现空/短档标出真实下界**，2007 之前未探。GO 判定与确切最早日无关。

- **真 point-in-time（非当前快照伪装）：** `date=2007-01-31`→实际 updateDate `2007-01-29`、`date=2026-01-30`→`2026-01-26`，且成分**随日期真实变化**（HS300 跨 19 年换掉 226/300）。若是静态当前列表，跨期不会变。
- **历史成分含「现已退市」名（去幸存者偏差的核心证据）：** ever-members 并集 = **1914** 名，current = **800**，ever-but-not-current = **1114** 名。抽查 40 名经 `query_stock_basic` 核 `status/outDate`，**9 名确证已退市**：

> **★口径校正（F003 防过度归因，verify lens 实测）：** 这 **1114** 名里，**「仍上市、只是轮出指数」的占绝大多数**，真正**已退市**的是其中一个**子集**。上面 9/40 是**有偏抽样**（按 code 排序取前 40 = 集中在 `sh.600xxx` 老钢铁/老工业股，退市率偏高），**非总体退市率**；verify lens 对该池**随机散点抽样仅 ~12% 真退市**。故**真正被 B068 漏掉的退市名数量「远小于 1114」**——F003 量化幸存者偏差时**不得**把 OOS 差异整体归因于「1114 名缺口」，只能归因于退市子集。

| 历史成分名 | outDate | status |
|---|---|---|
| 邯郸钢铁 | 2009-12-29 | 0(退市) |
| 武钢股份 | 2017-02-14 | 0 |
| 葛洲坝 | 2021-09-13 | 0 |
| 退市长油 | 2014-06-05 | 0 |
| 莱钢股份 | 2012-02-28 | 0 |
| 退市银鸽 / 退市保千 / 退市金钰 / 退市明科 | 2020–2022 | 0 |

> **这正是 B068「当前可得名单 top-N」看不见的输家。** B068 宇宙系统性缺席这些退市名 → OOS 系统性虚高。baostock 历史成分把它们带回来了。

---

## 2. Gate B — 退市名在册期间真实价格 = REACHABLE ✓（4/4）

`query_history_k_data_plus(code, fields, start, end, adjustflag="2"前复权)` 对 4 个**已退市**名取在册窗口真返回：

| 退市名 | 窗口 | 行数 | 首→末 close（真实价格轨迹）|
|---|---|---|---|
| 乐视网 `sz.300104`（2020 退）| 2017-01..2019-06 | **605** | 17.89 → 1.69（真崩盘）|
| 暴风集团 `sz.300431`（2020 退）| 2017-01..2019-06 | **605** | 38.70 → 7.27 |
| *ST康得新 `sz.002450`（2021 退）| 2017-01..2018-12 | **487** | 18.99 → 7.64 |
| *ST济堂 `sh.600090`（2021 退）| 2017-01..2019-12 | **731** | 11.34 → 4.18 |

- baostock 完整保留退市名 k 线 → 回测能真实「持有→跌→退市」这些输家（不再幸存者偏差地跳过）。
- **F003 注意（§28 停牌安全读价）：** 退市名 k 线**首末两端都**可能是 `volume=0`、`open=high=low=close`（停牌 ffill 残值——乐视网/*ST济堂 **首末行** source 里 vol=0）→ 回测取价须 NaN-safe，禁 `or 0.0`（generator.md §28），否则停牌段污染收益。**且停牌远非尾部小量**：verify lens 实测全在册窗口零成交日 乐视 **29.6%** / 康得新 **26.5%** / 济堂 7.0%（集中在退市前危机年）——详见 §5 carry-into-F002 STOP-BIAS。

---

## 3. Gate C — 规模可行 ✓ + akshare 反证

- **规模：** 单名全史（茅台 2015–2026）12.34s（含首调用开销）；5 名批量 70.41s（**14.08s/名**，13078 行）→ k 线拉取 **800 名 ≈ 188 min** 一次性研究态建（gated，非生产 daily refresh），可接受。**该 188 min 只含 k 线**，未含成分史拉取（~19yr×3 指数数百次 ~1.25s 调用，~数十 min）+ 每调用 login/logout 开销（`cn_provider._fetch_baostock` 每次登入登出）+ 退市日 basic-info 查询 → **真实约 3–4 小时**。F002 须**持一个 session 整批复用** + **成分史按 updateDate 缓存去重**（连续请求日塌缩到同 updateDate）。20 连发无 throttling，不破可行性。
- **akshare 反证（为何非 baostock 不可）：** `index_stock_cons_csindex` / `index_stock_cons` 真返回各 300 行但**无 date 参数（current-only）** → akshare 单独**给不了 Gate A**。baostock 的 dated 端点是 Gate A 的唯一免费使能源。

---

## 4. 判定 = GO；F002/F003 设计前提与诚实边界

**机械判定（`judge()`，单测 `tests/unit/test_b070_feasibility_judge.py` 焊死）：**
`gate_a_reachable ∧ membership_changes ∧ carries_delisted ∧ gate_b_reachable` → **GO**。

**F002/F003 设计前提（GO 后落实）：**

1. **同口径对比（关键，verify lens 纠正）：** **不要**走「PIT 成分内按 mcap top-N」的天真路线——**退市名没有免费历史 mcap**（`query_stock_basic` 无总股本/总市值；`stock_value_em` 仅当前上市且 ~2018 起），按 mcap 取 top-N 会**静默把退市名挤出 top-N → 在去偏宇宙里重新制造幸存者偏差**。**最安全的 apples-to-apples**：把 B068 自建宇宙**原样保留、仅把当时真实在册的已退市名补进来**，使**唯一变量 = 是否含退市名**；或退一步**只按成交额/amount 排序**（baostock 每 bar 有 `amount`）并诚实标注「因子换了」。详见 §5 MCAP-RANK PARITY。
2. **code 格式归一 + 复用 cn_provider：** baostock `sh.600000`/`sz.000001`（点+前缀）↔ trade 引擎 `600519.SH`，F002 loader 须双向归一。**价格拉取复用 `cn_provider.py`**（已含 baostock fallback path）：`adjustflag="2"`（前复权，匹配 akshare qfq）**已落代码 `cn_provider.py:255` + 锁测 `test_cn_provider.py:177`** → qfq 一致性**已解决**，非待办。注意 qfq 价位是**按名各自 rebase 到退市价**，故跨名只有**收益率可比**（动量 OK）。
3. **gated 不动生产：** 去偏宇宙=研究产物，写研究 data root（非 `/var/lib/workbench/data`），默认关，B067 daily refresh 字节级不变（同 B068 `allow_sina_fallback` 范式）。
4. **更新 B065 残余偏差结论：** `cn_universe.py:33` docstring「cannot include names delisted before today without a **paid** historical-constituents feed」被本批**证伪**（baostock 免费提供）；F002 据实更新该 docstring。
5. **诚实边界不撤：** 去偏只消除**幸存者偏差**（且**仅限指数可纳入band**，见 §5 CEILING）；B068 OOS 高估的**另一来源 2024Q4 顺风**不在本批范围 → advisory 披露续挂（project-status §0 焊死）。去偏后即便仍正收益，也只是「首次去幸存者偏差真验证」，仍研究态、仍披露顺风风险。

---

## 5. Carry-into-F002/F003（verify lens 多 agent 实测，高优先级，须继承）

> 这些不是 F001 的 GO 阻断项（GO 已 CONFIRM），而是 F002/F003 **不照做就会从另一扇门重新引入偏差**的硬约束。

1. **STOP-BIAS（F003，高）：** 停牌**不是尾部小量**——全在册窗口零成交（`tradestatus=0`）天数 乐视 **29.6%** / 康得新 **26.5%** / 济堂 7.0%，集中在退市前危机年（报告 2017–2019 窗口 ~0% 是因那时还活跃，故「末期多有」措辞**低估了量级**但方向对）。qfq 在停牌段**冻结上一收盘价**。F003 须：(a) 从**信号计算**与**可成交进出**都剔除 `volume==0`/`tradestatus==0` 天（停牌段持仓冻结，只在复牌有量 bar 成交）；(b) 无价值名以**最终退市价**记出场，**非**停牌前冻结收盘；(c) 每个退市持仓报告停牌占比。把冻结收盘当可成交 = 恰在「去偏要暴露的输家名上」高估策略。
2. **UNIVERSE-口径 CEILING（F002/F003，高）：** baostock 只暴露 dated `query_{hs300,zz500,sz50}_stocks`——`query_zz1000_stocks`/`query_zz800_stocks` **模块里不存在**（已核）。故去偏并集结构上 = ~800 当前/1914 ever = **大/中盘指数可纳入band**。退市的**微小盘**（常是最惨输家）**仍缺席**。F002/F003 须明确：B070 **只在指数可纳入band内**去幸存者偏差，**非完全去偏**——残余小/微盘偏差仍在（比 B068 小，非零）。**不得宣称完全去偏。**
3. **MCAP-RANK PARITY GAP（F002/F003，高）：** 见 §4 item 1——退市名无免费历史 mcap，天真 mcap top-N 会重造偏差。最安全 = 「B068 宇宙 + 补退市名」隔离单变量；或只按 amount 排序并标注因子换。
4. **TRANSIENT-EMPTY FLAKINESS（F002，中）：** dated 成分端点有**可复现的瞬时空返回但 `error_code` 仍 '0'（success）**——同一日期先返 0 行、立即重试返 300（间歇网络抖动，非限流；偶现 `logout failed!`）。探针 `_drain` 把「空+err0」当合法空 → 瞬时 miss 会**静默写入 0/部分成员的调仓日，污染 PIT 成分**。F002 loader 须：拉取后**断言 n 在期望band内**（==300/500/50 或 >0 带容差），空/短**退避重试**，**绝不**用空/短拉取写调仓行，记录重试。
5. **SCALE BUDGET（F002，低）：** 见 §3——188 min 仅 k 线；真实 ~3–4h；F002 持一 session + 成分史按 updateDate 缓存去重 + 重述为区间。
6. **更新 falsified docstring（F002）：** `cn_universe.py:33` 的「needs **paid** feed」被证伪；F002 据实改为 baostock dated constituents 免费使能（spec §4 item 4）。

**结论分支（F003/F004 落点）：** 去偏后仍正收益/正夏普 → A股 进攻策略**首次去幸存者偏差真验证**（可议信心，仍研究态）；塌掉 → 诚实「B068 强 OOS 主要是幸存者偏差幻觉」。两者都是**有效结论**。
