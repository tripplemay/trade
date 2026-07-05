# B088 — Smoothed / feedback volatility targeting（BL-B013-D1，基建/研究）Evaluator Signoff（2026-07-05）

> **裁定：全 PASS 2/2 → done。** F001（`trade/analysis/vol_targeting.py` 三控制律 + 4 单测 + turnover 对比，generator）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B087 先例），与实现完全隔离，最高怀疑度。
> 核心手段：**从零独立重实现**三控制律公式（不引用被验模块的数学）→ 与被验模块逐点对拍机器精度相等；**独立复算** turnover + 控波两指标；**PIT 扰动审计**（只动 rv[T] 看 e[0..T-1] 是否变）验无前视；**mutation-check** 验单测有牙。
> **被验收提交：`868f513`**（feat B088-F001，6 文件 255 行，**零产品策略码**）。HEAD `7473e91` = 其后 docs-only 提交（`docs/research/next-batch-prep-vix-overlay.md` 26 行，不动状态机/产品码）。
> **生产面：无。** `trade/analysis/vol_targeting.py` 为纯研究模块（numpy/pandas，无 akshare），除 test + demo 外无任何 strategy/workbench/timer/migration 引用 → 无部署面、无 VM 核实项（如实标注）。

## 0. 本批性质与诚实边界

- **纯研究/基建层**：证 open-loop vol-targeting 的 turnover spike 可由 **smoothing**（EWMA 平滑 rv 估计）与 **feedback**（partial-adjustment 比例控制）两控制律机械性地降低，且 realized vol 仍 ≈ target。
- **合成可测非主观 edge**（避 B084 式过度乐观）：turnover 减是控制律机械性质，合成 regime-vol 序列即可客观展示，不依赖真实收益 alpha 主张。
- **诚实 follow-up**：真策略集成（入 risk_parity / 对真 US 收益）为后续工作，本批不涉，报告已如实标注。
- **role-context「Fixture-only ≠ 策略性能 conclusion」适用性核对**：本批 acceptance 不主张任何真实收益/DD 优势，只主张**控制律机械性质 + 合成 turnover/控波对比**——属可测机械性质，非真实数据收益 conclusion，故合成验收合规（报告未越界宣称真实 alpha）。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算） |
|---|---|---|
| **① 三控制律公式核实（先验口径）** | **PASS** | 从零独立重实现三律（causal EWMA 手写 α=1−2^(−1/hl)；feedback 手写 partial-adjust 递归；open-loop min(target/rv,max)），与被验模块在 demo 完整合成序列上逐点对拍：**MAXDIFF open_loop=0.0 / smoothed=1.0e-15（浮点）/ feedback=0.0**。公式与 spec §0 完全一致：open-loop `min(target/rv_t,max)`；smoothing `min(target/ewma(rv,hl)_t,max)`；feedback `e_t=e_{t-1}+k·(ol_t−e_{t-1})`，`e_0=ol_0`。**k=1 恒等 open-loop** 经代数复算 `np.allclose(fb(k=1),ol)=True`（单测 `test_feedback_k1_recovers_open_loop` 亦 PASS） |
| **② turnover 减是否真（独立重算合成对比）** | **PASS** | 独立脚本（自建合成序列 seed=42，自写 turnover=Σ\|Δe\|）复算：**open_loop 9.67 / 100%；smoothed 4.46 / 46.1%（−54%）；feedback 8.50 / 87.9%（−12%）** —— 与报告表逐数字相等。demo 亦逐位复现（`python -m scripts.research.b088_vol_targeting_demo`）。**机械性质压测**：200 条随机 vol 序列上 feedback TV > open-loop TV 违例 **0/200**、smoothed 违例 **0/200** → turnover 减在此序列族上机械成立（feedback 严格：低通滤波 TV 不增；见 §3 O1） |
| **③ 控波核实（realized vol vs target 三律对比，不牺牲控波）** | **PASS** | 独立复算 realized vol（`exposure.shift(1)*ret` 无前视回测）：**open 0.0886/1.11x；smoothed 0.1044/1.30x；feedback 0.0906/1.13x**——与报告相等。**两面诚实**：smoothing 换来最大 turnover 减（−54%）但控波最松（1.30x）；feedback turnover 减最小（−12%）但控波几乎不损（1.13x ≈ open-loop 1.11x）。报告本身已算此面并双向披露 → **turnover 减未以失控波为代价**（feedback 兼得；smoothing 的松弛已如实标注为权衡）。realized vol 普遍 >target（1.1–1.3x）= 21 日 rv 估计滞后 regime 切换，报告标注为 vol-targeting 已知局限、非本律引入——核实无误 |
| **④ 反馈律无前视（PIT）** | **PASS** | **扰动审计**：仅将 rv[T]（末点）×3，三律的 e[0..T−1] 最大变化 = **0.00e+00**（open/smoothed/feedback 全 0）→ 无任一律回看未来。逐律核：open-loop 只用 rv_t；smoothed 用 `.ewm(halflife).mean()`（adjust=True 默认 = causal，仅历史+当前）；feedback 前向递归 e_t 仅依赖 e_{t-1}+ol_t。回测侧 `exposure.shift(1)*ret`（t−1 决策施于 t 收益）亦无前视 |
| **⑤ 参数无扫参（grep 先验常量）** | **PASS** | grep `sweep\|grid\|scan\|optimi\|best\|tune\|itertools\|for..in(halflife/target/k)` 于模块+demo+单测 = **无任何扫参/网格/优化模式**。三先验常量硬编码模块级：`TARGET_VOL=0.08 / SMOOTH_HALFLIFE=21 / FEEDBACK_K=0.5 / MAX_EXPOSURE=1.0`（来源 risk_parity + 文献口径），函数签名以之为默认值。禁扫参焊死 |
| **⑥ 零回归（risk_parity 产品码字节不变）** | **PASS** | `git diff 32ddd5c(B087-done)..HEAD -- trade/strategies/risk_parity.py` = **空（字节相同）**；B088 全提交仅动 6 文件（`vol_targeting.py` 74 + 单测 42 + demo 76 + spec 31 + 报告 32 + backlog −15）→ **产品策略码 0 行**。除 test/demo 外无任何 strategy/workbench 引用该模块（grep 实证）→ 全 flagship/策略路径不受影响 |
| **⑦ Gates + 单测有牙 + CI 绿** | **PASS** | 本地：`mypy trade/analysis/vol_targeting.py` = Success；`ruff check` = All checks passed；**4 单测本地实跑 4 passed**。**mutation-check（有牙）**：将 feedback `prev=prev+k*(value-prev)` 变异为 `prev=float(value)`（禁用 partial-adjust=退化成 open-loop）→ `test_feedback_partial_reduces_turnover` **FAIL**（`assert 1.0 < 1.0`，turnover 相等非更小）→ 该 turnover-减断言有牙；还原后 `git status` 空。**CI**：F001 push `868f513` 的 **Python CI（7m21s）+ Workbench Backend CI（8m41s）全绿**（Python CI = mypy trade+根 ruff+root pytest 最严门禁，已覆盖本模块）。HEAD `7473e91` 为 docs-only（paths-ignore 合法不触发 CI），其后无任何代码改动 |

## 2. 核心不变量复核（最高怀疑度）

**spec 点名最大陷阱 = turnover 减但控波失效（vol 偏离 target）→ 已独立双证兼得：**
1. **turnover 确减**（独立重算，非引用报告）：feedback −12% / smoothing −54%，200 随机序列 0 违例。
2. **控波未失**（独立重算 realized vol）：feedback 1.13x ≈ open-loop 1.11x（几乎不损）；smoothing 1.30x 的松弛为 EWMA 平滑对 regime 切换的已知代价，报告双向诚实披露、未粉饰。→ 两指标兼得（feedback 尤佳），非以失控波换 turnover。

**无前视**经扰动审计硬证（改 rv[T] 不动历史 exposure）；**无扫参**经 grep + 常量硬编码硬证；**零回归**经 risk_parity 字节 diff 空 + 产品码 0 行硬证。

## 3. 软观察（非阻断，供后续批参考）

- **O1 — 「机械性质」对 smoothing 的严格性措辞**（非阻断）：turnover 减对 **feedback** 是**严格机械**（partial-adjust = 对 open-loop 序列的低通滤波，非负权求和归一 → 总变差 TV 不增，数学可证）；对 **smoothing** 是**经验稳健**（EWMA 平滑 rv 后经非线性 1/x + clip，非严格 TV 不增定理，但本批合成序列 + 200 随机序列 0 违例）。spec/报告「可在任意 vol-varying 序列上证」对 smoothing 略强于严格已证，但已由合成 + 随机压测经验证实、且报告诚实呈现权衡 → 不影响裁定。后续如入策略，建议对 smoothing 的 turnover 减以「经验稳健」而非「定理」措辞。
- **O2 — realized vol 系统性 >target（1.1–1.3x）**：非本控制律缺陷，而是 21 日 trailing rv 估计滞后 regime 切换的通用 vol-targeting 局限（切换期用旧 vol → 短暂超配）。报告已标注。真策略集成时若要收敛控波，可考虑更短 halflife 或 regime-aware rv 估计（follow-up，非本批缺口）。

## 4. 结论

**B088 smoothed/feedback vol-targeting 2 features 全 PASS → done。**
三控制律公式经**从零独立重实现**逐点对拍机器精度相等（open/feedback 精确、smoothing 1e-15 浮点）；turnover 减经**独立重算**证实（open 9.67 / smoothed 4.46 −54% / feedback 8.50 −12%，200 随机序列 0 违例）；控波经**独立重算** realized vol 核实两面诚实（feedback 1.13x 几乎不损 / smoothing 1.30x 松弛已披露 → turnover 减未牺牲控波）；无前视经**扰动审计**硬证（改 rv[T] 不动 e[0..T−1]）；无扫参经 grep + 先验常量硬编码硬证；零回归 = risk_parity 字节不变 + **产品策略码 0 行**；Gates 全绿（mypy/ruff clean，4 单测 pass，mutation-check 证 turnover-减断言有牙）+ **Python CI/Backend CI 绿（868f513）**。**无生产面**（纯研究模块，无部署/timer/migration，如实标注）。两项软观察（O1 smoothing 机械性质措辞 / O2 rv 估计滞后）均非阻断、供后续真策略集成参考。
