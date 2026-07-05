---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B089 🔨 building（2026-07-05 开批）** VIX tail-overlay(BL-B013-D2, 纯研究/基建, 1g+1c)。静态 VIXY overlay on SPY 减尾部损失(前提实测 2020 SPY-34%/VIXY+278%)。新研究模块 trade/analysis/vix_overlay.py; overlay X 先验禁扫参; ★tail-loss减+negative carry代价两面诚实量化(对冲不免费)。Planner 已接手 F001。
- **B088 ✅ done（2026-07-05, round1 一轮闭环）** Smoothed/feedback vol-targeting(BL-B013-D1, 纯研究/基建, 1g+1c, 无生产面)。新研究模块 `trade/analysis/vol_targeting.py`(numpy/pandas) 三控制律 open-loop/smoothing(EWMA rv)/feedback(partial-adjust k), 先验禁扫参(target0.08/hl21/k0.5)。独立验收(代 Codex,与实现隔离): ★三律公式从零重实现逐点对拍(MAXDIFF open/feedback=0, smoothed=1e-15); ★turnover 独立复算 open9.67/smoothed4.46(−54%)/feedback8.50(−12%)+200随机序列0违例; ★控波独立复算两面诚实(feedback1.13x几乎不损/smoothing1.30x松弛已披露→turnover减未牺牲控波); PIT扰动审计无前视(改rv[T]不动e[0..T-1]); 无扫参(grep+常量硬编码); 零回归(risk_parity字节不变+产品策略码0行); mypy/ruff clean+4单测pass+mutation-check证turnover减断言有牙; Python/Backend CI绿(868f513)。真策略集成 follow-up。signoff docs/test-reports/B088-vol-targeting-smoothing-signoff-2026-07-05.md。
- **B087 ✅ done** bootstrap-seed deploy-chain 治本(运维)。migration 0041 幂等 seed CURATED_SYMBOL_NAMES(68条,固定stamp)走 alembic 落地生产; insert-if-absent 双证不覆盖 akshare_spot(mutation-check 有牙+VM 只读实测 4 A股 overlap 保中文名); 58=68-10 mainland 闭合; 治本闭环=B080 F005 同源 seed 缺口最后一块。
- **B086 ✅** A股行情统一层(多源 Eastmoney→Sina fallback)。**B085 ✅** cn_attack 残差动量 first-look，评审路线图 P0–P2 收官。**B084/B083 ✅** ETF趋势/PEAD first-look(migration 0039/0038)。**B082–B074 done**(B077 NOT-GO)。
- **接续**：backlog ~5 项(A股聪明钱/hk_china retest/test-automation/B055 等; vol-target 已 B088 兑现, VIX tail-overlay 已 B089 开批)。B081-B085 严验 follow-up 待并入。33 learnings 待用户确认。下阶段战略决策待用户方向。

## 遗留 / soft-watch
- **B088 O1**：turnover 减对 feedback 严格机械(低通滤波 TV 不增)、对 smoothing 经验稳健(非线性1/x+clip 后非严格定理但 200序列0违例)；报告「任意序列可证」措辞对 smoothing 略强，后续真策略集成建议标「经验稳健」。**B088 O2**：realized vol 系统>target(1.1-1.3x)=21日rv估计滞后 regime 切换通用局限(非本律引入)。
- **B087 O1/O2**：bootstrap upsert(覆盖) vs migration insert-if-absent=dev-only 差异(生产走 migration)；VM 3 服务 failed=pre-existing 供运维知悉。
- **B086 O1**：fetch_etf_daily 网络调用未包 timeout(research 层非阻断)；接生产刷 job 须按 §38 补 daemon join(timeout)。
- **B081 快照自愈**：cn_attack advisory 快照 daily timer 重算入纯保真口径；partial_rebalance=True 变体留独立 verdict 批。
- **★聪明钱方向**：backlog `B0XX-ashare-smart-money-following`，结论存 docs/research/。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38 宽集刷超时含 bulk discovery / §39 paper round-trip 成本 / §40 静默冻结守门 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
