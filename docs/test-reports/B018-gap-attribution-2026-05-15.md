# B018-gap-attribution-2026-05-15

## 1. 总体结论
- Batch: `B018-gap-root-cause-attribution`
- Result: PASS
- Scope: B013 / B010 对 static 60/40 的 gap root-cause attribution + 三轴参数 sweep
- Real-data status: `ran`
- Snapshot: `regime-adaptive:b69883b08eedea7d`
- 结论：`l2_vol_scaling` 是主导拖累，`l1_gating` 是次级拖累；可调轴主要是 `vol_target` 和 `cadence`，`universe` ablation 大多受 defensive 资产不变量限制，解释力弱于前两者。

## 2. 真实数据基线回顾
窗口：`2020-06-01..2022-12-31`（calm window），stress 子窗口：`2020_q1_q4` 与 `2022_full_year`

| strategy | calm ending | calm gap vs 60/40 | 2020 max DD | 2022 max DD | note |
|---|---:|---:|---:|---:|---|
| B010 | 103,997.77 | +2,201.00 | -0.19% | -1.06% | calmer branch, low DD but still above 60/40 |
| B013 | 102,268.55 | +471.79 | -1.62% | -0.51% | closer to 60/40 on calm window, but not a direct win on gap magnitude |

- 两条策略在 calm window 都没有被 60/40 反超到负值，但 `B013` 的净超额更小，说明它更像“接近 60/40 的风险调整后折中”，不是绝对收益主导。
- 2020 stress 子窗口更苛刻；`B010` 和 `B013` 都仍然守住 `-15%` 线，说明 B018 关注的是研究归因，不是安全失败。

## 3. 按资产归因
calm window 下的 top assets：

| strategy | top positive assets | 说明 |
|---|---|---|
| B010 | `VEA +2019.89`, `SPY +1621.20`, `GLD +656.16`, `SGOV +13.11` | 权益资产贡献正向 P&L，但被 L2 风控层明显稀释 |
| B013 | `SGOV +15490.16`, `GLD +5738.99`, `VEA +3190.44`, `DBC +2784.47` | 防守资产对总收益贡献很大，但这也意味着 calm period 的 upside 被 defensive sleeve 吃掉了一部分 |

- `B010` 更像“少量防守 + 轻度风控缩放”的拖累模型。
- `B013` 的正贡献更多来自防守资产与商品/债券混合，但这并没有自动转化成更大的绝对收益 gap 优势。

## 4. 按层归因
calm window 下的 layer contributions：

| strategy | layer | contribution | 结论 |
|---|---|---:|---|
| B010 | `l2_vol_scaling` | -6,245.98 | 主拖累，说明 8% / 类似波动率目标把总暴露压得过低 |
| B010 | `defensive_routing` | 0.00 | 本批不是主要问题 |
| B013 | `l2_vol_scaling` | -45,213.61 | 仍然是第一拖累，说明问题不在 L1 gating 本身 |
| B013 | `l1_gating` | -26,715.22 | 次级拖累，说明 activation policy 不是根因，但会放大保守化 |
| B013 | `l3_crisis_cut` | 0.00 | 对 calm window 不是关键因子 |
| B013 | `defensive_routing` | 0.00 | 不是这轮 gap 的主来源 |

- 这组结果支持同一个结论：**gap 的中心不是“选错了 gating / weighting 方法”，而是总暴露与 defensive 分配太保守**。

## 5. vol_target sweep

| target | B010 ending / gap / 2020 DD / 2022 DD | B013 ending / gap / 2020 DD / 2022 DD |
|---|---|---|
| 0.05 | 102,484.59 / +687.82 / -0.12% / -0.65% | 101,872.30 / +75.53 / -0.87% / -0.24% |
| 0.08 | 103,997.77 / +2,201.00 / -0.19% / -1.06% | 102,268.55 / +471.79 / -1.62% / -0.51% |
| 0.10 | 105,013.32 / +3,216.55 / -0.23% / -1.33% | 102,891.28 / +1,094.51 / -2.05% / -0.68% |
| 0.12 | 106,034.20 / +4,237.44 / -0.28% / -1.61% | 103,366.86 / +1,570.09 / -2.68% / -0.86% |
| 0.15 | 107,494.10 / +5,697.33 / -0.35% / -2.01% | 104,904.51 / +3,107.74 / -3.27% / -1.12% |

- `vol_target` 越高，ending value 越高，但 2022 DD 也同步恶化。
- `B010` 这条线更像“稳态风险压制”，`B013` 则更明显地表现出高波动目标带来的收益与回撤交换。

## 6. universe / cadence sweep

### 6.1 Universe ablation

| variant | B010 ending / gap / 2020 DD / 2022 DD | B013 ending / gap / 2020 DD / 2022 DD | note |
|---|---|---|---|
| full | 102,947.57 / +1,150.81 / -0.29% / -0.70% | 102,268.55 / +471.79 / -1.62% / -0.51% | control |
| drop_stabilizers | 103,230.78 / +1,434.01 / -0.42% / -1.11% | 103,430.19 / +1,633.42 / -1.63% / -1.45% | higher ending, but stress DD worsens |

- `drop_sgov`, `spy_ief`, `spy_only` 这几类 variant 在本批里大多被 defensive-asset / core-asset 不变量挡住，或者不适合作为可比的真实研究分支。
- 结果说明 `universe` 不是最优第一改动点：能跑的 variant 往往只是把收益和回撤重新分配，并没有形成稳定的 dominance。

### 6.2 Cadence sweep

| cadence | B010 ending / gap / 2020 DD / 2022 DD | B013 ending / gap / 2020 DD / 2022 DD | note |
|---|---|---|---|
| monthly | 103,997.77 / +2,201.00 / -0.19% / -1.06% | 102,268.55 / +471.79 / -1.62% / -0.51% | baseline |
| quarterly | 103,036.39 / +1,239.63 / -0.19% / -0.12% | 105,842.62 / +4,045.86 / 0.00% / -1.28% | B010 的 DD 明显改善 |
| semiannual | 100,527.06 / -1,269.70 / 0.00% / -0.13% | 101,366.65 / -430.11 / 0.00% / 0.00% | 更保守，收益明显下降 |
| annual | 100,422.86 / -1,373.91 / 0.00% / 0.00% | 99,568.18 / -2,228.59 / 0.00% / 0.00% | 最低 DD，但放弃了太多上行 |

- 对 `B010` 来说，`quarterly` 是一个很强的平衡点：2022 DD 从 `-1.06%` 直接收敛到 `-0.12%`，ending 只小幅回落。
- 对 `B013` 来说，`quarterly` 会显著抬高 ending value，但 2022 DD 也会拉高；`annual` 是纯低风险形态，但收益代价太大。

## 7. Pareto recommendations

### low-DD：`B010 / annual`
- Ending value: `100,422.86`
- Gap vs 60/40: `-1,373.91`
- 2020 max DD: `0.00%`
- 2022 max DD: `0.00%`
- Turnover: `2.08`
- Trade-off: 这是最稳的点，但它把 calm-window 的绝对收益也让出去了一部分。

### balanced：`B010 / quarterly`
- Ending value: `103,036.39`
- Gap vs 60/40: `+1,239.63`
- 2020 max DD: `-0.19%`
- 2022 max DD: `-0.12%`
- Turnover: `2.44`
- Trade-off: 这是本批最像“可继续研究的默认候选”的点，收益和回撤都比 monthly 更均衡。

### high-return：`B013 / target_vol=0.15`
- Ending value: `104,904.51`
- Gap vs 60/40: `+3,107.74`
- 2020 max DD: `-3.27%`
- 2022 max DD: `-1.12%`
- Turnover: `10.64`
- Trade-off: 这是高收益方向，但换来的是更高 turnover 和更明显的 stress DD。

> 备注：`vol_target` 侧的 raw sweep 里，`B010 / 0.15` 是全表最高 ending value 点；这里把 high-return 点保留在 `B013` 方向，是为了让推荐覆盖 regime-adaptive 分支。两种读法都成立，但后续 retune 批次应明确按同一 branch 比较，不要混淆。

## 8. 跟进建议
- 建议新增 backlog：`BL-B018-S1`，追踪 `B010` 的 cadence / vol-target 联合 retune，优先看 `quarterly` 与 `10%~12%` 波动率目标附近的组合。
- 这不是 B018 的策略改动范围；B018 只负责把“哪一层在拖累、哪一层值得调”讲清楚。

## 9. 研究声明
- 本批次所有输出均为 research-only。
- 不授权 paper / live / broker / AI 执行。
- 本批次不修改任何策略默认参数、spec 或 broker 相关边界。

_Sidecar: `docs/test-reports/B018-gap-attribution-2026-05-15.json`_
