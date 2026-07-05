---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B086 ✅ done（2026-07-05, round1 一轮闭环）** A股行情数据源统一层(基建, 多源 fallback, 1g+1c)。`scripts/research/ashare_market_source.py` `fetch_etf_daily()` Eastmoney(fund_etf_hist_em qfq)→Sina(fund_etf_hist_sina raw) fallback, 返回带 source/adjust 标注, 全失败→DataSourceError 不静默空。独立验收(代 Codex,与实现隔离): 6 mock 单测覆盖 fallback 各分支 + **mutation-check 双变异证有牙**(破fallback→2测FAIL/破sina_symbol→1测FAIL) + **真网端到端实测**(Eastmoney 真SSLError→Sina 接管23行/adjust=raw/日期窗正确/warning+info双log不静默); 口径标注按构造必异+显式(结构核实); 零回归 root pytest 1160 passed 0 failed + 无产品码 import 新模块 + b082-b085 脚本字节不变 + cn_attack·flagship·生产data_root 0行; CI全绿 + 生产release≡HEAD产品码(520897f, research模块不入部署)。软观察3非阻断(O1 timeout未包=作用域生产刷job非本research模块,与b084/b085先例一致/O2 mypy CI作用域=trade/O3 并发planner docs提交)。**两源live数值对照因 Eastmoney 持续不可达(8次重试全FAIL,dev+VM双向)受限,已诚实披露**——反再验证模块前提。signoff docs/test-reports/B086-ashare-quote-source-unify-signoff-2026-07-05.md。
- **B085 ✅ done（2026-07-05）** cn_attack 残差动量升级 first-look = 全2 PASS。**★评审路线图 P0–P2 全部收官**。残差IC异路径重算51月度点逐位吻合(0.0108/t0.45弱; delta+0.0118/t1.98 borderline); β PIT无前视双证; 禁扫参; rescope 引擎A/B→前置筛=合规缩窄(尊冻结flagship边界); INCONCLUSIVE 合法。完整引擎A/B降级backlog(待用户对触冻结flagship决策)。
- **B084 ✅ done** A股 ETF 趋势 first-look=全3 PASS(INCONCLUSIVE/LEAN-GO, 独立异路径复算逐位吻合, migration 0039)。**B083 ✅ done** PEAD first-look=全3 PASS(前视全过, IC三路径吻合, INCONCLUSIVE, migration 0038)。**B082 ✅ done** 红利低波防守腿(生产5CSV落地实证, alembic 0037)。**B081 ✅ done** cn_attack 回测引擎修真(alembic 0036)。B080/B079/B078/B076/B075/B074 done。B077 NOT-GO。
- **接续**：backlog ~9 项(A股聪明钱/hk_china retest/test-automation/B055/vol-target/VIX/bootstrap-seed 等; A股数据源已 B086 兑现)。B081-B085 严验 follow-up(refresh fx+benchmark/PEAD全A+快报SUE/ETF CPCV+复权+turnover/完整引擎A/B)待 planner 并入。learnings 队列待用户确认。下阶段战略决策待用户方向。

## 遗留 / soft-watch
- **B086 O1（促码提示）**：`fetch_etf_daily` 网络调用未包 timeout(research 层非阻断)；若未来接生产刷 job/systemd timer 须按 §38 补 daemon-线程 join(timeout)，建议 docstring 加提示。
- **B081 快照自愈**：cn_attack advisory 快照 daily timer 重算入纯保真口径；partial_rebalance=True 变体留独立 verdict 批。
- **★聪明钱方向**：backlog `B0XX-ashare-smart-money-following`，结论存 docs/research/。
- **B070 follow-on**：2因子去偏 baostock；港股 P3（backlog B055）。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38 宽集刷超时含 bulk discovery / §39 paper round-trip 成本 / §40 静默冻结守门 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
