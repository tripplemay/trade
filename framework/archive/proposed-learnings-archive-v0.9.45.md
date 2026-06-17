# proposed-learnings 归档 — v0.9.45（2026-06-18）

> 来源批次：B061 / B062 / B063 done 阶段累积。用户 2026-06-18 在 B063 done 收尾时批「全部沉淀，含 §25 流程修复」，清空全部活跃候选（含历史单例 async worker / sudoers wrapper / satellite 权重——破例不再等二例，因 §25 系统性问题触发整轮清队列）。

---

## ① ★系统性问题：evaluator FULL PASS 在真数据/真机核心验收未执行下标出（B061/B062/B063 三实例）

**类型：** 模板修订（evaluator 验收纪律）+ 系统性过程问题（须流程修复）

**三实例：**
- **B061 F005**：核心=§8 深度（真实数据全历史/5 符号/交叉源<0.5%）。L2 撞 401 auth 未拉到 A 股实数据 → §8 深度零实测，却判 FULL PASS（signoff 自承「端点受 auth 保护未能完全测试」）。
- **B062 F004**：核心=① HK lookup 0700.HK 真返回 ② CN/HK 真落 CSV ③ §8 质量跑 runner ④ ★US/Master 推荐 pre/post 实证零回归。L2 四项全未执行——只验「US 行存在」+结构论证+部署存在，却判 FULL PASS（用户 smoke 当场暴露 HK lookup 坏）。
- **B063 F004（最严重）**：决策点批次，核心交付=『real vs proxy 回测对比报告（真数字）+ Batch 3 go/no-go 建议』。Codex 标 FULL PASS→DONE，但 signoff 自承『回测框架就绪/后续执行路径:1.执行回测 2.分析 3.go/no-go』——回测从没真跑、零对比数字、无 go/no-go。整批的全部意义（决策依据）不存在却判 DONE。

**沉淀落点（v0.9.45）：** `evaluator.md §25.1`（FULL PASS≠部署存在/结构论证/「框架就绪」；红旗措辞；auth/网络挡核心→CONDITIONAL）+ `evaluator.md §29`（决策级/真数据批次 signoff 必含「实测证据」硬段）+ `planner.md done §1.5`（done 复核 FULL PASS 名副其实，决策点强制，路由 Generator 真跑或下沉 CI）+ `templates/signoff-report.md §实测证据`。**流程根因**：evaluator 缺真机 auth/真数据手段 → 系统性退化成「代码+部署验收」；结构性解法=测试自动化基建 golden 数据下沉 CI（backlog B0XX-test-automation-infra），当前缓解=决策级批次路由 Generator + planner done 强制复核。

---

## ② 新数据 provider/端点须本地实跑真调用，勿因兄弟端点通而推定（B062 F001）

**类型：** 新坑（generator 实现）+ 新规律

HK provider 把 akshare `stock_hk_hist` 当 A 股 `stock_zh_a_hist` 的港股镜像直接用，但两者命中不同主机：A 股走 eastmoney 常规主机（可达），HK 走 `33.push2his.eastmoney.com`（可复现 ReadTimeout，本地+prod 都坏，非 geo）。结果 prod 查 0700.HK 全失败。修=换 akshare `stock_hk_daily`（sina 端点，B060 验过可达）→真返回 5405 行腾讯（无 date 参须 provider 按窗过滤）。

**沉淀落点：** `generator.md §23` + `planner.md 铁律 9`。与 evaluator §25.1 互补（验收侧 vs 实现侧）。

---

## ③ 决策级/对比类 harness 须过 adversarial 公平性/诚实性复审（B063 F003）

**类型：** 新规律（generator/process）

对比 harness 全门禁绿+13 单测过，adversarial workflow（3 维度）抓出 9 confirmed 含 1 CRITICAL 公平性：proxy 信号自磁盘独立加载价格、real 信号读传入帧 → 两侧「同口径」承诺被破坏。其余修：CAGR wipeout 返 0.0 掩盖巨亏→−1.0、top_n 默认不同(2 vs 6)静默混淆→显式 surface、PIT universe 增长未披露→avg_candidates、defensive 混淆 data-gap 与规则→forced_defensive 分离。

**沉淀落点：** `generator.md §24`（含对比工具 6 项检查清单）。

---

## ④ spec 校验/检查条款须核实际实现粒度，现实已隐含满足则不造装饰机制（B061 F003，§22 扩展）

**类型：** 新规律（§22 的扩展）

spec §9.6 假设 daily 交易日 gap 检查会把 CN 节假日误判为缺口，要求按市场选日历。但 `loader._calendar_gaps` 实际是月粒度（>1 自然月才标 gap），对 CN（春节~1 周）天然安全 → 误判不会发生。裁定：不塞 daily CN 日历进离线 trade 引擎、不加装饰 market 参数（触 §17）、交付命名日历模块+市场检测工具+CN 安全回归测试。planner 接受。

**沉淀落点：** `generator.md §22.1` + `planner.md`（写「按 X 维度处理」前核行为差异）。

---

## ⑤ 队列清空（历史单例 + 小坑，用户批破例一并沉淀）

| 候选 | 来源 | 沉淀落点 |
|---|---|---|
| async job 范式（请求路径 enqueue→长驻 worker→轮询）| B047（单例，原等二例）| `generator.md §25` |
| narrow-sudoers 落盘须经 root 属 wrapper 防路径穿越 | B037-OPS1（单例，原等二例）| `generator.md §12.12` |
| satellite 子策略权重口径 total-level vs sleeve-relative | BL-B011-S2 F002（单例）| `planner.md`「satellite 子策略权重口径」段 |
| 改 JSON 长值用整值替换/程序化切片，勿前缀 Edit | B063 F002/F003 | `generator.md §26.1` |
| banlist 扫 loaded modules 用精确 import-root（子串误判 `__future__`）| B060 F002 | `generator.md §26.2` |
| 改 trade/ 后 workbench venv copy 须 force-reinstall 刷新 | B057 F004 残留 | `generator.md §26.3` |

---

**框架版本：** v0.9.44 → **v0.9.45**。活跃候选队列清空。CHANGELOG v0.9.45 条目含完整摘要。
