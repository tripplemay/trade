# proposed-learnings 归档 — v0.9.51（2026-06-23）

> 来源批次：B075 A股 生产股票池扩大到全市场流动 top ~1501（feasibility GO@1501，zero errors，0 fix-round done）。3 条 learning，用户 B075 done 收尾批准沉淀。

---

## 1. VM 跑 `/tmp/*.py` 临时脚本 `cd` 无效，须前置 `PYTHONPATH`（B075，refines environment.md）

**类型：** VM 执行坑

在 VM 跑 `/tmp/*.py` 用部署 venv 时,`sys.path[0]=/tmp`（脚本所在目录）,而 `/opt/workbench/.venv` site-packages 里 `workbench_api` 是 stale（缺 data_refresh 等子包）→ `import workbench_api.data_refresh` 报 ModuleNotFoundError,即便已 `cd /srv/workbench/current/backend`（cwd 不进 `sys.path[0]`）。**修法：`PYTHONPATH=/srv/workbench/current/backend` 前置**让源树覆盖 stale site-packages。environment.md 现有「cd 进 backend 再 import-check」对 `-m`/cwd-import 有效,对 `/tmp` 脚本无效——补这一行。**落点：** `.auto-memory/environment.md`（timer/precompute job 运行机制段补 `/tmp` 子条）。

## 2. feasibility-first 探针复用真生产 loader——既测可行性又验代码路径（B075 F001）

**类型：** 规律

B075 §23 VM 探针复用**真生产 loader**（`discover_ashare_superset` / `CnHkPricesLoader` / `CnMarketCapLoader` / `CnFundamentalsLoader`）,非合成 → 探针同时验证 ungate 代码路径真能在 VM 跑通（sina 发现 1501 / 日刷 100% 成功）。规律:feasibility-first 探针应调真生产 API,既测可行性又测代码路径（对比 `b070_feasibility_probe` 用裸 baostock=只测数据源）。**落点：** `generator.md §33`。配套 §23。

## 3. 宽 universe partial-failure exit-code 容忍——尾部失败不炸整轮（B075 F002）

**类型：** 新坑 / 流程约定

大宇宙（~1500）逐只刷必有尾部失败（退市/停牌）,旧 `main()` `errors>0→exit 1` 会让日 timer 天天假阳报红。修法:宽块错误单列计数（`cn_universe_price_errors`/`cn_fundamental_errors`,同时并入 errors 总数=单一 error 契约）+ `resolve_exit_decision` = core(US/CN_HK)错误严格 + 宽块按 rate floor（≤20%）容忍,真停摆（host down→大批失败）才红。是「partial-failure 优雅不炸整轮」的 exit-code 层落地,可复用于任何宽集逐只刷 job。**落点：** `generator.md §34`。配套 §28。

---

**框架版本：** v0.9.50 → **v0.9.51**。活跃候选队列清空。CHANGELOG v0.9.51。
