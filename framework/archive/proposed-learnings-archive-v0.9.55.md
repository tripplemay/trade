# proposed-learnings 归档 — v0.9.55（2026-07-07）

> 来源批次：B080 / B081 / B083 / B087+B090 / B098（2026-07-03 → 2026-07-06 累积 10 条候选）。用户 2026-07-07 明确「沉淀 learnings，全批准」，一并清队列。
> 其中 P5-F2（B098）已于 2026-07-06 先行写入 `evaluator.md §33`（commit `c5694f7`），本次仅归档、不重复写入。
> ★第 6 条（B081 F004）以其 **F005 审计更正版**沉淀——原「分数股假象」结论已被证伪。

---

## 1. 编辑 `trade/` 触发 spec 未列的额外门禁（B080 F002）

F002 把 cn_attack 复合因子分从 `CnSignalResult.factor_contributions_dict()` 提到 `CnAttackLiveTarget`——一处 `trade/` 编辑 → 触发 spec「gates 同 F001」漏列的门禁：`mypy trade`（Python CI）+ 根 `ruff check .` + 根 pytest（cn_attack live/b075/b076 acceptance）+ 改 `trade/` 后必须 `.venv/bin/python -m pip install ../..` 重装 trade 到 backend venv（否则 backend 测试导入 stale 已装副本，报 `no attribute signal_scores`）。**落点：** `generator.md §41(a)` + `planner.md §种子数据落地路径`（gates 提醒）。与 B081 F001 合并为一族。

## 2. api.ts 新 required 字段致 Frontend CI 瞬红（B080 F004）

给 pydantic response schema 加**带默认值**字段（`PaperSummary.benchmark_symbol="SPY"` / `first_day_caveat=False`）时，`openapi-typescript` 仍标 TS **required**（响应恒含 → 无 `?`）→ 用字面量构造该类型的前端 fixture 立即 tsc 失败。api.ts regen（后端 commit）与 fixture 修复（前端 commit）分两 commit（api.ts 先落）→ 中间 commit Frontend CI 必红（`dd9f703` 红 → `46ba83b` 绿）。修法：后端 regen api.ts 后立即 grep 该 schema 名前端 fixture，同一 commit 补齐。**落点：** `generator.md §42`。

## 3. bootstrap-only seed 不入部署链 = 生产静默缺数据（B080 F005）

`workbench-bootstrap` CLI 的幂等 seed（`_import_trials` 27 trials / curated symbol_names）只手动跑、不在 `deploy.sh`（只 alembic upgrade）/ `workbench-deploy.yml`，且无 timer 自愈 → 部署后生产从不落库（B080 F001 `trial_registry=0` + B079 `symbol_name=0` 同源）。对比 OOS 红卡（迁移 0028）/ paper currency（0032）走 data-migration 随 alembic 自动落地就没这问题。修：trial 回填改 data-migration 0033。规则：部署后必须存在的种子数据必走 alembic data-migration 或显式接入部署链，不能只放 bootstrap CLI。**落点：** `generator.md §43` + `planner.md §种子数据落地路径`。遗留：curated symbol_name 生产=0 仍未修（非阻断，可 backlog）。

## 4. 改 backtest 默认口径的 trade/ edit 须跑全 root pytest + 多变体透传 switch（B081 F001）

翻转 backtest 默认口径的 `trade/` edit（config 默认值翻转，如 `lot_rounding: bool = True`）不能只跑 cn_attack 子集就 push——full root pytest 里 comparison/reporting/**overfitting detector** 也消费默认 backtest。commit `e94955f` 只跑 cn_attack 子集（65 绿），push 后 Python CI `test_implausible_sharpe_flagged` 红（round-lot cash-drag 压低小合成账本 Sharpe，检测器不触发）。修：`build_cn_attack_comparison` 透传 `base.lot_rounding` + 该测 pin 旧口径。另坑：多变体构造器加 config switch 易漏透传 `base.<switch>` → 比较静默忽略 caller 口径。规则：改默认口径 → full root pytest；加 switch → 同步透传所有多变体构造点。**落点：** `generator.md §41(b)`。与 B080 F002 合并为一族。

## 5. 执行限制的 loop-level freeze/restore 模式（B081 F002/F003）

回测引擎「某名当日不可交易」（停牌禁买卖 / 涨停禁买 / 跌停禁卖 / 退市前停牌窗口）**不要**在 `_execute_open` 内改目标权重（撞 cost-reservation 缩股 churn + 归一化难题，同 F001#3 三次失败）。干净方案 = loop-level freeze/restore：执行前把受限持仓名（exact shares + entry/peak）冻结取出并从 target 剔除 → 非受限账本在剩余 tradeable pool 正常 rebalance（full/partial/lot_rounding 全不动）→ 执行后原样放回，equity 守恒。F002 停牌 + F003 涨跌停复用同一 `restricted_today` 集合（∪ 合并）。开关 off → 集合空 → bit 级旧口径。**落点：** `generator.md §44`。

## 6. ★A/B 真机重跑：容量下限（非分数股假象）+ 慢跑抗 kill 基建（B081 F004，用 F005 更正版）

**★（1）回测保真度结论（F005 审计更正版，原「分数股假象」已被证伪）：** B081 A/B（B070 去偏 PIT，pure_momentum）初看 `lot@100k` OOS −14.7%（旧分数股口径 +28.4%），F004 一度误读为「边际大半是分数股假象」。**F005 独立数字审计证伪**——负数是 **10 万本金的容量下限**（25 只等权中约 9 只一手买不起 → skip → 现金拖累 + 高换手），非分数股假象：`lot@1M` OOS +23.5%、`lot@10M` +28.2%（保留 99% edge），edge 随本金放大即恢复。修正后教训：①引擎修真 A/B 的「手数取整」组必须**同时做本金扫描**（100k/1M/10M），否则把容量下限误读为策略失效；②宣称「某修复揭示假象」前先问该效应是否随本金/规模消失；③元教训「宣称 edge 前先跑引擎修真 A/B」仍成立；④**A/B 结论本身也要过独立数字审计**（F005 抓住 F004 的误读）。F002 停牌/退市在此策略 = no-op（流动动量票不停不退），修真项是否咬取决于策略持仓。**落点：** `README.md §经验教训「回测保真度」`。
**（2）慢真机跑抗 background-kill 基建（不受更正影响）：** 8 组 × ~5min 全宇宙回测（236M）在本 harness ~20min 必被 kill，每次重跑 CSV load ~5min 吃光窗口 → 永不前进。方案：runner resumable（每组落 JSON，跳已算）+ pickle 缓存 prices（reload 5min→30s），数轮收敛，缓存 gitignore（161MB）。**落点：** `generator.md §45`。

## 7. 前端 flaky 测 red main 诊断——改动面 vs 红测面物理关联 + rerun 不清须真修（B083 F002）

纯 backend commit（trial 登记 migration+bootstrap+backend test）让 frontend UI 单测红（`risk-banner.spec.tsx`）——backend 改动物理上不可能影响 frontend fixture → 疑 flake，本机隔离跑 3× 全绿 + 前序 commit CI 全绿证伪。**★rerun-不清更正（修正 §27）：** rerun 若不清 = 非随机 flake 而是 CI-环境一致 async race（点击 Generate 前只等 mode-CARD 渲染，未等 red→defensive post-render `useEffect` settle，CI 时序抢跑 → POST `{defensive:false}`）→ 必须真修（测加 `await waitFor(defensive radio checked)` 等 flip settle，组件不改），不可反复 rerun 赌绿。治本入 backlog test-automation-infra（查 test 间共享状态泄漏）。**落点：** `evaluator.md §34`（修正 §27）。

## 8. planner 抢跑 done/开批时序耦合（B087+B090）

两例同款时序耦合：Planner 在 evaluator signoff 提交落地**之前**执行 done 收尾或开下批（B087：done-phase 把 evaluator 未提交写盘状态 sweep 进自己 commit；B090：预设 PASS 开 B091 并重置 progress.json 消费 B090-done 瞬态）。两次恰为 PASS 而无害，但若裁定 fixing 则状态机不一致。规约：Planner 在 verifying/reverifying 期间不 done 收尾、不开下批；唯一开批前置 = evaluator signoff 报告 + 状态流转 commit 已在 origin/main；等待期可只读预研（注明「不动状态机」）。**落点：** `planner.md §done 收尾/开批前置 gate`（与第 10 条合并）。

## 9. （已先行沉淀）独立对抗评审触发点固化（test-automation P5-F2，B098）

P5-F2「固化独立对抗评审触发点」= 评估流程约定（非 generator 可构建代码）：每批 done 前独立 agent 只审新颖/模糊残留（机械部分 CI 绿），守铁律 #4；generator-side pre-commit 对抗验证 + 独立 evaluator 只审判断核 + signoff「审+签」。**已于 2026-07-06 用户确认后写入 `evaluator.md §33`（承接 §30，commit `c5694f7`）。本次仅归档，不重复写入。**

## 10. 并发写竞态致无效 JSON 进 main（B098 F002，铁律 #11 实例 + 已落实钩子）

多 session 并发写同一状态 JSON：planner done-phase 写 progress.json 与 evaluator signoff 写 progress.json 并发 → git 合并抓到 `session_notes.evaluator` 尾部断裂态 → commit `f2bbb1c` 短暂在 main tip 携带不可解析 progress.json（铁律 #11 breach，`4477e7d` 自愈）。★已落实：`scripts/check_state_json.py`（负测有牙）+ `scripts/pre-commit-hook.sh`（git-tracked）+ 本机 `.git/hooks/pre-commit` 已装。钩子只拦「无效 JSON」，拦不住「竞态覆盖」→ 根治 = 序列化写入（done-phase 须在 evaluator signoff 落地 origin/main 后才跑，与第 8 条同族）。**落点：** `harness-rules.md §启动流程`（clone 后装钩子 setup 步骤）+ `planner.md §done 收尾/开批前置 gate`（写入序列化，与第 8 条合并）。

---

**框架版本：** v0.9.54 → **v0.9.55**。CHANGELOG v0.9.55。**活跃候选队列清空。**
