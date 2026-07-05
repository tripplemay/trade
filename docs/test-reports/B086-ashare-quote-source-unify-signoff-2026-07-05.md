# B086 — A股行情数据源统一层（多源 fallback, 基建）Evaluator Signoff（2026-07-05）

> **裁定：全 PASS → done。** F001（多源 A股 ETF 行情 fetch 层 + Eastmoney→Sina fallback + mock 测试，generator）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B085 先例），与实现完全隔离，最高怀疑度。fallback 分支经 **mutation-check（改源看测试是否 FAIL）** 证实有牙 + **真实网络实测** 端到端跑通。
> **生产 release = `520897f0c374878733c559961b8cbd99b96fa5f0`**（`/srv/workbench/current` symlink 逐字符相等，2026-07-05 12:14 部署）。本批为 **research 层基建**，零产品码 → 生产 release 停在 F001 feature 提交（其后 `3a7a24e` mark-done / `2e499a1` backlog / `b98b065` planner docs 均 paths-ignore chore/docs，不触发部署）→ **生产产品码 ≡ HEAD 产品码**。
> 被验收提交：`520897f`（F001 模块 + 6 单测 + 报告）。

## 1. 验收结论表

| 验收项（spec §2 F002 + team-lead 追加） | 裁定 | 证据 |
|---|---|---|
| **fallback 各分支 mock 真覆盖（非 happy-path only）** | **PASS** | 6 mock 单测覆盖：(1)Eastmoney 成功用它（Sina `pytest.fail` 断言不被调）(2)Eastmoney SSLError→fallback Sina (3)Eastmoney 空→fallback Sina (4)全失败→raise `DataSourceError` (5)sina_symbol sh/sz + 非法 raise (6)返回带 source/adjust 标注。6 passed 0.24s |
| **fallback 分支测试有牙（mutation-check）** | **PASS** | 变异①改源 `continue`→`raise`（破坏 fallback）→ `test_...falls_back_to_sina` + `test_all_sources_fail_raises` **双 FAIL**；变异②`sina_symbol` 恒 `sh` 前缀 → `test_sina_symbol_exchange_prefix` **FAIL**。两变异均被捕获，还原后 6 passed（`git diff` 空）|
| **fallback 端到端真实网络实测** | **PASS** | dev box 真跑 `fetch_etf_daily("510300", 2024-01..02)`：Eastmoney **真 SSLError**（`push2his.eastmoney.com` record layer failure）→ WARNING log → **Sina 接管 23 行**，`source=sina / adjust=raw`，日期窗 `2024-01-02→2024-02-01` 正确过滤 → INFO log `ashare sina served 510300 after ['eastmoney: SSLError']`。**不静默：warning+info 双 log 命中源** |
| **口径标注（qfq vs raw）正确 + 不静默混价** | **PASS（结构核实）** | 每源硬编码自己的 adjust 标签（Eastmoney→`qfq` line 68 / Sina→`raw` line 89）；qfq 施复权调整、raw 不施 → **口径按构造必然不同**，模块显式标注 `adjust` 列 → 调用方永不静默混复权/非复权价。实测 Sina 路径 adjust=raw 正确。**live 数值对照见 §2 软限制** |
| **不静默吞错（全失败明确 raise）** | **PASS** | 全失败 → `raise DataSourceError(f"all sources failed for ETF {code}: {errors}")`（line 124，errors 累计每源失败原因）；单测 `test_all_sources_fail_raises_not_silent` 锁 + mutation-check 证有牙。每源失败/空均 `logger.warning`，永不返回空帧 |
| **消费方零回归（既有 fetch 路径不破 + 产品码 0 行）** | **PASS** | full root pytest（`--ignore=tests/acceptance`）**1160 passed 0 failed**；**无任何 trade/ 或 workbench/ 产品码 import 新模块**（唯一 importer = 本模块单测）；b082/b084/b085 已完成脚本 **git diff 空（字节不变）**；批次改动范围 = 1 研究模块 + 1 单测 + 1 报告 + spec/状态机 JSON，**cn_attack/flagship/生产 data_root 0 行** |
| **超时纪律（网络调用包裹）** | **PASS（软观察 O1，见 §3）** | 网络调用未包 timeout —— 但**与 b084/b085 research-层先例一致**（全 research 脚本零 akshare timeout 包裹）；§38/§39 超时纪律**作用域 = 生产宽集刷 job**（B078 systemd data-refresh 冻结沉淀），非 ad-hoc research 模块。本模块 research-safe、无 systemd timer、无产品消费方 → **非阻断**。促码若未来提升为生产刷 job 须补（见 §3）|
| **CI 绿 + HEAD≡prod + 生产落地** | **PASS** | Python CI + Workbench Backend CI + Workbench Deploy **均绿**（`520897f`）；`/srv/workbench/current` → `520897f…`（= 最后触发部署的产品提交）。本批**无 migration/timer/产品部署物**（research 模块不入部署 rsync）→ 无生产落地物，符合基建 research 层定位 |

## 2. 两源数据一致性（团队 lead 追加项 #2）— PASS（核心不变量），live 数值对照受限

**核心不变量（口径差异显式标注、不静默混价）= PASS**，验证路径见 §1 第 4 行。

**live 数值对照软限制（诚实披露）：** 验收窗口内 **Eastmoney 从 dev box（SSL record layer failure）与 VM（ConnectionError / RemoteDisconnected）双向持续不可达**（VM 上对 510300 + 159915 各重试 4 次全 FAIL，共 8 次），故**无法在本窗抓到 live qfq-vs-raw 逐点数值差**。Sina 两处一致（dev box + VM 均 23 行、close 相同、确定性）。

**这不是缺陷，反而再验证模块前提：** Eastmoney IP 限流/阻断是**真实且持续**的（正是 B084 撞坑 → 本批固化 fallback 的动机）。fallback 在真网下完整生效（§1 第 3 行实测）。口径差异的**存在性**由构造保证（qfq 施分红复权、raw 不施），模块的显式 `adjust` 标注即防混价的正确机制 —— 已结构核实 PASS。live 数值差对照并入 Eastmoney 恢复后的后续可选核查（非阻断）。

## 3. 软观察（非阻断，供后续批 / 促码方参考）

- **O1 — 网络调用未包 timeout（作用域澄清后非阻断）**：`_fetch_eastmoney` / `_fetch_sina` 的 `ak.fund_etf_hist_em` / `ak.fund_etf_hist_sina` 真网调用**无 timeout / daemon-线程 join 包裹**。经作用域审计判**非阻断**：(a) 与 b084/b085 research-层先例一致（`scripts/research/*.py` 零 akshare timeout 包裹）；(b) generator.md §38/§39「超时包裹 ALL 真网络调用」沉淀源 = **B078 生产 A股 data-refresh 宽集刷 job 挂死冻结**，作用域是**生产 systemd 刷 job**，非本 research 模块；(c) 本模块 research-safe、未接任何 systemd timer、无产品消费方。**潜在风险（留给促码方）：** 若未来策略把 `fetch_etf_daily` 接入**生产刷 job / systemd timer**，无 timeout 的网络读可挂死（正是 B078 命门），届时须按 §38 补 daemon-线程 `join(timeout)`。建议在模块 docstring 加一句「生产化前须包 timeout」提示（非阻断，可下批补）。
- **O2 — mypy CI 作用域**：CI `python -m mypy … trade` 仅查 `trade` 包，本模块在 `scripts/research/`（作用域外）→ CI mypy 不覆盖。直接对文件跑 mypy 报 `akshare import-untyped`（缺 stubs），属 research 层预期、与 layering 决策（不入 trade/ 严格域）一致 → **非阻断**。ruff `check .`（全仓）覆盖并通过。
- **O3 — 并发 planner docs 提交**：验收窗口内并发 planner 提交 `b98b065`（`docs/research/next-batch-prep-bootstrap-seed-audit.md`，纯 docs 下批预研），**不碰 B086 状态机 / F001 模块** → 不影响本裁定。已在 commit 前 pull 对齐，避免 clobber。

## 4. 结论

**B086 A股行情数据源统一层（多源 fallback, 基建）2 features 全 PASS → done。**
fallback 各分支经 6 mock 单测覆盖（非 happy-path only）+ **mutation-check 双变异证实有牙**（破 fallback→2 测 FAIL / 破 sina_symbol→1 测 FAIL）+ **真实网络端到端实测**（Eastmoney 真 SSLError → Sina 接管 23 行、adjust=raw、日期窗正确、warning+info 双 log 不静默）；口径标注（qfq vs raw）按构造必然不同且模块显式标注、防混价（结构核实 PASS）；全失败明确 raise `DataSourceError` 不静默吞错（单测 + mutation 双证）；**消费方零回归**（root pytest 1160 passed 0 failed / 无产品码 import 新模块 / b082-b085 完成脚本字节不变 / cn_attack·flagship·生产 data_root 0 行）；CI 全绿 + 生产 release ≡ HEAD 产品码（research 模块不入部署，符合基建定位）。三项软观察（O1 timeout 作用域=生产刷 job 非本 research 模块 / O2 mypy 作用域 / O3 并发 docs 提交）均非阻断。

**两源数值 live 对照因 Eastmoney 持续不可达受限**（8 次重试全 FAIL，dev box + VM 双向）—— 已诚实披露；此持续阻断反再验证模块「固化 fallback」的前提。核心不变量（口径显式标注、fallback 不静默、零回归）全部达成 → **全 PASS**。

> 本批为 P0–P2 评审路线图收官后的**基建批次**（用户 away → 按 option 3 安全推进）。新模块供未来策略取数复用，停止重踩限流/格式坑。
