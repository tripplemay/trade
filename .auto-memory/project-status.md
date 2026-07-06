---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B099 ✅ done（2026-07-06, 1g+1c, Workflow-build）** smart-money **机构建仓 first-look（免费季度 `stock_institute_hold`）→ NO-GO/INCONCLUSIVE**。research-only(4 文件 scripts/research+tests+report, 产品码 0)。免费季度机构持股(20 季 49193 行 4995 股)机构数变化/持股比例增幅=加仓信号→披露滞后入场→rank-IC+回测。★裁定 **全 PASS 2/2**。独立验收(代 Codex, 隔离, 最高怀疑度, 本机数据缓存齐→真 20 季复算非 fixture): ★★命门1 PIT 无前视=入场推到披露 deadline 次月 1 日(Q1→5/1…Q4→次年 5/1), 独立审计 20/20 季 0 违规(手核 2020Q1/2021Q1/2024Q2 入场均晚于截止)+12 测复跑绿; ★★命门2 外推边界(本批最关键)=报告**两处**明确"不证伪 ¥200 日频 top_inst"(免费季度滞后≠付费日频 T+1, 归因=滞后而日频砍滞后)→**未过度外推**, caveat 真实且严谨; ★★命门3 归因坐实(我构造 look-ahead 对照)=**作弊版(报告期末入场) primary t=+2.44 显著/IC+0.031 vs 合规 PIT 版 t≈0/IC≈0**→坐实"滞后吃掉 edge, 信号本身有信息", 同时**独立强化外推边界**(短延迟有 edge→日频值得测); 命门4 IC 逐位复算一致+GO 门槛(IC≥0.03&t≥2)四组无一达标→NO-GO 唯一正确+回测+49% 是负 IC 却正超额=beta/size 幻觉诚实诊断; 命门5 覆盖诚实(价格宇宙 25.4% 大盘 tilt 已披露)+无扫参(grep 硬编码先验, 全量报告非择优); 命门6 零回归(0 产品码 grep 无消费者)+L1 12 测+ruff 绿+CI 三绿(Python/Backend/Deploy@d3fc880 success)+HEAD≡prod。signoff docs/test-reports/B099-institutional-holdings-first-look-signoff-2026-07-06.md。
- **★含义**: smart-money **免费信号三支均测尽**(机构席位覆盖限 B077 INCONCLUSIVE / 游资 B094 NO-GO / 机构建仓季度 B099 NO-GO 滞后元凶)→免费路径无可靠 edge; **决定性测试仍是付费 ¥200 Tushare 日频 top_inst**(本批不证伪反佐证及时性关键→值得有界付费试)。待用户决策。
- **B098 ✅ done** test-automation P5-F1 signoff 自动起草工具(`scripts/gen_signoff_draft.py` 598 行+23 测, additive 零产品码, 全 PASS 2/2, 铁律#4 工具不僭越判断结构证+对抗测试, 详见 B098 signoff)。**generator-buildable 部分全落地(P0–P5-F1)**; 剩 P5-F2=evaluator 流程域。
- **B097 ✅ done** P3 生产 synthetic 监控+rollback 接线+定时 canary(PASS 3/3)。★env: 活生产 API=`trade.guangai.ai`(非 astock.guangai.ai)。
- **B096 ✅** LLM-judge 语义层。**B095 ✅** 确定性语义 lint。**B094 ✅** 游资 NO-GO。**B093 ✅** hk_china real NO-GO(保 proxy)。**B092–B074 ✅**。
- **接续**：★战略决策待用户(免费策略研究无强 edge)。backlog 剩: A股聪明钱[机构 ¥200 待用户] + test-automation **P5-F2**(独立评审流程, 铁律 4, evaluator 域) + residual-engine(触冻结待用户)。34+ learnings 待用户确认。★key 曾对话明文暴露→建议用户用完轮换(与 commit 安全独立)。

## 遗留 / soft-watch
- **B098 S1/S2/S3**（非阻断）：§5 门禁 echo 整个 generator_handoff.summary 叙事含 generator 自拟框架措辞(明标自报+置机械半段+§7 裁定空占位→不破铁律4, 未来加固可只 echo 结构化门禁数字) / commit-range 启发式 diffstat 纳入开批 chore 无关文件(机械正确非 bug, 范围宽于单一 feature) / 本机 py3=3.9.6 无 ruff/mypy 须 venv。
- **B097 S1/S2/S3**（非阻断）：actionlint deploy.yml SC2087 warning 全 pre-existing 意图正确 / synthetic→rollback 集成路径待下次产品部署 exercise(组件已单独证) / environment.md 域名已修正 trade.guangai.ai。
- **B096 O1/O2/O3**（非阻断）：frontend CI Playwright E2E smoke flake(backend-only 无关) / 语义 judge 尚无 runtime-gate 消费者(advisory) / cassette 按录制顺序重放。
- **B095 O1/O2/O3**（非阻断）：确定性 pre-filter 固有'宁漏勿误'漏报口 / 小写 allowlist 演进需守证据门 / lint 尚无 runtime/CI 消费者(advisory-only)。
- **B094/B093**（归档）：B094 events.csv 重复键未去重(dedup 后仍 NO-GO)/priced 1,279 非满 1,500；B093 proxy 弱基准+单 regime+幸存者=结构性天花板。**B089–B081**：见旧注。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
