# B069 — cn_attack 实盘 advisory 默认权重切 inverse_vol（据 B068 验证）Spec

**批次定位：** B068 验证的 **follow-up 落地批**。B068 在宽宇宙上对比 等权 vs 波动率倒数加权,用户自验结论支持 **inverse_vol 改善 OOS** → 本批把 **B067 实盘 advisory 两 cn_attack 模式的默认权重从 equal 切到 inverse_vol**。**小批**(2 generator + 1 codex)。

**来源：** 2026-06-18/19 用户讨论 + 自验 B068 → 选 follow-up 调实盘默认权重。

---

## 0. ★诚实前提（焊死）

- **切线上推荐默认 = 产品变更,须有可审计依据。** B068 的 4 配置对比数字**没进 git**(用户本地自验)。**本批 F001 先把切换依据落进 git**(跑/记 B068 对比,确认 inverse_vol vs equal 的 OOS 改善),**F002 据此才切**——确认改善才切,没改善则不切并诚实报告(不盲切)。
- **OOS 红卡不动。** B066 OOS 动量逆转的"未验证/会亏"诚实披露**继续显示**——inverse_vol 是"改善崩盘",不是"已验证赚钱"。研究态/advisory-only/不自动下单 不变。
- **回测/研究默认仍 equal。** 只改 live producer 传参,`CnAttackParameters` 全局默认 `weighting_scheme=equal` 不动 → B068/B066 回测对照基线不变,可控。

---

## 1. 切换点（已核源码）

- `workbench_api/strategy_modes/cn_attack_precompute.py:183`：现 `CnAttackParameters(factor_variant=factor_variant)`(不传 weighting_scheme → 默认 equal)。**改为传 `weighting_scheme="inverse_vol"`**(两模式 quality_momentum + pure_momentum 都切;权重方案正交于因子变体)。
- `trade/strategies/cn_attack_momentum_quality/parameters.py:49`：`DEFAULT_WEIGHTING_SCHEME = WEIGHTING_SCHEME_EQUAL` **保持不变**(全局默认 equal=回测/研究/向后兼容)。

---

## 2. Feature 拆解（3 features：2 generator + 1 codex）

### F001 — 落 B068 切换依据入 git（可审计）（executor: generator）

1. 跑 B068 4 配置对比(等权 vs 波动倒数 × 2 因子,复用 B068 F003 harness + 宽宇宙)on VM,或整理用户自验结论 → **落一份简短研究依据报告入 git**(`docs/test-reports/` 或 `docs/product/`):Q2 核心=**inverse_vol vs equal 的 OOS CAGR/Sharpe/MaxDD 对比数字**(以及 Q1 质量、Q3 顺带)。
2. **明确给出"是否支持切 inverse_vol"的结论**(改善 OOS → 支持;无改善/更差 → 不支持,F002 不切)。

**Acceptance（§29 实测）：** 切换依据报告入 git,含 inverse_vol vs equal 的 **OOS 真数字对比** + 明确支持/不支持结论。Gates：backend+trade 门禁绿。

### F002 — cn_attack 两模式 live 默认切 inverse_vol（据 F001 确认）（executor: generator）

1. **据 F001 结论**:若支持 → `cn_attack_precompute` 两模式传 `weighting_scheme="inverse_vol"`(targeted);若不支持 → 保持 equal + 升级 planner(诚实,不盲切)。
2. `CnAttackParameters` 全局默认不动(equal);snapshot meta 标注当前 live 权重方案=inverse_vol(供 surface/审计)。
3. **OOS 红卡 + 研究态披露不动**;前端若展示权重方案则标注(可选,双语)。
4. 单测:precompute 两模式产出反映 inverse_vol(高波动票权重更低);equal 全局默认回归(B066/B068 回测不变)。

**Acceptance：** 两模式 precompute 用 inverse_vol;`CnAttackParameters` 默认仍 equal(回测零回归);OOS 红卡在。Gates：backend pytest/ruff 目录上下文/mypy CI-exact + frontend(若动)。

### F003 — Codex L2 验收 + signoff（executor: codex）

**真机批次——signoff 含实测证据（§29）：**
- L1 全门禁。
- **L2 真机(VM,贴真返回)**:切后两模式 precompute 真跑 → `recommendation_snapshot` 权重**反映 1/σ**(同标的下,高波动票权重 < 等权时,贴对比数字)；权重和=1.0(cash 补);OOS 红卡仍渲染;`astock.guangai.ai` /recommendations 两模式新权重生效。
- **零回归**:B068/B066 回测默认 equal 不变;Master/regime/B067 其它行为不破;HEAD≡prod;recent-errors=0。
- 边界:research-only/advisory-only/no 自动下单/no 收益预测。signoff 实测证据逐条贴真观测。

---

## 3. 状态流转 + 不变量

- 小混合批次：`planning → building(F001→F002) → verifying(F003) → done`。
- **不变量**:①回测/研究默认 weighting_scheme=equal 零回归(只改 live producer);②OOS 负/未验证诚实红卡继续显示;③research-only/advisory-only/no-broker/no 自动下单;④Master/regime/B067 其它零回归;⑤§12.10.2/ruff 目录上下文/mypy CI-exact。
- **诚实出口**:F001 若发现 inverse_vol 在 OOS 上**并不**改善(或更差)→ **不切**,F002 保持 equal + 报告说明(尊重数据,不为"已计划"硬切)。
