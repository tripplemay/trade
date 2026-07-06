---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B097 ✅ done（2026-07-06, 混合批 2g+1c, Workflow-build）** test-automation roadmap **P3 部署后 synthetic 监控**(生产, 用户 2026-07-05 授权解锁)。新增 `workbench/deploy/scripts/synthetic_check.sh`(194 行, 只读 4 检查: health 200+db / recent-errors=0[auth-gated opt-in] / HEAD≡prod SHA / 关键端点 401 形状)+`workbench-prod-canary.yml`(45 行, 每 6h 只读告警非 rollback)+deploy.yml additive(synthetic 作额外 rollback 门, EXPECTED_SHA armed, rollback if 由 healthcheck 扩为 OR synthetic)。★裁定 **全 PASS 3/3**(F001+F002 实现+F003 独立验收)。独立验收(代 Codex, 隔离, 不信任声明→活 prod 只读实测+真机 CI 日志+逐条 trace): ★★命门1只读(BLOCKING清)=4 curl 全 GET; ★★命门2 rollback 安全(BLOCKING清)=边界 4 场景 trace 正确+additive OR 不削弱+blast radius 有界(仅 deploy failure()+deploy.outcome 守门非任意触发)+假红稳健(活 prod 本地 EXIT0+真机 canary run 28776985789 绿+armed check[3]双向 teeth+只断可靠值 SKIP 不 FAIL); ★★命门3无凭证泄露(BLOCKING清)=新文件无硬编码+cookie 仅 env 读不落盘+全史扫空; ★命门4 additive 零回归=healthcheck 未改+产品树 prod≡HEAD 逐字节相同; ★命门5=canary 注册 active+真机跑绿 12s+B097 路径不触产品 CI 故 prod 合法停 4ff104d(预期非异常, gate=Backend+Safety 二绿, Frontend flake 非回归)。signoff docs/test-reports/B097-prod-synthetic-canary-signoff-2026-07-06.md。3 soft-watch 非阻断(S1 actionlint deploy.yml exit1=SC2087 warning 全 pre-existing 意图正确非回归/S2 集成路径待下次产品部署 exercise 组件已单独证/S3 environment.md 域名过期交 Planner)。
- **★含义**: test-automation **P3 生产 synthetic/canary 落地**, roadmap 仅剩 **P5**。**B098 已开批 building**(P5-F1 signoff 自动起草工具, 机械 scaffold 守铁律4; P5-F2=evaluator 流程不含)。★env 修正: 本项目活生产 API=`trade.guangai.ai`(非 environment.md 记的 astock.guangai.ai=nginx 401 非本项目面), 建议 Planner 修 environment.md。
- **B096 ✅ done** P4-F2 LLM-judge 语义层(advisory, additive, PASS 2/2)。**B095 ✅** P4-F1 确定性语义 lint(advisory, PASS 2/2)。**B094 ✅** 游资 follow **NO-GO**; ★smart-money 免费两支测尽(机构 B077 INCONCLUSIVE+游资 B094 NO-GO), institutional 仍需付费 Tushare ¥200(未买留用户)。**B093 ✅** hk_china real-stock **NO-GO(保 proxy)**。**B092–B074 ✅**。
- **接续**：★战略决策待用户(免费策略研究无强 edge)。backlog 剩: A股聪明钱[机构 ¥200 待用户] + test-automation **P5**(独立评审, 铁律 4, 基建 user-gated) + residual-engine(触冻结待用户)。34+ learnings 待用户确认。★key 曾对话明文暴露→建议用户用完轮换(与 commit 安全独立)。

## 遗留 / soft-watch
- **B097 S1/S2/S3**（非阻断）：actionlint deploy.yml exit1=SC2087 warning(SSH heredoc 故意 client-side 展开, 4 处 pre-existing+1 新 synthetic 步同惯用法)非回归 / synthetic→rollback 集成路径待下次产品部署 exercise(组件已单独证零假红+armed teeth) / environment.md 域名过期(prod=trade.guangai.ai 非 astock, 交 Planner 修)。
- **B096 O1/O2/O3**（非阻断）：frontend CI Playwright E2E smoke flake(backend-only 无关, 非 deploy gate) / 语义 judge 尚无 runtime-gate 消费者(advisory) / cassette 按录制顺序重放(EVAL_SET 顺序 load-bearing)。
- **B095 O1/O2/O3**（非阻断）：确定性 pre-filter 固有'宁漏勿误'漏报口(bare 下单剔除+NEGATION_WINDOW=5, docstring 明述, P4-F2 后手) / 小写 allowlist 演进需守证据门 / lint 尚无 runtime/CI 消费者(advisory-only 能力层)。
- **B094/B093**（非阻断, 归档）：B094 events.csv 重复键未去重(dedup 后仍显著 NO-GO)/priced 1,279 非满 1,500/仅 N5 edge；B093 proxy 弱基准+25 季 SGOV-floored 单 regime+幸存者=结构性天花板。
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
