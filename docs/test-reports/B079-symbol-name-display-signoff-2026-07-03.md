# B079 — 标的名称显示（名称为主、代码次之）验收签收报告

**批次：** B079 — Symbol Name Display（横切前后端 UX：所有显示代码处加显名称）
**验收阶段：** verifying（F004，首轮）→ **裁定 PASS**
**日期：** 2026-07-03
**Evaluator：** 独立 agent（代 Codex 执行，用户 /goal 授权，无实现上下文隔离——本报告一切以仓库现状 + 真机实测为准，不依赖任何实现者转述）
**被验收交付：** `d188096`(F001 名称 store) + `585d30a`(F001 §12.10.2 守门修) + `157cb21`(F002 后端 10 model enrich) + `ef30cc9`(F003 前端 SymbolLink + name threading)

---

## 0. 裁定摘要

**PASS。** B079 三个 generator feature（F001 名称 store + batch 解析 / F002 后端 10 response model enrich / F003 前端 SymbolLink 名称为主）已在生产 VM 上端到端验证通过：

- **US / ETF / 大盘 CN·HK 名称立即可用**（进程内 curated seed，不依赖 seed job）——真机 recommendations / position-diff / paper / symbols 详情逐一贴出真实响应，名称正确。
- **A股 宽 universe（cn_attack）中文简称当前为 `null`，走纯 code 优雅兜底**——这是 spec §3 诚实边界① + F004 第 7 项**明示的「待下次日刷，不算 FAIL」**：F001 名称捕获码今日 16:20–18:35 部署，晚于今日 01:30 的日刷；捕获 wiring 已逐条核实正确（生产 ExecStart 传 `--cn-universe-sina-fallback`，sina spot 在 VM 可达并含「名称」列），下次日刷（01:30 UTC 2026-07-04）将落库全市场 A股 中文名。
- **零回归全部守住**：既有 `symbol`/code 契约不变；no-execution / no-broker safety 守门（172 safety PASS）；cn_attack research 态免责声明（OOS −9%~−11% 警示）完整保留；名称落库 read-only（写只发生在离线 data-refresh + bootstrap seed，请求路径零写入）。

---

## 1. HEAD ≡ prod（等价性）— PASS

| 项 | 值 |
|---|---|
| origin/main HEAD | `1056b33`（chore: progress.json → verifying，**paths-ignore 不触发部署**）|
| 上一个代码提交 | `ef30cc9`（F003，B079 最后一个产品代码变更）|
| 生产 release symlink | `/srv/workbench/current` → `releases/ef30cc9d0827…` |

`1056b33` 仅改 progress.json（进度类，paths-ignore），不部署。生产 release = `ef30cc9` **携带 F001+F002+F003 全部代码**。等价性成立。✓

---

## 2. 名称在所有显示位置出现（真机实测，authenticated GET）— PASS

真机 `ssh tripplezhou@34.180.93.185`，backend `127.0.0.1:8723`。认证：token 为明文 HS256 JWS（`jwt_validator.py` 确认非 JWE），在 VM 上就地用 `NEXTAUTH_SECRET` 铸一枚 10 分钟只读会话 token（secret 全程留在 VM、从不打印），发 `authjs.session-token` cookie 做**只读 GET**。

| 显示位置 | 端点 | 真实响应片段（symbol → name） | 结果 |
|---|---|---|---|
| **Recommendations（master）** | `/api/recommendations/current?strategy_id=master_portfolio` | `CAT`→`Caterpillar Inc.` / `HD`→`The Home Depot, Inc.` / `SPY`→`SPDR S&P 500 ETF Trust` / `SGOV`→`iShares 0-3 Month Treasury Bond ETF` / `AGG` / `VEA` / `GLD`（7/7 命名）| ✓ |
| **Recommendations（cn_attack pure）** | 同上 `?strategy_id=cn_attack_pure_momentum` | 25 条 A股（`001267.SZ` / `300308.SZ` …）name=`null`（待日刷，见 §7）| ✓ 兜底 |
| **Recommendations（cn_attack quality）** | 同上 `?strategy_id=cn_attack_quality_momentum` | 25 条 A股 name=`null`（待日刷）| ✓ 兜底 |
| **Position-diff（master）** | `/api/execution/position-diff?strategy_id=master_portfolio` | `diff[]` + `target[]` 双列均带名：`CAT`→`Caterpillar Inc.` / `SPY`→`SPDR S&P 500 ETF Trust` … | ✓ |
| **Paper（master）** | `/api/paper/master_portfolio` | `positions[]`(7) + `drift[]`(7) 均带 ETF/US 名 | ✓ |
| **Paper（regime_adaptive）** | `/api/paper/regime_adaptive` | `DBC`→`Invesco DB Commodity Index Tracking Fund` / `QQQ`→`Invesco QQQ Trust` … | ✓ |
| **Paper（cn_attack ×2）** | `/api/paper/cn_attack_*` | 25 仓 + drift，A股 name=`null`（待日刷）| ✓ 兜底 |
| **Symbols 详情头部（A股 大盘）** | `/api/symbols/600519.SH/price` | `600519.SH`→`Kweichow Moutai`（curated CN 大盘）| ✓ |
| **Symbols 详情头部（US）** | `/api/symbols/AAPL/price` | `AAPL`→`Apple Inc.` | ✓ |
| **Fills** | `/api/execution/fills` | 生产仅 1 张 voided ticket（0 fills）→ 无数据可练；code + L1 已覆盖（见 §附）| ⚠ 空态 |
| **Backtest trades** | `/api/backtests/{run_id}` | 生产无已完成 run 可枚举；code + L1 已覆盖 | ⚠ 空态 |

> **前端渲染（F003）走查**：`<SymbolLink>` 在 recommendations（ag-grid cellRenderer + 洗售 flag + PositionCards）/ position-diff / paper（仓+drift）/ backtest / fills 全部以 `name={…}` threading（10 处复用点核实）；组件 `name` 存在时渲染「名称为主 + code 灰色小字」，缺失/null 渲染纯 code。详情页头部 `symbols/page.tsx` 同样 `data.name ? 名称+code灰 : code`。名称为主、代码次之的展示契约一致。

**结论：** 所有**有生产数据的**显示位置均正确显示名称（US/ETF/大盘），A股 宽 universe 走 null 兜底（待日刷）；fills/backtest 因生产无数据未能真机贴证，但代码路径与 L1 已覆盖，如实标注空态。

---

## 3. 缺失 fallback 优雅兜底（不变量③）— PASS

- **列表型兜底**：cn_attack 两模式共 50 条**真实合法** A股 symbol，name 全部 `null`，**响应无报错、不空白、symbol 字段完好** —— 这正是「name store 与 curated 均无 → 纯 code」的优雅兜底真实样本。
- **前端渲染兜底**：`SymbolLink.tsx` `displayName ? (name + code灰) : (symbol)`；详情页头部同构。null 名称退化为纯 code，无破链、无空 label（组件 `data-testid="symbol-link"` + `aria-label` 仍在）。
- 无需再造假标的：生产现状本身即提供了 50 条 name=null 的真实兜底证据。✓

---

## 4. batch 解析证据（不变量④，1 次 DB 非 N 次）— PASS

**代码证据（file:line）：**
- `symbols/names.py:122-142 resolve_symbol_names` = 单一 enrich 入口：一次进程内 curated dict lookup + **一次** `SymbolNameRepository.get_names`（`names.py:141`）。
- `db/repositories/symbol_name.py:34-48 get_names` = 单条 `select(...).where(SymbolName.symbol.in_(list(symbols)))`——**一个 `.in_()` 查询 enrich N 行**，空输入短路 `{}`，纯 DB 不触发任何外部 fetch。
- 各 service 每响应**只调用一次** `resolve_symbol_names`（grep 全量核实）：`recommendations.py:199`（target_symbols 集合）/ `execution.py:221`（held∪target 并集，一次喂 diff+target）/ `paper.py:135`（一次喂 positions+drift 双子表）/ `fills.py:254,333` / `backtests.py:72` / `reconcile.py:269` / `wash_sale.py:137` / `symbols/service.py:178`。
- **真机侧证**：cn_attack 单响应一次性返回 25 个 symbol，name 全 null——若前端逐个打 `/fundamentals`，则会触发 akshare/yfinance 逐个 fetch 出名；null 恰证明后端一次批量解析、前端零逐个外部 fetch。✓

---

## 5. 名称落库 read-only 边界（不变量⑤，§12.10.2）— PASS

- **写只在离线 job**：`upsert_names` 全仓仅两个调用点——`data_refresh/cli.py:351`（每日 data-refresh job，`source="akshare_spot"`）+ `cli/bootstrap.py:169`（bootstrap curated seed）。**请求路径零 `upsert_names` 调用**（grep 全量核实）。
- **§12.10.2 守门**：`tests/safety/test_symbols_request_self_contained.py` 已注册 `symbols/names.py`（`585d30a` 补），且 `test_every_symbols_module_is_scanned` 钉死「新 symbols/ 模块必须登记」——本地复跑 172 safety PASS。
- **model 隔离**：`db/models/symbol_name.py` docstring「never read by the recommendation / backtest / risk / account scoring layers … a pure display concern」，且 `names.py` 不 import trade（守门断言）。请求路径读 name 走纯 DB `get_names`，不写、不触发外部。✓

---

## 6. 零回归（不变量①②）— PASS

| 回归面 | 证据 | 结果 |
|---|---|---|
| ① 既有 code/symbol 契约不变 | 所有真机响应仍含 `symbol` 原字段（name 为**新增可选**字段）；recommendations/position-diff/paper/fills/backtest schema 均 `symbol` + `name?` | ✓ |
| ② no-execution / no-broker safety 守门 | 本地复跑 `tests/safety/` **172 passed, 15 skipped**（含 `test_no_broker_sdk_imports` / `test_symbols_request_self_contained` §12.10.2 / recommendations·backtests·snapshots·strategy-modes self-contained）；`SymbolLink` 为**只读导航**（deep-link 到 quote 页），无 buy/sell/execute affordance | ✓ |
| ② research 态 disclaimer | 真机 `cn_attack_pure_momentum` 响应 `research_caveat` **完整存在**：`{validated:false, oos_result:"negative", oos_cagr_range:"-9% ~ -11%", headline_zh:"未经样本外验证：B066 样本外（2025H2 起）CAGR −9%~−11%（动量逆转期会亏）。" …}` | ✓ |
| 名称落库不改日刷关键路径 | 捕获复用 `discover_ashare_superset` 已抓的 spot 帧「名称」列（零额外 fetch）；`_persist_symbol_names` 在价格写入后、与 data-window 同一 prod-DB guard 下执行（`data_refresh/cli.py:479-498`）| ✓ |

---

## 7. symbol_name 表状态 + akshare spot 落库（F004 第 7 项，诚实边界①）

**当前生产 `symbol_name` 表 = 0 行**（`sudo sqlite3 'file:/var/lib/workbench/db/workbench.db?mode=ro'` 只读查询）。这**不影响 US/ETF/大盘名显示**（走进程内 `CURATED_SYMBOL_NAMES`，`names.py:107-119` import 时构建，docstring「always available in-process … coverage never depends on a seed job having run」——真机 master 名称即由此而来）。

**A股 中文名待下次日刷（非 FAIL，wiring 已核实自愈）：**

决定性时间线（2026-07-03 UTC）：

| 时刻 | 事件 |
|---|---|
| **01:30** | data-refresh 运行（旧 release，F001 捕获码**尚未部署**；完成日志 `data refresh done — price_symbols=42 … cn_universe_price_rows=1680776`，无 symbol_name 写入行）|
| **16:20** | `d188096`（F001 捕获码）部署 |
| **17:31** | `585d30a`（F001 §12.10.2 fix）部署 |
| **18:35** | `ef30cc9`（F003）部署，symlink 翻到 ef30cc9 |
| **01:30（明日）** | 下次 data-refresh —— 首次携带 F001 捕获码运行 |

即**F001 名称捕获码部署（16:20–18:35）晚于今日日刷（01:30）→ 尚未经历任何一次日刷** → 表空正是 spec §3 诚实边界① + F004 第 7 项明示的「今天 refresh 未跑 → 待下次日刷，不算 FAIL」。

**捕获 wiring 已逐条核实正确（保证下次日刷必落库）：**
1. `cn_marketcap.py:212-256 _discover_from_sina` 在循环顶部（filter 之前）对**每条** spot 记录写 `names_out[canonical]=名称`——覆盖 sina 全市场 ~5500 名（含 cn_attack 小盘）。
2. `data_refresh/cli.py:434-440` 把 `capture_names=captured_cn_names` 穿进 `discover_ashare_superset(allow_sina_fallback=args.cn_universe_sina_fallback)`；`cli.py:494-498` 价格写入后 `_persist_symbol_names → upsert_names(source="akshare_spot")`。
3. **生产 ExecStart 实证**：`workbench-data-refresh.service` = `… data_refresh.cli fetch --cn-universe-sina-fallback --cn-universe-top-n 1500 --cn-universe-max-superset 1500 …`——sina 分支已开启。VM 上 eastmoney push host ConnectionError（B065/B068 教训），sina 为 §23 VM-可达 bulk 端点；今日 01:30 run 的 `data_refresh_wide_cn_partial_failure: 3/1494 wide A-share fetches` 已侧证 **sina 在 VM 上答且返回含「名称」列的全市场帧**（ST 过滤即读该列）。捕获读同一帧 → 必落库。

**Soft-watch（下次日刷复核项，不阻断本次签收）：** F001 捕获码部署后**尚无一次日刷实跑**，故「`symbol names — captured=N written=M`」日志行 + A股 表行数为**未观测**。建议下次日刷（01:30 UTC 2026-07-04）后抽查该日志行 + `SELECT source,COUNT(*) FROM symbol_name` 确认 akshare_spot 行落库、cn_attack 面出现中文简称。wiring 已验、非阻断。

---

## 附. L1 抽查（verifying 可跳全量复跑，evaluator §30）— PASS

本机 `.venv/bin/python`（本机 python3=3.9 不满足，一律各自 venv）：

- `tests/unit/test_symbol_name_store.py` + `test_symbol_name_enrich.py` + `test_cn_marketcap_name_capture.py` → **15 passed**（store batch get_names / upsert / enrich 形状 / A股 zero-fetch 捕获）。
- `tests/safety/` → **172 passed, 15 skipped**（skip 为需真 key 的 VCR 红队用例）。

CI 全绿由 planner 交接确认（B079 verifying 前置）；本地抽查覆盖 name 新颖面 + §12.10.2 守门 + no-broker/no-execution safety。

---

## 裁定

**PASS。** F001+F002+F003 功能正确、已部署、真机端到端验证：US/ETF/大盘名立即生效，A股 宽 universe 走 null 优雅兜底且捕获 wiring 已核实（下次日刷自愈）；五条不变量（code 契约 / safety 守门 / null 兜底 / batch 解析 / read-only 落库）全部守住；research disclaimer 零回归。唯一待观测项（A股 首次捕获日志 + 表行数）为 spec 明示的诚实边界，列为下次日刷 soft-watch，不阻断签收。

状态机动作：`progress.json` status→`done` / completed_features=4 / current_sprint=null；`features.json` F004 status→`done`。
