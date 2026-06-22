# B075 — A股 生产股票池扩大到全市场流动（top ~1500，feasibility-first）Spec

**批次定位：** 产品改动——把 cn_attack 两策略的生产 universe 从 ~43 只种子蓝筹扩大到**全市场流动 top ~1500**(市值+成交额),让 advisory 推荐 + 模拟盘从更宽的池子选股。**feasibility-first**:目标 1500,但实际 N 由 VM 真机可行性闸定,刷不动诚实退到最大可行 N。

**来源：** 2026-06-22 用户「希望把股票池扩大」→ AskUserQuestion 选「全市场流动(top ~1500+)」。

---

## 0. ★范围 + 诚实约束（焊死）

- **目标 top ~1500（市值+成交额,current liquid,剔 ST/退市）**;**feasibility-gated**:F001 VM 实测确定可行 N,**若 1500 日刷不可靠则诚实退到最大可行 N 并报告,不静默 cap、不硬凑跑不完的数字**（roadmap honest-fallback,B070 先例）。
- **survivorship 对 live/forward 不是问题**:用当前可交易宽名单向前跑是正确的（偏差只伤回测,本批是生产 live universe）。
- **不改 cn_attack 策略本身**:仍研究态、OOS 红卡续挂、edge 微弱不可配资。本批只扩**选股广度**(43→~1500),不改打分/权重/退出逻辑,不构成策略验证。
- **数据负载是命门**:价格逐只 akshare(1500 次/天)是重活;**基本面季度才变→低频刷(周/月),不日刷**;partial-failure 须优雅(部分失败跳过、不炸整轮)。
- **§23 主机可达性**:`stock_zh_a_spot_em` bulk 发现走 eastmoney push 主机(dev box SSL-fail)→**可行性必须在 VM 实测,不得以 dev box 结果定论**。

---

## 1. 现状 + 复用清单（已核源码）

| 资产 | 位置 | 用法 |
|---|---|---|
| 宽宇宙发现（gated）| `cn_universe.py discover_ashare_superset`（`stock_zh_a_spot_em` bulk,BEST-EFFORT,eastmoney push 主机 dev SSL-fail→fallback `CN_UNIVERSE_SEED`/VM bulk-spot snapshot）| ungate 生产 + top-1500 |
| PIT top-N 排名 | `cn_universe.py point_in_time_top_n`（superset→top_n by composite 市值）| N=1500 |
| 历史市值 fetch | `cn_marketcap.py`（per-symbol BEST-EFFORT,caller bounds superset size）| 宽集逐只 |
| CN 价格 loader | `data_refresh/cn_hk_prices.py CnHkPricesLoader`（akshare lazy per fetch,逐只）| 宽集 prices（命门）|
| data_refresh CLI | `data_refresh/cli.py fetch`（`--cn-*` 参数 + `cn_extra_price_symbols` superset cap）| 宽集 prices daily + fundamentals low-freq |
| price_snapshot 同步 | `cn_snapshot_sync`（B074,统一 CSV→price_snapshot）| 宽集/目标 A股 给模拟盘 |
| cn_attack 选股 | `cn_attack_precompute.py` + `cn_pit_universe` | 从宽 PIT 池选 top-25 |
| acceptance 层 | `tests/acceptance/`（B071-B074）| 宽宇宙不变量守门 |

---

## 2. Feature 拆解（3 features：2 generator + 1 codex）

### F001 — 宽 universe 机制 + VM 可行性闸（确定可行 N）（executor: generator）

1. **ungate 宽宇宙发现**：`discover_ashare_superset` 在生产可用（top-N 可配,默认目标 1500,市值+成交额,剔 ST）。VM bulk-spot snapshot 路径（eastmoney 主机 VM 可达性）。
2. **★VM 可行性探针（§23,generator 实施时 SSH VM 实跑）**：实测 (a) bulk discover top-1500 可达/耗时;(b) **日刷 ~1500 A股 价格的时长 / 成功率 / rate-limit**;(c) 基本面低频(周/月)刷 ~1500 的可行性。**产出可行最大 N + GO/PARTIAL 结论**（1500 不可靠→退最大可行 N,写 session_notes/handoff,不静默 cap）。
3. **优雅 partial-failure**：逐只 fetch 部分失败跳过、记数、不炸整轮;fundamentals 低频 schedule(与 prices 解耦)。
4. 单测（宇宙构建/排名/partial-failure 处理,确定性 fixture）。

**Acceptance：** 宽宇宙发现生产可用(top-N 可配);VM 实测确定可行 N + GO/PARTIAL 结论(贴真耗时/成功率);partial-failure 优雅;fundamentals 低频解耦。Gates：backend pytest/ruff 目录上下文/mypy CI-exact 0。

### F002 — 接生产数据刷新 + price_snapshot 同步 + cn_attack 宽池选股（按 F001 可行 N）（executor: generator）

1. **生产 data_refresh 覆盖宽集**：prices daily(~可行 N)+ fundamentals low-freq;`cn_extra_price_symbols` superset 扩到可行 N;统一 CSV 写宽集。
2. **price_snapshot 同步宽集**（复用 B074 `cn_snapshot_sync`）：宽集/cn_attack 目标 A股 进 price_snapshot,模拟盘能估价宽选股。
3. **cn_attack 两策略从宽 PIT 池选股**：precompute 读宽 `cn_pit_universe`(可行 N)→选 top-25;质量变体缺基本面名按现有 construction 剔除(NaN quality drop)。advisory 推荐 + 模拟盘反映宽选股。
4. 边界：研究态不改策略逻辑;US/Master/regime/hk 零回归。

**Acceptance：** 生产 data_refresh 覆盖可行 N(prices daily+fundamentals low-freq);price_snapshot 含宽选股目标;cn_attack 两策略从宽池选 top-25(advisory+模拟盘);Master/regime/hk 零回归。Gates 同 F001 + acceptance。

### F003 — Codex L2 真机验收 + GO/PARTIAL 诚实结论 + signoff（executor: codex）

**真机/真数据/可行性批次——signoff 含实测证据（§29 + §23）：**
- L1 全门禁（verifying 可跳 L1 复跑,B071 §30）。
- **L2 真机（VM,贴真返回）：** ① 宽宇宙真建(N 只,贴 discover 耗时/成功率) + **独立复核 F001 可行 N 结论(1500 还是退档)**;② cn_attack 两策略从宽池选 top-25(贴 advisory 推荐 + 模拟盘建仓持仓,与 43 种子选股对比看变化);③ 数据刷新真覆盖宽集 + 稳定(多日/重跑成功率);④ Master/regime/hk + US paper **零回归**。
- **★GO/PARTIAL 诚实结论**：实测可行 N = ?;1500 达成/退档;诚实记数据负载现实(日刷时长/失败率)。
- 边界:research-only/no-broker/no 真金;不改策略逻辑;HEAD≡prod。signoff 实测证据逐条。

---

## 3. 状态流转 + 不变量

- 混合批次：`planning → building(F001→F002) → verifying(F003) → done`。
- **不变量**：① US/Master/regime/hk 数据 + paper 零回归;② research-safe / no-broker / no 真金 / 不改 cn_attack 策略逻辑;③ §23 可行性 VM 实测(非 dev box);④ 诚实可行 N(刷不动退档不静默 cap);⑤ §12.10.2 / ruff 目录上下文 / mypy CI-exact;⑥ partial-failure 优雅(不炸整轮)。
- **诚实边界**:扩的是选股广度(43→~可行 N),**不改"策略研究态、未验证、edge 微弱不可配资"定位**;池子大≠edge 更强(更多候选也带更多噪声/暴雷,质量变体的基本面剔除是唯一防护)。
- **运维**:部署后 data_refresh(宽 prices)+ fundamentals low-freq job + cn_snapshot_sync + cn_attack precompute + paper-mtm 各跑让宽选股生效。
