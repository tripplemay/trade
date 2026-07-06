---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B098 ✅ done（2026-07-06, 混合批 1g+1c, Workflow-build）** test-automation roadmap **P5-F1 signoff 自动起草工具**。新增 `scripts/gen_signoff_draft.py`(598 行, 机械 scaffold: 批次/feature+被验 commit(scope 过滤)+改动文件 diffstat+CI 结论 echo gh 原始 conclusion+门禁 echo generator_handoff+生产面 location 分桶)+`tests/unit/test_gen_signoff_draft.py`(299 行, 23 测)。additive 零产品码。★裁定 **全 PASS 2/2**。独立验收(代 Codex, 隔离, 不信任'铁律#4-safe'声明→逐行读 598 行+复跑门禁+亲跑活工具反向对抗测试+grep 消费者+gh run view 复核): ★★命门1 工具不僭越判断(铁律#4, 最重, BLOCKING清)=render_judgment_sections() 零参结构证(inspect.signature 单测有牙)+判断段全硬编码[待独立评估填写]占位+亲跑 --batch B097(真绿 CI)判断半段 grep verdict=NONE(绿 CI 不诱导 PASS)+机械段只 echo gh 原始 conclusion/features.status/handoff(标自报未判定)/location(标非风险裁定)不映射 PASS→辅助脚手架非评估; ★★命门2 additive 零回归(BLOCKING清)=全仓 grep 消费者 0+无 CI wiring 不自动生成并提交+read-only(git log/diff/gh 只读, 写只在 -o, 缺数据 graceful)+既有 signoff 流程不变; ★命门3(BLOCKING清)=23 测双环境绿+ruff/mypy clean+CI(Backend+Python@6fc0721/Deploy@ae8c1cd success 独立 gh run view)+产品码 diff 空 HEAD≡prod。signoff docs/test-reports/B098-signoff-scaffold-tool-signoff-2026-07-06.md。3 soft-watch 非阻断(S1 §5 echo 整个 handoff 叙事含 generator 自拟框架措辞但明标自报置机械段不破铁律4, 未来可只 echo 门禁数字/S2 diffstat 范围含开批 chore 无关文件机械正确/S3 本机 py 无 ruff 须 venv)。
- **★含义**: test-automation **generator-buildable 部分全落地(P0–P5-F1)**。剩 **P5-F2**(独立对抗评审流程触发点)=evaluator 流程域, 非 generator 可有意义构建。
- **B097 ✅ done** P3 生产 synthetic 监控+synthetic→rollback 接线(additive)+定时 canary(PASS 3/3, 生产敏感批, 命门 1-5 详见 B097 signoff)。★env: 活生产 API=`trade.guangai.ai`(非 astock.guangai.ai)。
- **B096 ✅** P4-F2 LLM-judge 语义层(advisory)。**B095 ✅** P4-F1 确定性语义 lint(advisory)。**B094 ✅** 游资 follow NO-GO; ★smart-money 免费两支测尽(机构 B077 INCONCLUSIVE+游资 B094 NO-GO), institutional 仍需付费 Tushare ¥200(未买留用户)。**B093 ✅** hk_china real-stock NO-GO(保 proxy)。**B092–B074 ✅**。
- **接续**：★战略决策待用户(免费策略研究无强 edge)。backlog 剩: A股聪明钱[机构 ¥200 待用户] + test-automation **P5-F2**(独立评审流程, 铁律 4, evaluator 域) + residual-engine(触冻结待用户)。34+ learnings 待用户确认。★key 曾对话明文暴露→建议用户用完轮换(与 commit 安全独立)。

## 遗留 / soft-watch
- **B098 S1/S2/S3**（非阻断）：§5 门禁 echo 整个 generator_handoff.summary 叙事含 generator 自拟框架措辞(明标自报+置机械半段+§7 裁定空占位→不破铁律4, 未来加固可只 echo 结构化门禁数字) / commit-range 启发式 diffstat 纳入开批 chore 无关文件(机械正确非 bug, 范围宽于单一 feature) / 本机 py3=3.9.6 无 ruff/mypy 须 venv。
- **B097 S1/S2/S3**（非阻断）：actionlint deploy.yml SC2087 warning 全 pre-existing 意图正确 / synthetic→rollback 集成路径待下次产品部署 exercise(组件已单独证) / environment.md 域名已修正 trade.guangai.ai。
- **B096 O1/O2/O3**（非阻断）：frontend CI Playwright E2E smoke flake(backend-only 无关) / 语义 judge 尚无 runtime-gate 消费者(advisory) / cassette 按录制顺序重放。
- **B095 O1/O2/O3**（非阻断）：确定性 pre-filter 固有'宁漏勿误'漏报口 / 小写 allowlist 演进需守证据门 / lint 尚无 runtime/CI 消费者(advisory-only)。
- **B094/B093**（归档）：B094 events.csv 重复键未去重(dedup 后仍 NO-GO)/priced 1,279 非满 1,500；B093 proxy 弱基准+单 regime+幸存者=结构性天花板。**B089–B081**：见旧注。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True(仅人工解红卡；三重守门)。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 3 版）
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
