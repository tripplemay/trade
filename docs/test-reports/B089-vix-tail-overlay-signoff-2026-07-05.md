# B089 — VIX tail-risk overlay（SPY + X% VIXY，基建/研究）Evaluator Signoff（2026-07-05）

> **裁定：全 PASS 2/2 → done。** F001（`trade/analysis/vix_overlay.py` 静态 overlay + MaxDD/CAGR + 4 单测 + tail-loss/carry 对比，generator）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B088 先例），与实现完全隔离，最高怀疑度。
> 核心手段：**从零独立重实现** overlay（月度再平衡 + 月内漂移，不引用被验模块数学）→ 与 demo 逐数字对拍；**独立 re-fetch 复算** 2020 covid 前提（SPY −34% / VIXY +278%）；**独立呈现 decay-drag 全期**（VIXY buy-hold −99.7%）验 carry 未淡化；**mutation-check** 验单测有牙。
> **被验收提交：`29ce6bd`**（feat B089-F001，4 文件 198 行，**零产品策略码**）。HEAD `09d860d` = 其后 chore commit（features.json + progress.json 仅，paths-ignore 不触发 CI，不动产品码）。
> **生产面：无。** `trade/analysis/vix_overlay.py` 为纯研究模块（numpy/pandas），除 test + demo 外无任何 strategy/flagship/workbench/timer/migration 引用（grep 实证）→ 无部署面、无 VM 核实项（如实标注）。

## 0. 本批性质与诚实边界

- **纯研究/基建层**：证静态 X% VIXY overlay on SPY 能机械地减急跌尾部损失（2020 covid MaxDD），代价为 VIXY 结构性 **negative carry**（contango roll cost）拖累长期 CAGR。
- **可测客观非主观 edge**：tail-loss 减（stress MaxDD）与 carry 代价（全期 CAGR）均为机械可复算指标，真实价格 snapshot 上客观展示，不依赖 alpha 主张。
- **spec 点名最大陷阱 = 只报 tail-loss 减不报 carry 代价（吹对冲免费）** → 已独立双证兼得：报告同时量化两面，carry 代价（~1%/yr @ 10%）与 VIXY 全期归零（roll cost）均如实披露，**未吹免费午餐**。
- **诚实 follow-up**：真策略集成（叠 Master/cn_attack）为后续工作，本批不涉，报告已如实标注。
- **role-context「Fixture-only ≠ 策略性能 conclusion」适用性核对**：本批指标在**真实 SPY/VIXY 价格 snapshot**（3894 日 2011–2026）上复算，非合成 fixture；acceptance 主张 = 观测窗口内的 tail-loss/carry 客观对比，未越界宣称普适 alpha → 合规（另见 §3 O2 窗口限定软观察）。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据（独立复算） |
|---|---|---|
| **① 2020 covid 前提独立复算（SPY −34% / VIXY +278%）** | **PASS** | 独立从缓存价格重算 2020-02-19→2020-03-23：**SPY 338.34 → 222.95 = −34.1%；VIXY 11.15 → 42.18 = +278.3%** —— 与 spec/报告前提逐字相等，且与公开史实一致（SPY covid 崩盘 ~−34% peak-to-trough）。VIXY 对股灾负相关对冲极显著 = overlay 价值来源，前提硬证 |
| **② overlay 数字独立重算（不 import 被验模块）** | **PASS** | 从零手写 overlay（月度再平衡回目标 + 月内漂移）+ 自写 MaxDD/CAGR，与 demo 逐数字对拍：pure SPY **CAGR 12.13% / MaxDD −34.1% / 2020 −34.1% / 2022 −25.4%**；+5% **11.80% / −24.9% / −24.9% / −22.8%**；+10% **11.09% / −20.9% / −15.15% / −20.3%** —— 全表机器精度相等。demo 亦逐位复现（`python -m scripts.research.b089_vix_overlay_demo`）。（报告表 2020 10%-overlay 显示 −15.2% = 真值 −0.1515 四舍五入呈现，独立复算同为 −0.1515，非实质差异） |
| **③ tail-loss 减是否真（stress MaxDD 独立复算）** | **PASS** | 10% VIXY：**2020 covid 急跌 −34.1% → −15.15%（近腰斩）**，full MaxDD −34.1% → −20.9%；5% 亦有效（−34.1%→−24.9%）。**急跌 vs 慢熊差异诚实**：2020 急跌对冲极好（VIXY +278%），2022 慢熊对冲弱（−25.4%→−20.3%，VIXY 慢熊少暴涨）——报告如实区分「对冲的是急跌 tail 非慢熊」，未夸大 |
| **④ negative carry 代价诚实量化（对冲非免费，焊死）** | **PASS** | 独立复算全期 CAGR drag：+5% 拖累 **0.33pp/yr**（12.13→11.80），+10% 拖累 **1.04pp/yr**（12.13→11.09）——与报告 ~1%/yr 相等。**decay-drag 长期硬呈现**：独立算 VIXY buy-hold 全期 = **−99.7%**（CAGR −31.84%/yr，contango roll cost 归零特性）、同期 pure SPY +486.5%。报告显式量化 VIXY「长期巨亏 roll cost」「牺牲长期收益换尾部保护」→ **carry 未被淡化**，全期呈现（非只挑危机窗），两面诚实兼得 |
| **⑤ X% 先验无扫参（grep）** | **PASS** | grep `sweep\|grid\|optim\|tune\|best\|itertools` 于模块+demo+单测 = **无任何扫参/网格/优化模式**。唯一命中 `for w in _WEIGHTS`，`_WEIGHTS = (0.05, 0.10)` = **两档先验硬编码**（注释「先验(禁扫参)」），非 grid search；两档均全登记于报告表（按最弱口径亦全披露）。禁扫参焊死 |
| **⑥ 窗口诚实（VIXY 2011 起）** | **PASS**（含软观察 O2） | 报告 header 明标窗口 **3894 日 2011–2026**，VIXY 2011 起。数据实测 first=2011-01-04。观测窗口如实披露。软观察 O2：报告陈述了窗口但未显式标注「缺 2008 GFC」/「对冲结论限定观测窗口」（prep doc 已注「缺 2008」）——非阻断，见 §3 |
| **⑦ 零回归（策略/flagship/生产 0 行）** | **PASS** | F001 全提交仅动 **4 文件**（`vix_overlay.py` 61 + 单测 35 + demo 79 + 报告 23），**产品策略码 0 行**；`trade/strategies/`+`workbench/` 对 `vix_overlay` **零引用**（grep 实证），模块仅被 test/demo 引用 → flagship/策略/生产路径字节不受影响 |
| **⑧ Gates + 单测有牙 + CI 绿 + HEAD≡prod** | **PASS** | 本地：`mypy trade/analysis/vix_overlay.py` = Success；`ruff check .` = All passed；**4 单测本地实跑 4 passed**。**mutation-check（有牙）**：将月度再平衡 reset 变异为 no-op（禁再平衡）→ `test_overlay_rebalances_at_month_change` **FAIL**（`assert 0.0101 < 1e-12`）→ 再平衡机械断言有牙；还原后 `git status` 空。**CI**：feat `29ce6bd` 的 **Python CI（7m24s，最严 mypy trade+根 ruff+root pytest）+ Workbench Backend CI（9m22s）全绿**。HEAD `09d860d` = chore-only（features/progress，paths-ignore 合法不触发）。**HEAD≡prod**：纯研究模块无生产面/无部署项，如实标注 |

## 2. 核心不变量复核（最高怀疑度）

**spec 点名最大陷阱 = 只报 tail-loss 减、隐去 carry 代价（吹对冲免费）→ 已独立双证两面诚实兼得：**
1. **tail-loss 确减**（独立重算，非引用报告）：10% VIXY 令 2020 covid 急跌 −34.1%→−15.15%（近腰斩），full MaxDD −34.1%→−20.9%。
2. **carry 代价确焊死量化**（独立重算 + decay-drag 全期硬呈现）：10% overlay 年化拖累 1.04pp/yr；VIXY buy-hold 全期 −99.7% 的 roll-cost 归零特性已在报告显式呈现（非只挑危机窗）→ 对冲**非免费**，报告未淡化 drag。

**2020 前提**经独立 re-fetch 复算硬证（SPY −34.1% / VIXY +278.3%）；**无扫参**经 grep + 两档先验硬编码硬证；**零回归**经 4 文件 diff + 策略/生产零引用 + 产品码 0 行硬证。

## 3. 软观察（非阻断，供后续批参考）

- **O1 — 「月度再平衡令 carry 温和 / 比 buy-hold 高效」措辞略强**（非阻断）：报告称「月度再平衡（涨后卖/跌后买）令 carry 代价温和——比 buy-hold VIXY 高效」。独立复算：10% **月度再平衡 CAGR 11.09%**（drag 1.04pp）实际 **低于** 静态 10% **从不再平衡** buy-hold（CAGR 11.35%，drag 0.78pp）——因不再平衡时 VIXY 自然衰减至 ~0、组合渐变为纯 SPY，drag 反而更小；月度再平衡持续「喂」衰减资产。故「carry 温和」的真因 = **VIXY 权重小（10%）+ SPY 强牛市主导**，非再平衡效率。「比 buy-hold VIXY 高效」字面仅对「纯 100% VIXY（−32%/yr）」成立（平凡真）。**核心两面诚实不受影响**（drag 数字本身正确、全期披露）；后续如入策略，建议将再平衡的 carry 因果措辞据实修正。
- **O2 — 窗口限定未显式 caveat**（非阻断）：报告陈述了观测窗口（2011–2026）但未显式标注 backtest **缺 2008 GFC**、及「对冲有效性结论限定观测窗口（此段为 SPY +486% 的重牛市、仅 2 次显著崩盘）」。prep doc 已注「VIXY 2011 起（缺 2008）」。窗口本身已披露 → 非阻断；后续真策略集成或对外结论时建议补窗口限定 caveat。

## 4. 结论

**B089 VIX tail-risk overlay 2 features 全 PASS → done。**
2020 covid 前提经**独立 re-fetch 复算**硬证（SPY −34.1% / VIXY +278.3%，与史实一致）；overlay 全部数字（CAGR/MaxDD/stress MDD）经**从零独立重实现**逐数字对拍机器精度相等；tail-loss 减经独立复算证实（2020 −34%→−15%，full MaxDD −34%→−21%）；negative carry 代价经**独立复算 + decay-drag 全期硬呈现**核实诚实焊死（10% drag 1.04pp/yr；VIXY buy-hold −99.7% roll-cost 归零已披露、非只挑危机窗）；X% 先验经 grep + 两档硬编码硬证无扫参；零回归 = 4 文件 diff + 策略/生产零引用 + **产品策略码 0 行**；Gates 全绿（mypy/ruff clean，4 单测 pass，mutation-check 证再平衡断言有牙）+ **Python CI/Backend CI 绿（29ce6bd）**；**无生产面**（纯研究模块，HEAD≡prod 无部署项，如实标注）。两项软观察（O1 再平衡 carry 因果措辞 / O2 窗口限定 caveat）均**非阻断**、不触发 spec 最大陷阱（报告已两面诚实量化 carry），供后续真策略集成参考。
