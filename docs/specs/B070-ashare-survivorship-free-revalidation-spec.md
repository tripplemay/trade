# B070 — A股 进攻策略 去幸存者偏差重验（point-in-time 历史成分股）Spec

**批次定位：** A股 进攻策略可信度的**真瓶颈攻坚批**。B066-B069 把策略刻画清楚了（等权对、质量有风险调整价值），但**强 OOS 很可能是幸存者偏差 + 顺风高估的幻觉,策略未真验证**。本批用 **point-in-time 真实历史成分股 + 退市名价格** 重建去偏宇宙、重跑回测,回答唯一问题:**去掉幸存者偏差后,这个策略还成立吗?**

**feasibility-first（像 B060 A股 P0 spike）：** 免费源（akshare/baostock）能否拿到去偏所需数据是**最大未知**。**F001 先验,拿不到 → 诚实 NO-GO**（免费数据修不了 = 有效结论:策略只能停研究态,真验证需付费数据如 Wind/聚宽）。

**来源：** 2026-06-19 用户 B069 done 后选「消除幸存者偏差」为下一批。

---

## 0. 为什么这是真瓶颈（诚实背景）

- 现宽宇宙（B068）= 用**当前**可得名单建（top-N by 市值+成交额）→ **天然只含"活下来的赢家"**,已退市/已剔除的输家全缺席 → 回测系统性虚高（B068 OOS CAGR 62-77% 大概率假）。
- 去偏需 **point-in-time 真实成分**:每个调仓日**当时**的真实指数成分（含后来退市/剔除的名字）+ 这些名字在其在册期间的**真实价格**。
- **这正是付费数据商（Wind/聚宽/JoinQuant）卖钱的东西。** 免费源能不能拿到 = 本批成败,F001 先验。

---

## 1. 三个 feasibility 关口（§23，F001 先验，任一不可达即影响结论）

| 关口 | 要什么 | 候选免费源 | 不可达后果 |
|---|---|---|---|
| **A. 历史 PIT 成分** | 每个调仓日的真实指数成分（含变更史）| akshare `index_stock_cons_csindex` / `index_stock_cons` / 沪深300·中证500 成分变更记录 | 无成分史 → 无法定 PIT 宇宙 → NO-GO |
| **B. 退市/历史名价格** | 已退市/已剔除名字的历史价格（在册期间）| akshare/baostock 退市股价格 / sina 历史 | 无退市价格 → 偏差只能部分消除 → PARTIAL（诚实标残余偏差）|
| **C. 数据量/规模可行** | 数百名 × 多年的拉取量 + 时长可接受 | sina/baidu host（B062/B064/B068 验过的可达 host）| 规模不可行 → 缩范围 + 诚实标 |

> **GO** = A+B 都拿得到 → 真去偏宇宙;**PARTIAL** = A 有 B 缺 → 部分去偏 + 诚实标残余;**NO-GO** = A 缺 → 免费修不了,诚实结论（策略停研究态,真验证需付费数据）。

---

## 2. 复用清单（本会话已核）

| 资产 | 位置 | 用法 |
|---|---|---|
| PIT universe builder | `workbench_api/data_refresh/cn_universe.py`（`point_in_time_top_n` / `build_cn_universe` / sina spot 可达 B068 验过）| 改为吃**真历史成分**（替当前 top-N 自建）|
| cn_attack 引擎 + 回测 + §29 红旗 | `trade/strategies/cn_attack_momentum_quality/` + `trade/backtest/.../` + B068 4 配置 harness | 在去偏宇宙上重跑（默认 equal,B069 结论）|
| B068 宽数据/对比 harness | `docs/dev/B068-wide-comparison-report.md` + F003 harness | 对照（偏差宇宙 vs 去偏宇宙,量化高估多少）|
| §23 spike 范式 | B060 A股 P0 / B068 F001 sina 验法 | F001 VM 实跑验三关口 |

**必须新写：** (a) 历史成分 loader（akshare 成分史 → PIT 成分表）;(b) 退市名价格拉取（在册期间）;(c) survivorship-free universe builder（真成分 + 退市价格,替自建 top-N）;(d) 去偏 vs 偏差 OOS 对比。

---

## 3. Feature 拆解（4 features：3 generator + 1 codex）

### F001 — §23 三关口 feasibility 验证（VM 实跑）+ GO/PARTIAL/NO-GO 报告（executor: generator）

1. VM 实跑验三关口（§1）：A 历史 PIT 成分（akshare 成分史端点）/ B 退市名价格 / C 规模。
2. **明确判定 GO / PARTIAL / NO-GO** + 报告入 git（贴真返回:能拿到几年成分史、退市名价格样本、覆盖率）。
3. **NO-GO/PARTIAL 是成功的 spike 非失败**（诚实出口:免费源天花板 = 有效结论）。

**Acceptance（§29）：** 三关口可达性结论各贴真返回证据 + 明确 GO/PARTIAL/NO-GO。Gates：backend+trade 门禁绿。**NO-GO → 批次主要在此收（F002/F003 跳过或缩）。**

### F002 — survivorship-free PIT 宇宙构建（GO/PARTIAL 才做）（executor: generator）

1. 历史成分 loader（成分史 → 每调仓日 PIT 成分,含后来退市名）。
2. 退市/历史名价格拉取（在册期间）→ 进数据帧。
3. survivorship-free universe builder（真成分 + 退市价格,替 B068 自建 top-N）;PARTIAL 时诚实标残余偏差。
4. gated（默认关,不动 B067/生产 daily refresh,同 B068 allow_sina_fallback 范式）。

**Acceptance：** 去偏宇宙含历史成分（含已退市名,贴样本日成员 + 退市名占比）;US/B067 零回归。Gates 同 F001。

### F003 — 去偏宇宙重跑回测 + 偏差量化对比（GO/PARTIAL 才做）（executor: generator）

1. 在 survivorship-free 宇宙上重跑 cn_attack（默认 equal,B069 结论;2 因子）walk-forward。
2. **对比偏差宇宙（B068）vs 去偏宇宙的 OOS** → 量化幸存者偏差高估了多少（CAGR/Sharpe 差）。
3. **研究判定**:去偏后策略是否仍正收益/正夏普（=真成立）还是塌掉（=之前是幻觉）。§29 红旗沿用。

**Acceptance：** 去偏宇宙回测真数字 + 偏差量化（去偏 vs 偏差 OOS 对比）+ 明确「去偏后是否仍成立」结论。Gates 同 F001。

### F004 — Codex 验收 + 研究判定 + signoff（executor: codex）

**真数据批次——signoff 含实测证据（§29）：**
- L1 全门禁。
- **L2 真机（VM,贴真返回）：** F001 三关口可达结论;（GO/PARTIAL）去偏宇宙真建（历史成分 + 退市价格样本）;去偏 vs 偏差 OOS 对比真数字;**去偏后策略是否仍成立的研究判定**。
- 零回归（B067/B068/B066/Master 不破,gated 不动生产）;研究态/no-broker;HEAD≡prod。
- **结论分支**:GO+策略仍成立 → A股 进攻策略**首次真验证**（可议是否提升信心/配资讨论,仍研究态）;GO+塌掉 → 诚实"之前是幻觉,策略不成立";NO-GO → "免费数据修不了,需付费数据,策略停研究态"。signoff 实测证据逐条。

---

## 4. 状态流转 + 不变量

- feasibility-gated 混合批次：`planning → building(F001 gate→F002→F003) → verifying(F004) → done`。F001 NO-GO 则 F002/F003 缩/跳,F004 验 NO-GO 诚实结论。
- **不变量**：①B067 生产 advisory / B068 / B066 / Master 零回归（去偏宇宙 gated 默认关,不动生产 daily refresh）;②research-only / no-broker / no 收益预测 / 不碰 live 配资;③OOS 红卡续挂（去偏前策略未验证;去偏后据结论更新披露）;④§12.10.2 / §23 端点实跑 / ruff 目录上下文 / mypy CI-exact;⑤NO-GO=有效诚实结论,不强凑。
