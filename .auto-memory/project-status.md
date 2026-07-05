---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B089 ✅ done（2026-07-05, round1 一轮闭环）** VIX tail-overlay(BL-B013-D2, 纯研究/基建, 1g+1c, 无生产面)。新研究模块 `trade/analysis/vix_overlay.py`(numpy/pandas) 静态 X% VIXY overlay on SPY(月度再平衡, 先验 X=5%/10% 禁扫参)。独立验收(代 Codex,与实现隔离,最高怀疑度): ★2020 covid 前提独立 re-fetch 复算(SPY-34.1%/VIXY+278.3% 与史实一致); ★overlay 数字从零重实现逐点对拍(CAGR 12.13/11.80/11.09, full MaxDD -34.1/-24.9/-20.9, 2020 MDD -34.1/-24.9/-15.15); ★tail-loss 减真(10% 令 2020 急跌 -34%→-15% 近腰斩, 慢熊2022帮助弱-25→-20 诚实区分); ★carry 代价诚实焊死(10% drag 1.04pp/yr + decay-drag 全期硬呈现 VIXY buy-hold -99.7% roll-cost 归零, 非只挑危机窗、未淡化); 无扫参(grep+两档硬编码); 零回归(4文件, 策略/生产零引用, 产品码0行); mypy/ruff clean+4单测pass+mutation-check证再平衡断言有牙; Python/Backend CI绿(29ce6bd)。真策略集成(叠Master/cn_attack) follow-up。signoff docs/test-reports/B089-vix-tail-overlay-signoff-2026-07-05.md。
- **B088 ✅ done（2026-07-05）** Smoothed/feedback vol-targeting(BL-B013-D1, 纯研究/基建, 无生产面)。`trade/analysis/vol_targeting.py` 三控制律 open-loop/smoothing/feedback, 先验禁扫参。独立验收: 公式从零重实现逐点对拍(MAXDIFF open/feedback=0/smoothed=1e-15); turnover 独立复算 open9.67/smoothed4.46(−54%)/feedback8.50(−12%); 控波两面诚实(feedback1.13x不损/smoothing1.30x松弛已披露); PIT无前视; 零回归; CI绿(868f513)。signoff docs/test-reports/B088-vol-targeting-smoothing-signoff-2026-07-05.md。
- **B087 ✅ done** bootstrap-seed deploy-chain 治本(运维)。migration 0041 幂等 seed CURATED_SYMBOL_NAMES(68条,固定stamp)走 alembic 落地生产; insert-if-absent 双证不覆盖 akshare_spot(mutation-check 有牙+VM 只读实测 4 A股 overlap 保中文名); 58=68-10 mainland 闭合; 治本闭环=B080 F005 同源 seed 缺口最后一块。
- **B086 ✅** A股行情统一层(多源 Eastmoney→Sina fallback)。**B085 ✅** cn_attack 残差动量 first-look，评审路线图 P0–P2 收官。**B084/B083 ✅** ETF趋势/PEAD first-look(migration 0039/0038)。**B082–B074 done**(B077 NOT-GO)。
- **接续**：backlog ~5 项(A股聪明钱/hk_china retest/test-automation/B055 等; vol-target/VIX tail-overlay 已 B088/B089 兑现)。B081-B085 严验 follow-up 待并入。33 learnings 待用户确认。下阶段战略决策待用户方向。

## 遗留 / soft-watch
- **B089 O1**：报告「月度再平衡令 carry 温和/比 buy-hold 高效」措辞略强(独立复算月度再平衡10% CAGR11.09%<从不再平衡静态10% 11.35%; carry 温和真因=权重小+SPY牛市非再平衡效率)；核心两面诚实不受影响,后续真策略集成建议修因果措辞。**B089 O2**：报告陈述窗口(2011-2026)但未显式 caveat 缺2008 GFC/结论限定观测窗口(prep doc 已注)。
- **B088 O1/O2**：turnover 减对 smoothing 是经验稳健(非严格定理,200序列0违例)报告措辞略强；realized vol 系统>target(1.1-1.3x)=rv估计滞后通用局限。
- **B087 O1/O2**：bootstrap upsert(覆盖) vs migration insert-if-absent=dev-only 差异(生产走 migration)；VM 3 服务 failed=pre-existing 供运维知悉。
- **B086 O1 / B081**：fetch_etf_daily 未包 timeout(research 非阻断,接生产按 §38 补 daemon join)；cn_attack 快照 daily timer 重算入纯保真, partial_rebalance=True 留独立批。**★聪明钱方向**：backlog `B0XX-ashare-smart-money-following`，结论存 docs/research/。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38 宽集刷超时含 bulk discovery / §39 paper round-trip 成本 / §40 静默冻结守门 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
