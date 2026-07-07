# B106 — 组合层落地:红利低波并入 Master + 杠铃 + 风险加权对照 Spec

**批次定位:** 组合层落地实现批(混合 3g+1c)。deployment-plan(docs/research/deployment-plan-2026-07-07.md)阶段 A 的核心第一步——**整体提高收益的最高杠杆**。把已验证的红利低波防守腿并入 Master 组杠铃、固定权重改风险加权,回测验证组合 Sharpe/回撤的提升。研究态,verdict-gating,不碰真金。

**来源:** 2026-07-07 用户授权全权运作项目("保证收益最大化,干起来")。依据 uplift review(ashare-portfolio-uplift-review-2026-07-07.md)§1 组合层杠杆 + deployment-plan 阶段 A。

**负责人决策(全权授权下):** 组合层是实证认定的真杠杆(单策略 5 类优化已全否)。红利低波与动量负相关、削回撤 −66%→−40%,并入组杠铃是最直接的组合 Sharpe 提升来源。现有基建(risk_parity_vol_target/risk_parity_hrp/regime_adaptive)已备,红利低波只差并入。

---

## 0. 设计要点(焊死)

- **Master 现状**: 4 sleeve(momentum global_etf 40% / risk_parity_vol_target 30% / us_quality 20% / hk_china 10%),SGOV 防守占位,季度调仓。★70% 是动量族(momentum+us_quality+hk_china)高度同向,唯一稳定腿 risk_parity 30%,**分散性弱**。
- **红利低波(cn_dividend_lowvol)**: 已验证削回撤(B082)、已激活 paper(2026-07-05,满配 512890.SH)。与动量在 A股负相关(2024 初动量崩时 +5.9%)。但**目前游离在 Master 外**——这是最大组合层机会。
- **★核心不变量**: ① 现有 Master 4-sleeve 默认配置**向后兼容不破**(生产 paper/master_portfolio 账户行为不变,新配置是 opt-in 对照);② verdict-gating——组合提升显著才建议改默认,不提升则诚实保持现状(B069/B076 先例);③ 回测用 B070 去偏纪律 + 真成本;④ 研究态/advisory-only/不碰真金。
- **权重方案对照**: 现固定 40/30/20/10 vs 风险平价(risk_parity_vol_target 推广 sleeve 层)vs HRP(risk_parity_hrp)——三方案 + 加防守腿的杠铃,回测对照哪个组合 Sharpe/回撤最优。
- **触 trade/**: master.py 是 trade/ 包 → 全套门禁(mypy trade + 根 ruff + root pytest + backend venv 重装)。

## 1. 复用清单

| 资产 | 位置 | 用法 |
|---|---|---|
| Master 组合配置 | trade/portfolio/master.py | 扩展 sleeve + 权重方案 |
| 风险平价权重 | trade/strategies/risk_parity_vol_target(risk_parity.py) | sleeve 层配权 |
| HRP 层次风险平价 | trade/strategies/risk_parity_hrp.py | sleeve 层配权对照 |
| 红利低波策略 | trade/strategies/cn_dividend_lowvol/ | 防守腿 sleeve |
| regime 检测 | trade/strategies/regime_adaptive/ | (P3 follow-up,本批不接) |
| 去偏回测数据 | data/research/b070 + b082 红利低波数据 | 组合回测输入 |

## 2. Feature 拆解(4:3 generator + 1 codex)

### F001 (g) — Master 组合层扩展:防守腿 sleeve + 权重方案参数化
1. **红利低波作防守腿并入**: Master sleeve 配置加入 cn_dividend_lowvol(role_label="defensive_sleeve"),组成"进攻(动量)+防守(红利低波)"杠铃。新增第 5 sleeve 或重配权重(generator 定,保权重和=1)。
2. **权重方案参数化**: sleeve 层权重从固定值扩展为可选方案——`fixed`(现状 40/30/20/10,默认向后兼容)/ `risk_parity`(按 sleeve 波动率反比,复用 risk_parity_vol_target)/ `hrp`(risk_parity_hrp)。
3. **★向后兼容**: 默认 `fixed` + 现有 4 sleeve = 生产 Master 字节级不变(master_portfolio paper/生产不破);新防守腿 + 新权重方案是 opt-in(对照用)。
**Acceptance**: Master 配置扩展(防守腿 sleeve + 3 权重方案);默认配置与现状 byte-identical(零回归守门单测);权重和=1 各方案。Gates: mypy trade + 根 ruff + root pytest + backend venv 重装 + backend pytest。

### F002 (g) — 组合回测对照 + verdict
1. **回测 runner** scripts/research/b106_portfolio_uplift_ab.py: 在去偏数据 + 真成本上跑组合层对照——① 现状(4 sleeve fixed,基线)② +防守腿(fixed)③ +防守腿(risk_parity)④ +防守腿(hrp)⑤ +防守腿(vol target)。产组合 NAV/Sharpe/CAGR/MaxDD/回撤复利对照表。
2. **★重点输出**: 各方案组合 Sharpe/MaxDD vs 基线的提升;红利低波与动量的相关性(证分散);2022/2024-02 回撤窗口的杠铃缓冲效果;回撤复利价值量化(−X% 回撤→回本涨幅)。
3. **verdict-gating**: 哪个方案组合 Sharpe/回撤显著优于基线 → 建议改默认;若都不显著优 → 诚实保持现状(NO-GO 合法)。报告落 docs/test-reports/B106-portfolio-uplift-ab.md + 登记 trial_registry。
**Acceptance**: 5 方案对照表真数字落盘;基线与现状一致(复现性);verdict 与数字一致;相关性/回撤复利量化。Gates 同 F001。

### F003 (c) — 独立验收 + signoff
- L1 全门禁 + 新单测抽查(默认向后兼容 byte-identical 断言重点)。
- L2/研究: 回测对照数字独立复算(抽 2 方案重跑)、组合 Sharpe/回撤提升真实性(非样本内乐观)、红利低波与动量相关性真实、回撤复利算术、verdict 与数字一致、★现有 Master 4-sleeve 默认零回归(master_portfolio 生产 paper 不破)、HEAD≡prod。
- 边界: research-only/no-broker/不碰真金;signoff 逐条证据。

## 3. 状态流转 + 不变量
- `planning → building(F001→F002) → verifying(F003) → done`。
- **不变量**: ① 现有 Master 4-sleeve fixed 默认向后兼容(生产 master_portfolio paper 字节级不破);② verdict-gating(提升显著才建议改默认,不提升诚实保持);③ 回测 B070 去偏 + 真成本;④ research-only/advisory-only/不碰真金;⑤ 触 trade/ 全套门禁。
- **诚实边界**: ① 组合回测的窗口/数据口径限制如实标注;② 红利低波 A股窗口 ~2018 起(ETF)/2005 起(指数 TR),Master 其他 sleeve 是美股/港股口径——★跨市场组合回测的币种/口径对齐要诚实处理(可能需分市场 sub-portfolio 或 USD 统一);③ 提升是风险调整后(Sharpe/回撤)非绝对 alpha 暴涨。
- **后续(不在本批)**: regime 接入动态权重(P3);paper 前向验证新配置(阶段 B,B106 done 后启动 paper 记录);替换拖累的 hk_china sleeve。
