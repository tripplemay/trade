---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留问题
type: project
---
## 当前状态
- **B029-fundamentals-snapshot：`building`**；F001 completed（commit b338c39）→ F002 generator 接手；F003 pending（generator）+ F004 pending（codex）。Spec：`docs/specs/B029-fundamentals-snapshot-spec.md`。
- Pre-impl 审计走通：commit 7cfde22（审计请求）→ Planner 裁决 commit c07867f（全 A：#1 12-字段 schema 含 `fiscal_quarter_end` / #2 `fiscal_quarter='2014Q4'` 无短横线 / #3 30 ticker 含 3 synthetic null + ValueError skip 模式 / #4 不引入新 dep）。spec §2/§4.2/§5/§7/§9/§10 + features.json 已同步修订。
- F001 落 7 新文件 + 4 改文件 + 37 测试：`workbench_api/data/{fundamentals_loader,sec_edgar_loader,xbrl_parser}.py` + `fixtures/sec_edgar_responses/{aapl_companyfacts.json,nvda_companyfacts.json,ticker_cik_map.json}`（30 ticker：27 真 CIK + 3 synthetic null）+ `settings.SEC_EDGAR_CONTACT_EMAIL` + `.env.example` + `deploy.sh` pre-flight check exit 67 + `tests/safety/test_settings_env_allowlist` 同步。
- 本机 Gates 全绿：backend pytest **341 passed** 2 skipped（B028 baseline 304 → +37；spec F001 ≥12 floor + ≥316 整体 floor ✓）/ ruff 0 / mypy 0（142 source files）/ frontend vitest 166（baseline 不破）。
- 永久边界 (h)(i)(j) 落地：SEC_EDGAR_CONTACT_EMAIL User-Agent 强制（缺时 RuntimeError + deploy pre-flight）/ SimpleRateLimit(10, period_sec=1.0) 滑动窗口限速 / 8 ratio 公式锁定 strategy doc §6 + B029 spec §4.4。
- 决策：companyfacts API 走 JSON 不引入 lxml（裁决 #4）；CRITICAL_RUNTIME_DEPS 不动；pyproject.toml 不动；B025 fixture 0 字节改；strategy 代码 0 改。
- 下一 sprint F002：`scripts/backfill_fundamentals.py` argparse driver + `scripts/universe_us_quality.py`（30 ticker 与 B025 fixture 一致）+ `scripts/ticker_to_cik.py` one-shot + 本机跑 27 真 ticker × 40 quarter backfill ≥1000 rows + PIT validation 报告 + pytest ≥10（≥326 整体 floor）。F002 backfill driver 须 catch `ValueError(Synthetic ticker...)` + log warn + skip 不阻塞批次（裁决 #3 fail-safe）。
- 后续路径：B029 done → B030（Stream 1.D 全 sleeve 切真 + reports/ fixture vs real 对比）→ 里程碑 A Layer 0→1。

## 已完成签收 + MVP 完工
- B001-B028 全部签收。MVP substantively 完成 (PRD §10/§11/§12) — 完工声明：`docs/prd/mvp-completion-declaration-2026-05-20.md`。
- 最近：B028 Real Data Backfill signoff 2026-05-26（1 fix-round；52 vendor + 153K rows unified；25/25 cross-check PASS；SPY PIT spot-check）；B027 signoff 2026-05-26；B026 signoff 2026-05-26。

## 生产状态
- `https://trade.guangai.ai` live with 双语 workbench + OAuth + `/api/health` + `/api/debug/recent-errors` + B026 synthetic data banner；production HEAD 追至 B028 SHA `15dfb4b`；B029 F001 是 backend-only 新代码（不动 trade/），push 后 paths-trigger 触 Workbench Backend CI + Workbench Deploy（v0.9.27 §12.7.1 已修；自然 deploy 不需 dispatch）。

## 永久硬边界（B029 起继续；v0.9.29 + §12.7.1）
- 系统层：no-broker SDK / no-paper-or-live URL / no-credential / no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository 读写非直 file
- UI 层：no-execution buttons + 中文等价禁词同级 / Order ticket Markdown 双语 disclaimer 永存 / **B026 banner 保留显示**
- 数据 / CI 层：fixture-first 离线 CI / pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ cloud-deploy paths-trigger 含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- B027 起 (f)(g)：Tiingo API key 永不入前端/build/log；月预算 cap `$10` enforced
- **B029 起 (h)(i)(j)：** SEC EDGAR User-Agent 必含 contact email（缺则 ban IP 30d）/ Rate limit 10/sec hard / 8 ratio 公式锁定 strategy doc §6 + B029 spec §4.4
- AI 边界（v0.9.28）：5 子条 spec 列入；本批次不触

## Framework 状态
- 最新版本 **v0.9.29** + §12.7.1 sub-pattern 微沉淀；proposed-learnings.md 空。

## 已知 gap（非阻塞）
- 本机 `python3` 为 3.9.6；所有检查必须用 `.venv/bin/python`。
- GitHub Secret `TIINGO_API_KEY` 已配（B027）；`SEC_EDGAR_CONTACT_EMAIL` **B029 F001 已加入 ALLOWED_ENV_VARS + deploy.sh pre-flight，需用户配置 GitHub Secret**（generic research-only 邮箱）后才能 production-side fetch；F002 本机 backfill 仅需本地 `.env` 设置即可。

<!-- 覆盖写；保持 ≤30 行；只放 WHAT，不重复 progress.json 结构化字段。 -->
