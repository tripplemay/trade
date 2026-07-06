---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B096 ✅ done（2026-07-06, 混合批 1g+1c, Workflow-build）** test-automation roadmap **P4-F2 LLM-judge 语义层**(桶 C 概率部分, advisory, additive)。用户 2026-07-05 授权 `AIGC_GATEWAY_API_KEY`(验 HTTP200)解锁。新增 `llm/semantic_judge.py`(278 行, 扩 judge.py B032 范式)+`test_semantic_judge_vcr.py`(284 行, 9 例评测集)+2 VCR cassette+`routing.py`+1 条(semantic_judge→claude-haiku-4.5): judge 单调用返双 verdict(模糊英文/混合残留 + grounding 数值是否 trace 输入)。★裁定 **全 PASS 2/2**。独立验收(代 Codex, 隔离, 独立解码非信任测试自证): ★★key 零泄露(BLOCKING gate 通过)=cassette 无 authorization header(filter_headers 剥除)+全 git 历史无 `sk-`/`Bearer <value>`+key 走 env 无硬编码+.env.example 空+.gitignore 覆盖; ★评测集准确=我从磁盘 gzip.decompress 9 响应体逐条比对预期标签 9/9(evidence 引真机措辞证非伪造, 跨 4 象限含硬 mismatch P/E 12.5vs22); ★additive 零回归=git diff 证红队门/dataset/judge.py/conftest 逐字节未动+grep 证未接 runtime(唯一 import=其单测=advisory-only)+safety 261 passed+CI AI Safety Eval 绿; ★advisory=advisory=True 永久标记仅契约违反 raise; ★VCR=record_mode=none 空 key 4 passed 离线确定性。门禁全绿(ruff/mypy 320/pytest)+HEAD≡prod。signoff docs/test-reports/B096-llm-judge-semantic-signoff-2026-07-06.md。3 软观察非阻断(O1 frontend E2E flake 与本批无关非回归/O2 尚无 runtime-gate 消费者/O3 cassette 顺序依赖)。
- **★含义**: 推进 test-automation 1 feature(P4-F2 LLM 语义能力层+评测集证据网+drift 检测已进 backend CI, 未接 runtime gate, 符合 roadmap advisory 非硬 block)。item **不清空**——P3(生产 synthetic/canary, 已授权待 B097)+P5(独立评审固化, 铁律 4)仍待办。★key 曾对话明文暴露 → 建议用户用完后主动轮换(与本批 commit 安全性独立, 已核 key 未进任何 committed 文件)。
- **B095 ✅ done** test-automation **P4-F1 确定性语义 lint**(桶 C 确定性, 英文残留+no-AI 禁语, advisory-only, 全 PASS 2/2)。**B094 ✅ done** 游资席位 follow first-look **NO-GO(跟游资反而亏)**; ★smart-money 免费两支已测尽(机构 B077 INCONCLUSIVE + 游资 B094 NO-GO), 首要 institutional 仍需付费 Tushare ¥200(故意未买, 留给用户)。**B093 ✅** hk_china real-stock **NO-GO(保 proxy)**。**B092/B091/B090–B074 ✅**(B077 NOT-GO)。
- **接续**：★战略决策待用户(所有免费策略研究无强 edge)。backlog 剩: A股聪明钱[机构 ¥200 待用户] + test-automation P3(生产 synthetic/canary, 已授权→B097)/P5(独立评审, 铁律 4)(基建, user-gated) + residual-engine(触冻结待用户)。34+ learnings 待用户确认。

## 遗留 / soft-watch
- **B096 O1/O2/O3**（非阻断）：frontend CI Playwright E2E smoke flake(backend-only 变更无关, 非 deploy gate, Deploy 已绿) / 语义 judge 尚无 runtime-gate 消费者(advisory-only, 但 drift 检测已进 backend CI) / cassette 按录制顺序重放(EVAL_SET 顺序 load-bearing, 重排需重录)。
- **B095 O1/O2/O3**（非阻断）：确定性 pre-filter 固有'宁漏勿误'漏报口(bare 下单剔除+NEGATION_WINDOW=5, docstring 明述, P4-F2 后手) / 小写 allowlist 演进需守证据门 / lint 尚无 runtime/CI 消费者(advisory-only 能力层)。
- **B094 O1–O4**（非阻断, 归档）：events.csv 重复键未去重(immaterial, dedup 后仍显著 NO-GO) / §1 caveat 措辞欠精确 / priced 1,279 非满 1,500 / 仅 N5 edge 显著。
- **B093 O1/O2/O3**（非阻断）：报告未溯源 2024-03 shared-date 机制 / proxy 本身弱基准 / 25 季 SGOV-floored 单 regime+幸存者=结构性天花板窗口不可扩。
- **B089/B088**：carry/turnover 措辞略强+窗口 caveat。**B087/B086/B081**：见旧注。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实, real-stock live 不激活）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
