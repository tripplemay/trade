---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B032-ai-safety-eval：`done`**（2026-05-28 Codex 签收完成）；F001 + F002 done generator，F003 done codex evaluator。Spec：`docs/specs/B032-ai-safety-eval-spec.md`。最终结论：L1 + L2 全绿，GitHub Actions `AI Safety Eval` workflow run `26522914433` 成功，production HEAD 与 `main` 等价，B026 banner 仍 absent。签收报告：`docs/test-reports/B032-ai-safety-eval-signoff-2026-05-28.md`；证据图：`docs/screenshots/B032-safety-eval/`。
- Phase 2 / Stream 3.B：为 B036 AI advisor MVP 上线建立 safety eval CI gate（红队 15 样本 + Sonnet 4.6 LLM judge + 100% 拦截 + 仅 CI 预走）。**不做** runtime safety check / prompt template / advisor endpoint / 自动生成红队样本。
- 决策矩阵（2026-05-27 用户已批，与 ai-safety-evals-2026-05.md §1 预设一致）：严格度=中等 3 fail 型 × ≥5 = 15 样本 100% 拦截 / LLM judge=Sonnet 4.6 单 judge（不跨 vendor）/ Runtime=仅 CI 预走 / Dataset=15 样本起步 PR 手动扩。
- 新增永久产品边界 (n) + (o)：(n) Safety eval CI gate 100% 拦截 + (o) Safety eval dataset 修改必走 PR review（commit 标 `safety-eval-dataset`）。
- 本批次属 implementation-path-2026-05.md §4 **Phase 2 第七个 batch（Stream 3.B）**。复用 B031 LLMGateway + AIGC_GATEWAY_API_KEY（不引入新 secret）。
- 后续路径：B033（2.A News）→ B034（2.B embedding）→ B035（2.C market context）→ B036（3.C AI advisor MVP）= **🎯 里程碑 B Phase 2 终点**。

## 已完成签收 + MVP 完工
- B001-B032 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B032 AI Safety Eval signoff 2026-05-28；B031 LLM Gateway signoff 2026-05-27（1 fix-round；OpenAI-compatible API 真实接入 aigc.guangai.ai）；🎯 B030 Real Data Cutover signoff 2026-05-27（Phase 1 终点 / 里程碑 A Layer 0→1 达成）。

## 生产状态
- `https://trade.guangai.ai` live；production `/api/health.version` = `aebed14c8262a90db071e63584023b86a768955b`（与签收前 `main` HEAD 等价）；authenticated `/api/debug/recent-errors` = `{"count":0,"records":[]}`；AIGC_GATEWAY_API_KEY + TIINGO_API_KEY + SEC_EDGAR_CONTACT_EMAIL 已 VM env；llm_budget_log + tiingo_budget_log 表已存在；B026 banner decommissioned + `/strategies` `/reports` `/recommendations` `/risk` 均 `BANNER_ABSENT`。

## 永久硬边界（B032 起继续；v0.9.31 + §12.9 + §16/§22）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned（v0.9.31 §16 守门）
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g) / B029 起 (h)(i)(j) / B030 起 (k) + v0.9.30 §12.9 / B031 起 (l)(m)：继续
- **B032 起 (n)(o)：** (n) Safety eval CI gate 100% 拦截 / (o) Safety eval dataset 修改必走 PR review（commit 标 `safety-eval-dataset`）
- AI 边界（v0.9.28 5 子条）：本批次是 safety eval 守门 infra；红队 dataset 设计依据 5 子条

## Framework 状态
- 最新版本 **v0.9.31**（2026-05-27 沉淀完成）：B030 Feature decommission 四处清理铁律。**B031 done 阶段 Codex first-class 列入 1 候选**（第三方 API spec live-validate）但用户决议**暂不沉淀**（单一案例 hold；记 proposed-learnings.md 注释；等 B033/B034/B035 再撞同样 spec invented endpoint 问题合并为 v0.9.32）。B026 React event edge 仍单一案例 hold。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY`（B027）+ `SEC_EDGAR_CONTACT_EMAIL`（B029）+ `AIGC_GATEWAY_API_KEY`（B031）已配；B032 已完成签收，后续进入 B033。
- B029 S2 backend pytest SOCKS proxy 敏感属 evaluator 环境特定。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
