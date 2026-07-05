---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B090 ✅ done（2026-07-05, round1 一轮闭环）** hk_china 真数据重测(BL hk-china-real-data-retest, 纯研究/负结论批, 1g+1c, 无生产面)。scripts/research/b090_hk_china_{fetch,retest}.py, 缓存真数据 31 标的(16HK sina/10A股/4proxy/SGOV qfq 130,371 行)+FRED FX。★交付=诚实负结论+真根因: **warmup 假设证伪**(NO/WITH-warmup 均 real 25/25 全防守 0 持股, defensive 变化+0; avg_scored 19→23 证 warmup 确施加却不改局→卡点非 warmup); ★真根因=**above_200d_ma calendar-misalignment bug**(200-row 窗 × 3 交易日历 union→MA 恒 NaN→regional_risk_off 每季→真 sleeve 100% 趴 SGOV)。独立验收(代 Codex,隔离,最高怀疑度): 独立重跑逐数字复现报告 §4/§5/§6; ★从零最小 2-ticker 异日历样本复现 bug(严格上涨 ticker union 帧 160/200 non-NaN→误判 below MA)+证单日历无害(proxy 12/25 佐证, backlog 零回归前提); 真-vs-proxy 因 bug 仍未真正测到→报告如实 INCONCLUSIVE 未夸大; qfq caveat 诚实+FX 方向抽点正确(7.8 HKD→0.999 USD); workflow journal 复核 2 对抗验证 un-refuted 属实; 零回归(4 文件 diff+trade/ 空 diff+产品码 0 行, bug 发现未修正确推 backlog)+ruff/10 单测/mypy trade clean+CI 绿(c9c36e8)。signoff docs/test-reports/B090-hk-china-retest-signoff-2026-07-05.md。
- **B089 ✅ done** VIX tail-overlay(纯研究/基建)。静态 X% VIXY overlay on SPY, 2020 covid tail-loss 减真(10% −34%→−15%)+carry 代价诚实焊死(drag 1.04pp/yr, VIXY buy-hold −99.7% roll-cost)。signoff B089-...-2026-07-05。
- **B088 ✅ done** Smoothed/feedback vol-targeting(纯研究/基建)。三控制律逐点对拍+turnover 独立复算(smoothed −54%/feedback −12%)+控波两面诚实。signoff B088-...-2026-07-05。
- **B087 ✅** bootstrap-seed deploy-chain 治本; migration 0041 幂等 seed CURATED_SYMBOL_NAMES insert-if-absent 不覆盖 akshare(VM 只读双证)。**B086 ✅** A股行情统一层。**B085/B084/B083 ✅** cn_attack/ETF趋势/PEAD first-look。**B082–B074 done**(B077 NOT-GO)。
- **接续**：★backlog 新增 **修 above_200d_ma calendar bug**(medium, per-ticker dropna 单日历 no-op 保 live proxy/多日历 real 修好; blast radius=hk_china_momentum wired workbench; Workflow-doable)。余 4 项(A股聪明钱[¥200 Tushare 待用户]/test-automation P3-P5/B055 US careful/residual-engine 触冻结待用户)。★下阶段战略决策待用户(P0-P2 无强 edge; 安全可测机械 win 已尽 B086-B089)。33 learnings 待用户确认。

## 遗留 / soft-watch
- **B090 O1**：3 研究脚本未被 mypy CI 覆盖(Python CI 仅 mypy trade), 直跑仅暴露调用层 artifacts(akshare 无 stub/双模块名解析)非真缺陷。**B090 O2**：可跑窗仅 25 季(2020-06…2026-06)SGOV floor 住重压中国股灾+今日流动名单幸存者偏差→真-vs-proxy 决策级 GO/NO-GO 须待 factor bug 修+更长无偏窗+matched top_n 再跑。
- **B089 O1/O2**：报告「月度再平衡 carry 温和/比 buy-hold 高效」措辞略强; 窗口(2011-26)未显式 caveat 缺 2008 GFC。**B088 O1/O2**：smoothing turnover 减经验稳健措辞略强; realized vol 系统>target 通用局限。**B087/B086/B081**：见旧注(bootstrap 覆盖 vs migration insert-if-absent/fetch_etf timeout/聪明钱方向 backlog)。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38 宽集刷超时含 bulk discovery / §39 paper round-trip 成本 / §40 静默冻结守门 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
