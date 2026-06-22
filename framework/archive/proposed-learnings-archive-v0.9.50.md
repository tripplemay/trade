# proposed-learnings 归档 — v0.9.50（2026-06-22）

> 来源批次：B074 cn_attack A股 模拟盘建仓修复（生产 hotfix，0 fix-round done）。1 条 learning，用户 B074 done 收尾批准沉淀。

---

## paper「搁浅现金 / build_complete 永 False」诊断 family——双查证券 mark + 无 mark 的 cash sentinel（B074 F002）

**类型：** 新坑 / 规律（§17.1/B058 隐形变体 + planner 根因诊断完整性）

「target 含字面现金 sentinel(CASH)行 → pure paper engine 当作无 mark 的 skipped target → build_complete 永 False」是 §17.1/B058「目标无 mark→搁浅现金」family 的**隐形变体**。B074 planner VM 诊断只焊死 A股 价缺 mark(根因#1),漏了根因#2:cn_attack precompute 在 cash_weight>0 时追加一行 CASH(weight>0、无价),`compute_rebalance` 把它计入 `skipped_symbols`,`_apply_rebalance` 的 `fully_built = traded and not skipped` 因 CASH 永为 False——即便 A股 价同步到位也建不了仓。Master/regime 没事因为现金用实 ETF(SGOV)有 mark,不写字面 CASH。

**教训：** 诊断 paper 搁浅现金类 bug,必须同时核 (a) 目标证券 mark 是否齐 + (b) 目标里是否有无 mark 的 sentinel/cash 伪符号被 engine 误判 skipped。修法:#1 A股 价从统一 CSV 同步进 price_snapshot(`cn_snapshot_sync`,不碰 Tiingo/price_universe=零回归);#2 `paper/targets.load_strategy_targets` 剥离 cash sentinel(target_key 保留全目标指纹,只影响发布字面 CASH 的策略=零回归)。validate 用 `compute_rebalance` 实跑(含/剥 CASH 对照)最快锁死。**附**:spec「建仓成功=cash≈0」Master 模板对持现金缓冲策略(cn_attack)不准,应 cash≈buffer(本批剥 sentinel 后实际 ≈0)。

**沉淀落点：** `generator.md §32`（paper 搁浅现金诊断 family:双查 mark+sentinel;cash 缓冲用实 ETF 优于字面 CASH;剥离 sentinel;compute_rebalance 对照锁死）+ `planner.md §根因诊断`（诊断 paper build 失败查 sentinel 行勿只查证券 mark;建仓成功模板对持现金缓冲策略 cash≠0）。Codex L2 验两账户 build_complete=1/25 持仓。

---

**框架版本：** v0.9.49 → **v0.9.50**。活跃候选队列清空。CHANGELOG v0.9.50。
