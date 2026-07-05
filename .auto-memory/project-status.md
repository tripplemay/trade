---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B087 ✅ done（2026-07-05, round1 一轮闭环）** bootstrap-seed deploy-chain 治本(运维, 1g+1c)。migration `0041_curated_symbol_names_seed` 幂等 seed CURATED_SYMBOL_NAMES(68条,source=curated,固定stamp)走 alembic 部署链落地生产。独立验收(代 Codex,与实现隔离): ★insert-if-absent 双证不覆盖 akshare_spot(静态 mutation-check 注入 INSERT OR REPLACE→测试 FAIL 有牙 + 生产 4 A股 overlap 保 akshare_spot 中文名实测); VM 只读实测 alembic head=0041 / breakdown akshare_spot|5203(基线不减)+curated|58(治本 production=0) / 58=68-10 mainland 逐点闭合 / SPY·AGG·AAPL·MSFT 值正确; upgrade→downgrade→upgrade 幂等+可逆(downgrade 只删 curated 不误删 spot); bootstrap 同源 lockstep(names.py 单一真相源); 产品策略码 0 行; 176 回归+2 单测 pass; CI 全绿(e1b0a03,Python CI 因 workbench/** paths-ignore 合法跳过)+HEAD≡prod。★治本闭环=B080 F005 同源 seed 缺口最后一块。signoff docs/test-reports/B087-bootstrap-seed-deploy-chain-signoff-2026-07-05.md。
- **B086 ✅ done** A股行情数据源统一层(基建,多源 fallback)。fetch_etf_daily Eastmoney(qfq)→Sina(raw) fallback 带 source/adjust 标注全失败 raise。验收 6 mock+mutation双变异有牙+真网端到端(Eastmoney SSLError→Sina 23行); 两源 live 数值对照因 Eastmoney 持续不可达受限(已披露)。
- **B085 ✅** cn_attack 残差动量 first-look 全2 PASS，★评审路线图 P0–P2 全收官。**B084/B083 ✅** ETF趋势/PEAD first-look 全PASS(migration 0039/0038)。**B082/B081/B080/B079/B078/B076/B075/B074 done**，B077 NOT-GO。
- **接续**：backlog ~7 项(A股聪明钱/hk_china retest/test-automation/B055/vol-target/VIX 等; bootstrap-seed 已 B087 兑现)。B081-B085 严验 follow-up 待 planner 并入。33 learnings 待用户确认。下阶段战略决策待用户方向。

## 遗留 / soft-watch
- **B087 O1**：bootstrap `_import_symbol_names` upsert(覆盖) vs migration insert-if-absent(不覆盖)——dev-only 差异(生产走 migration 不跑 bootstrap)，名集同源已满 lockstep；语义完全对齐可下批纯洁癖(非缺陷)。
- **B087 O2**：VM `workbench-data-refresh`/`workbench-prices`/`workbench-canonical-backtest` 3 服务 failed=pre-existing 与 B087 无关(akshare 5203 历史基线)，供运维知悉。
- **B086 O1（促码提示）**：fetch_etf_daily 网络调用未包 timeout(research 层非阻断)；接生产刷 job 须按 §38 补 daemon 线程 join(timeout)。
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
