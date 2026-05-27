---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B031-llm-gateway：`verifying`**（2026-05-27 generator 交付）；F001 + F002 done generator + F003 pending codex evaluator。Spec：`docs/specs/B031-llm-gateway-spec.md`。下一步 Codex 起 verifying：L1 CI gates + L2 真 VM SSH 验 alembic 0004 + sqlite llm_budget_log 表 + smoke health_check + B026 banner 仍 0 hits + signoff docs/test-reports/B031-llm-gateway-signoff-*.md + ≥2 PNG screenshots。
- 🎯 **Phase 2 起点 / Stream 3.A**：本批次 = Layer 1.5 AI-augmented advisory 基础设施。Phase 1 Layer 0→1 已完成（B030 done 2026-05-27）。
- 目标：把 aigc-gateway（已有 MCP server 30+ tools）接入 backend，提供统一 chat completion + multi-tier routing + cost guard + log。**不做** prompt template / safety eval / advisor endpoint / 前端 UI 改动（留 B032/B036+）。
- 决策矩阵（2026-05-27 用户已批）：aigc-gateway HTTP REST 接入（不走 MCP）/ Multi-tier routing per llm-provider-evaluation §5.2（Sonnet 主 / Haiku 高频 / Flash news / Opus quarterly）/ 月 cost cap ¥1500（¥1200 alert + Haiku fallback / ¥1500 halt）/ 范围 = 纯 basic infra。
- 新增永久产品边界 (l) + (m)：(l) LLM provider routing 不可硬编码 model name in 业务代码 + (m) LLM 月预算 cap ¥1500 enforced。
- 本批次属 implementation-path-2026-05.md §4 **Phase 2 第六个 batch（Stream 3.A 起点）**。受益 v0.9.30 §12.9 secret 三处接线（AIGC_GATEWAY_API_KEY 四处接线）+ v0.9.31 §16/§22/§Decommission Checklist（本批次非 decommission；signoff 标"无"）。
- 后续路径：B032（Stream 3.B AI safety eval）→ B033（2.A News）→ B034（2.B embedding）→ B035（2.C market context）→ B036（3.C AI advisor MVP）= **🎯 里程碑 B Phase 2 终点**。

## 已完成签收 + MVP 完工
- B001-B030 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：🎯 **B030 Real Data Cutover signoff 2026-05-27（Phase 1 终点 / 里程碑 A Layer 0→1 达成）**；B029 signoff 2026-05-26；B028 signoff 2026-05-26；B027 signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live；production `/api/health.version` = `61bc4c31a7fa3229a84896d7d3a93fab1b613405`（B031 F001，2026-05-27 deploy 成功；AIGC_GATEWAY_API_KEY 已配 GitHub Secret + bootstrap-env workflow + tripplezhou install + systemd restart 完成；deploy.sh pre-flight 通过）；B026 synthetic banner 仍 0 hits decommissioned；strategy 已切真数据（real prices + real fundamentals）；fixture vs real 5+1 对比报告本机已生成。

## 永久硬边界（B031 起继续；v0.9.31 + §12.9 + §16/§22）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned（v0.9.31 §16 四处清理已完成）
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g)：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced
- B029 起 (h)(i)(j)：SEC EDGAR User-Agent 必含 contact email / Rate limit 10/sec hard / 8 ratio 公式锁定 strategy doc §6
- B030 起 (k) + v0.9.30 §12.9：production secret 必须 3+1 处接线 + **Layer 状态不可逆向滑落**（B030 done 后 Layer 1 稳定）
- **B031 起 (l)(m)：** (l) LLM provider routing 不可硬编码 model name in 业务代码 / (m) LLM 月预算 cap ¥1500 enforced（¥1200 alert + Haiku/Flash fallback / ¥1500 halt）

## Framework 状态
- 最新版本 **v0.9.31**（2026-05-27 沉淀完成）：B030 沉淀 Feature decommission 四处清理铁律（generator.md §16 + evaluator.md §22 + templates/signoff-report.md §Decommission Checklist 三处一体）。"deploy hygiene + decommission" 系列已覆盖 6 层 production-only edge 防御。B026 React event edge 仍单一案例 hold。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY`（B027）+ `SEC_EDGAR_CONTACT_EMAIL`（B029）已配。
- GitHub Secret `AIGC_GATEWAY_API_KEY` 已配（2026-05-27 用户）+ bootstrap-env workflow 已 dispatch + tripplezhou 已 install env + services 已 restart + Workbench Deploy 已成功 (run 26516368849)；F002+F003 不再阻塞。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
