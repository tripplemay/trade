---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B093 ✅ done（2026-07-05, 决策级重跑, round1 一轮闭环）** hk_china 真个股 vs proxy 决策级重跑(B091 解锁, 1g+1c, Workflow-build)。修 B091-O1 close-NaN 残留(close=wide.iloc[-1]→wide.ffill().iloc[-1] 各票自身最后有效 close)+matched top_n=2 公平对照+携四 caveat。★裁定 **NO-GO(保 ETF-proxy)**: 公平 matched 上 real +2.97%/Sharpe 0.437/MaxDD -9.20% **不胜** proxy +2.75%/0.522/-3.87%(Sharpe 更差+回撤 2.4x 深); 真 sleeve 参与 0→72%(B091 warmup, close-NaN 修贡献 0); 唯一有利 top6 Sharpe 0.616 = breadth artifact matched 消失。独立验收(代 Codex,隔离): ★close-NaN 修零回归 proxy 单日历 25 信号日 bit 级 0 mismatch; ★修 immaterial to verdict(matched real 指标 fixed=buggy bit 级恒等); ★flip 恰 2 票/1 季(2023-09-29)均不在 top-rank, 2024-03 Good Friday 悬念解为 shared 信号日 03-28 避假日→0 flip; ★NO-GO 与数字一致(B069/B076 verdict-gating, 幸存者顺风美化 real 使 NO-GO 反更稳); research-only(trade/ 仅 factors.py)+门禁全绿+CI 三绿(b5c9a10)+HEAD≡prod。signoff docs/test-reports/B093-hk-china-real-vs-proxy-signoff-2026-07-05.md。
- **B092 ✅ done** B055 US 进攻选股 first-look(research-only)。裁定 **INCONCLUSIVE**(对同宇宙 EW 基线 OOS Sharpe 1.45<1.54 edge-decay→不推荐建全 P1)。signoff B092-...-2026-07-05。
- **B091 ✅** 修 above_200d_ma 多日历 MA bug(真根因,各票自身日历)。**B090 ✅** hk_china 真数据重测(发现 calendar bug)。**B089/B088 ✅** VIX/vol-targeting。**B087 ✅** deploy-chain。**B086–B074 done**(B077 NOT-GO)。
- **接续**：★战略决策待用户(P0-P2 无强 edge; B092 US 攻击无 OOS edge; **hk_china real-stock 悬案 B063 以来闭合=NO-GO 保 proxy**)。backlog 剩 3: A股聪明钱[¥200 Tushare 待用户] + test-automation P3-P5(基建) + residual-engine(触冻结待用户)。34 learnings 待用户确认。

## 遗留 / soft-watch
- **B093 O1/O2/O3**（非阻断）：报告未溯源 2024-03 shared-date 03-28 机制(文档 gap, 已独立坐实) / proxy 本身弱基准(已注) / 25 季 SGOV-floored 单 regime+幸存者=结构性天花板窗口不可扩(若重访须 PIT 无偏宇宙+更长窗)。
- **✅ B091 O1(close-NaN 残留) / B091 O2(重跑无 backlog 条目) / B090 O2(决策级重跑待更长窗+matched)= B093 已全部收口**：close-NaN 已修+证 immaterial; matched top_n=2 已做; 决策级 NO-GO 已下。
- **B089/B088**：carry/turnover 措辞略强+窗口 caveat。**B087/B086/B081**：见旧注。**B090 O1**（研究脚本未纳 mypy CI）非真缺陷。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实, real-stock live 不激活）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
