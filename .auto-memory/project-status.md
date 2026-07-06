---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B100 ✅ done（2026-07-06, 1g+1c, Workflow-build）** 残差动量**完整引擎 A/B**（research-only wrapper）→ **INCONCLUSIVE**。在**冻结** cn_attack `build_cn_portfolio` 上跑两遍，唯一差动量输入(BASELINE=裸动量, VARIANT=B085 残差)，同宇宙/调仓/skip/top_n=25/cap/等本金/成本。★裁定 **全 PASS 2/2**。独立验收(代 Codex, 隔离, 最高怀疑度, 真 169MB PIT 面板复算非 fixture): ★命门1 BLOCKING=**整批 `trade/` 产品码 0 行改动**(`git diff` 空), 冻结 flagship 零改/read-only import/不 mark validated/不触 data_root→research-only 坐实; 命门2 公平=两臂唯一差动量(单测 bit-identical 锁)+等本金双簿+窗口匹配(均 87 调仓 2019-04-30→2026-06-18)+残差 β PIT 手核(000723.SZ β=1.121 手算=引擎 1e-9, 未来变异不变)+turnover 双臂同模型(soft-watch: 残差 252d β 窗致 scored-pool 中位少 19/1250≈1.5%, 尾部名不影响 top-25 选股, benign 非不公); 命门3 独立逐位重算=BASELINE CAGR 0.1719/Sharpe 0.640 vs VARIANT 0.1586/0.608(Δ−1.33pp/−0.032)与报告吻合→INCONCLUSIVE 唯一正确(GO 需 Δ≥+2%&+0.15 未达)+year-by-year 诚实(残差仅 2020 胜, worst sub-window 略 worse 未掩盖)+honest frame 引 B085 t=1.98 逐字核对; 命门4 禁扫参(grep 净, top_n 冻结默认非扫)+零回归+L1 8 测(变异 1.0→2.0 FAIL 有牙)+ruff/mypy 绿+CI(Python/Backend@2579da5+Deploy@0daf6f6 success)+HEAD≡prod。signoff docs/test-reports/B100-residual-momentum-engine-ab-signoff-2026-07-06.md。
- **★含义**: 残差引擎 A/B=INCONCLUSIVE，残差**边际 trailing** 裸动量→**不支持切入 flagship**；与 B085 前置筛(delta t=1.98 borderline)一致(edge 真实但边际)。**flagship 维持裸动量**(OOS 红卡冻结)；采纳残差=**用户决策非本批**。
- **B099 ✅ done** smart-money 机构建仓免费季度 first-look→**NO-GO**(滞后元凶, look-ahead 对照坐实作弊版 t=+2.44 vs 合规 t≈0; **不证伪 ¥200 日频反佐证及时性**)。全 PASS 2/2。→免费信号三支(机构席位 B077/游资 B094/机构建仓 B099)均测尽无 edge; **决定性=付费 ¥200 日频 top_inst** 待用户。
- **B098 ✅** P5-F1 signoff 起草工具(additive, 铁律#4 不僭越判断)。**B097 ✅** 生产 synthetic+canary+rollback(活生产 API=`trade.guangai.ai` 非 astock)。**B096–B074 ✅**。
- **接续**：★战略决策待用户(免费策略研究无强 edge)。backlog 剩: A股聪明钱[机构 ¥200 待用户] + test-automation **P5-F2**(独立评审流程, evaluator 域, 注: c5694f7 已固化 evaluator.md §33) + residual-engine(B100 已测 INCONCLUSIVE, 采纳待用户)。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。

## 遗留 / soft-watch
- **B100 S1/S2/S3**（非阻断）：残差臂 scored-pool 中位少 ~1.5%(252d β 窗内生, 不影响 top-25 选股, 未来定论可取两臂交集复核) / Δ−1.33pp 落单条 7 年路径噪声带(不证残差劣亦不支持采纳) / 复算 json 本机 gitignored(报告 md 承载全数字可复现)。
- **B098/B097**（非阻断）：§5 门禁 echo generator_handoff 叙事(明标自报, 不破铁律4) / commit-range 启发式 diffstat 纳开批 chore / synthetic→rollback 集成待下次产品部署 exercise / environment.md 已修 trade.guangai.ai。
- **B096–B093**（归档）：judge/lint advisory 无 runtime-gate 消费者 / 确定性 pre-filter 宁漏勿误 / B094 events 未去重(dedup 后仍 NO-GO) / B093 proxy 结构天花板。**B089–B081**：见旧注。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。**残差动量 B100 A/B INCONCLUSIVE，不切入。**
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点(承接 §30)；test-automation roadmap P0–P5 全完→backlog 移除。
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
