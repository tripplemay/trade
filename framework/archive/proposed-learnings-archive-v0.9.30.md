# proposed-learnings v0.9.30 归档（2026-05-26）

## 背景

B029 done 阶段，Generator handoff 主动建议沉淀「spec acceptance 'deploy.sh 加 pre-flight check' 时若引入新 production secret 必须同 commit 扩 `bootstrap-env.yml`」配对铁律。Codex F004 signoff 标"本批次无 framework learnings"。

Planner 在 done 阶段做独立评估：**这是真正的二例**，满足之前用户在 B026 done / B027 done 阶段确认的"等二例再合并沉淀"原则。

## 二例 anti-pattern 严格相同性证明

| 维度 | B027 | B029 |
|---|---|---|
| 新 secret | `TIINGO_API_KEY` | `SEC_EDGAR_CONTACT_EMAIL` |
| Spec acceptance 已含的接线 | `.env.example` 加 secret 行 + `deploy.sh` 加 pre-flight check | 完全相同：`.env.example` 加 + `deploy.sh` pre-flight |
| Spec acceptance 漏的接线 | `bootstrap-env.yml` 未提及 | 完全相同：`bootstrap-env.yml` 未提及 |
| Generator 实施现象 | 推 deploy 后 production VM 拿不到 secret；`/etc/workbench/workbench.env` grep 不命中 | 完全相同 |
| Fix-round commit | `dcf1463 fix(B027-F002): bootstrap-env.yml — include TIINGO_API_KEY in env file` + `c46bda3 chore(B027): note env-file deploy gap + operator action in handoff` | `ef421e9 fix(B029-F001): wire SEC_EDGAR_CONTACT_EMAIL into bootstrap-env.yml` + `1e21e9f chore(B029): F001 production-side aligned` |
| 修复方法 | 同：把 secret 加到 bootstrap-env.yml workflow 同位置 | 同 |
| 用户授权 ops（admin sudo install on VM）| 同：用户授权 deploy 后手动 sudo install 把新 secret line 加到 `/etc/workbench/workbench.env` | 同 |

**结论：** 两次完全相同的 anti-pattern + 完全相同的 fix 路径 + 完全相同的 user ops 介入。**真二例**，不是相似机制不同问题。

## 沉淀理由

1. **复用窗口大**：
   - B031 LLM gateway batch 会引入 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `COHERE_API_KEY` 至少 3 个新 secret
   - B033 News ingest batch 可能引入付费 RSS / NewsAPI key
   - Phase 4 long-tail batches（任何 SaaS / paid 服务接入）
   - 不沉淀 = Generator 每次重复踩坑 + 用户每次重复 ops 介入
2. **防御方案成熟**：4 处同 commit checklist 简单可执行；Generator 实施时第一件事 grep `bootstrap-env.yml` 既有 secret 加新 secret 到同位置
3. **与 v0.9.X "deploy hygiene" 系列同脉络**：§12.5 deploy.sh source env / §12.6 schema-assert / §12.7 chore-deploy / §12.7.1 paths-trigger / §12.8 runtime deps / §12.9 secret 三处接线 — 都是 "production env vs local env" 差异防御

## 沉淀位置（已落地）

| 内容 | 落地文件 |
|---|---|
| 4 处接线 ASCII art + 4 条规约 + 反面案例对比表 + 预防价值 | `framework/harness/generator.md` §12.9 "production secret 三处接线铁律（v0.9.30 — B027 + B029 二例合并沉淀）" |
| v0.9.X "deploy hygiene" 教训汇总表更新（加 §12.9 行）| 同上末尾 |
| 4 处接线核心规约 | (1) `.env.example` 加占位符 (2) `config.py` os.environ 读 (3) `deploy.sh` pre-flight check (4) **`bootstrap-env.yml` workflow inject** ← 容易漏的 |

## v0.9.X "deploy hygiene" 系列演进

| 版本 | 教训 | 哪一层 |
|---|---|---|
| v0.9.25 §12.5 | deploy.sh 没 source env file → alembic 跑 scratch DB | deploy script |
| v0.9.25 §12.6 | alembic 跑后 schema 不一致 | deploy script |
| v0.9.27 §12.7 | chore-only commit 不触 CI / deploy → drift | deploy workflow |
| v0.9.27 §12.7.1 | 产品代码 paths-trigger gap → drift | deploy workflow |
| v0.9.27 §20 (evaluator.md) | production VM stale dev process | runtime process |
| v0.9.29 §12.8 | wheel install 缺 dev extras → ImportError | packaging |
| **v0.9.30 §12.9** | **新 secret 漏 bootstrap-env.yml → production env 缺 secret** | **secret 注入** |

**系列演进趋势：** 每个 v0.9.X 补一层 production-only edge 防御。覆盖面渐趋完整：
- ✅ deploy script (12.5/12.6)
- ✅ deploy workflow (12.7/12.7.1)
- ✅ runtime process (§20)
- ✅ packaging (12.8)
- ✅ secret 注入 (12.9)
- ⏳ frontend bundle 层（已部分覆盖：§13 same-origin + build artifact grep）
- ⏳ nginx / reverse proxy 层（已部分覆盖：§13.5 dev rewrite mirror nginx）
- ⏳ systemd / cron 层（B028 EOD cron 上线时可能再撞）
- ⏳ DB migration 层（已部分覆盖：§12.6 schema-assert）

## 未沉淀（继续 hold）

| 候选 | 决策 | 理由 |
|---|---|---|
| **B026 React event edge**（vanilla DOM fallback 双路径） | 继续 hold | 仍单一案例。B027 deploy install / B028 paths-trigger / B029 secret inject 都机制不同，不与 React event edge 合并。等下一例 React UI 互动 local-pass-prod-fail 出现再合并 |
| B029 S1 unified 685 行 < 1000 floor | 不沉淀为 framework | sector-structural 是策略层细节（金融 / 公用事业 / REIT sector 的 SEC XBRL concept 与一般行业不同），B030 per-sector ratio model 解决 |
| B029 S2 backend pytest 对 SOCKS proxy 敏感 | 不沉淀 | 单一案例 + evaluator 环境特定；建议在 evaluator role-context 默认 unset HTTP_PROXY 即可 |

## Planner done 阶段补写时机说明

与 v0.9.26 / v0.9.27 / v0.9.28 / v0.9.29 沉淀模式一致：
- Codex F004 signoff §Framework Learnings 段从产品 spec PASS / FAIL 视角评估
- Planner 在 done 阶段做**跨批次 framework 演进**视角评估
- 两者视角不同；Codex 标"无 learnings" ≠ Planner 评估"无沉淀价值"
- 本次特殊：**Generator handoff 主动提出建议沉淀**（不只是 Codex 视角），Planner 验证二例严格相同后采纳

来源：B027 F002 fix-round 1 + B029 F001 fix-round 1 + B029 done 阶段 Generator handoff 主动建议；commits `dcf1463` / `c46bda3` (B027) + `ef421e9` / `1e21e9f` (B029)；signoff `docs/test-reports/B029-fundamentals-snapshot-signoff-2026-05-26.md`；本归档由 Planner 在 done 阶段 2026-05-26 与用户确认后落地。
