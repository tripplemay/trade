---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B030-real-data-cutover：`building`**；F001 done (generator)；F002+F003 pending（generator）+ F004 pending（codex）。Spec：`docs/specs/B030-real-data-cutover-spec.md`。
- **F001 done 2026-05-27**：per-sector alias chains 落地 (Financials/Utilities/Real Estate × 6 concept) + universe sector 映射；重跑 backfill **685 → 853 rows (+24.5%)**；4/6 sector ticker 恢复 (LIN 31/NEE 53/PLD 58/JPM 13)；BAC/V structural gap (无标准 capex / 无 quarterly shares_outstanding) 文档化转给 Planner。Gates: backend pytest 381 / trade pytest 755 / ruff clean。PIT report: `docs/test-reports/B030-pit-validation-2026-05-27.md`。**Spec §(4) ≥1000 row floor 未达 (853；-15%)** — alias-chain 机制穷尽，需后续算法变更 (capex=0 fallback / annual-shares interp) 或 universe 调整决策。用户已批 Land 选项 1（land aliases + 转 Planner）。
- 🎯 **Phase 1 终点 / 里程碑 A Layer 0→1**：本批次完成后 workbench 进入「research with real historical data」阶段；回测指标第一次有真实意义；B026 banner 下线；fixture vs real 5 份对比报告生成。
- 决策矩阵（2026-05-27 用户已批）：6 sector-structural ticker 处置 = F001 per-sector aliases (现 4/6 实施成功；BAC/V residual gap 转 Planner) / B026 banner 关闭 = B030 done by acceptance / 4 features 拆分 / 对比报告 = Master 4 sleeve + B025 us_quality 各独立 5 份 + 1 overview。
- 新增永久产品边界 (k)：**Layer 状态不可逆向滑落** — B030 done 后若真数据严重 unreliable 必须新批次 spec 决议，不 silent rollback。
- 本批次属 implementation-path-2026-05.md §4 **Phase 1 第五个 batch（Stream 1.D 终点）**。
- 后续路径：F002 strategy 切真（trade/strategies/* + trade/portfolio/master.py）→ F003 对比报告 + banner 关 → F004 codex L2 → 🎯 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B029 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B029 Fundamentals Snapshot signoff 2026-05-26（0 fix-round；27 CIK + 685 rows + PIT 25/25 PASS）；B028 signoff 2026-05-26；B027 signoff 2026-05-26；B026 signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live；B029 production `/api/health.version` 为 `c3ec920f96587bf9945c4e384fc151fc774f9696`；B030 F004 后 production 将 cutover 到真数据 + B026 banner 下线。

## 永久硬边界（B030 起继续；v0.9.30 + §12.9）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / **B026 banner 在 B030 done 后下线**（B030 起组件代码保留可重启路径）
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g)：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced
- B029 起 (h)(i)(j)：SEC EDGAR User-Agent 必含 contact email / Rate limit 10/sec hard / 8 ratio 公式锁定 strategy doc §6
- B030 起 (k) + v0.9.30 §12.9：production secret 必须 3+1 处接线 (.env.example + config.py + deploy.sh + bootstrap-env.yml) + **Layer 状态不可逆向滑落**（B030 done 后 Layer 1 稳定，回滚需新批次 spec）

## Framework 状态
- 最新版本 **v0.9.30**（2026-05-26 沉淀完成）：B027 + B029 二例合并沉淀 "production secret 三处接线铁律"（§12.9）。"deploy hygiene" 系列已覆盖 5 层 production-only edge 防御（deploy script / deploy workflow / runtime process / packaging / secret 注入）。proposed-learnings.md 空。B026 React event edge 仍单一案例 hold。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY`（B027）+ `SEC_EDGAR_CONTACT_EMAIL`（B029）已配；B030 本批次不引入新 secret 无需用户介入。
- **B030 F001 残留 (gap → Planner)**：853 < 1000 row floor (-15%)；BAC/V 仍 0 row。BAC 无标准 capex（银行不发 PaymentsToAcquirePropertyPlantAndEquipment 只发证券购买），V 无 quarterly shares_outstanding（只发年度 cover-page）。Forward path: (a) Financials capex=0 fallback + (b) V annual-shares interpolation → ~920 rows；或 (c) B025 universe 移除 BAC/V。详 `docs/test-reports/B030-pit-validation-2026-05-27.md` §4+§9。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
