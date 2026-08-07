# proposed-learnings 归档 — v0.9.57（2026-08-06）

> 来源批次：B112（防御闸 A/B 裁定批，两轮修复；单条提案含 6 子内容）。用户确认后一并沉淀、清队列。
> 用户确认的落点分配与提案原始「建议写入」不同：内容 1/2/3 → evaluator.md，内容 4 → planner.md，内容 5/6 → generator.md。

---

## [2026-08-06] Claude CLI + Codex — 来源：B112（防御闸 A/B 裁定批，两轮修复）

**类型：** 新规律 ×3（evaluator signoff 沉淀）+ 新坑 ×3（generator 修复轮）

**内容 1 — golden 测试不依赖 git show old-sha（CI 浅克隆 fetch-depth:1）。**
固定历史基线应提交 golden 快照/指纹；golden 前必须 canonicalization
（float `.14g`、set 排序、date isoformat），否则 hash seed / 1-ULP 噪声造假回归。
（B112-F001-5a；落地实例 649c22f。）

**内容 2 — 浮点回测产物的等价判据是数值容差，不是 canonical JSON hash。**
同输入跨进程有 ≤3e-13 IEEE 末位噪声；hash 不同必须展开字段级 diff，
≤1e-10 且仅数值末位可接受，超阈或非数值字段变化即 blocker。（B112 signoff S1。）

**内容 3 — H6 覆盖披露必须逐段：名称、行数、跨度、去重优先级。**
只报合并总数会漏掉占半数以上的输入段（B112-F001-4a：3.2M 行新名价格段漏报未被发现，
指数「日历日」误标「交易日」）。

**内容 4 — spec 冻结输入条款，落笔前必须核实全窗口可得性。**
「top~1500 去偏 PIT 宇宙」在 2019-2026 全窗口本不存在（baostock 无 zz1000/800 dated 成分、
生产宇宙 2021-09 才起且有偏差），验收才暴露 → 数据缺口条款应预设分支：
「不可得 → 按数据缺口处理」，避免 fixing 轮才发现。

**内容 5 — 「提交前可运行」升级为「HEAD 可从原始输入复跑」。**
本地工作树修补未提交 = 验收方在 HEAD 复跑即死（B112-F001-2：日期 dtype 修复只存在本地）。
交付含 runner 的产物前，必须在干净 stash 状态下从原始输入冒烟一遍。

**内容 6 — 数据集拼接防方法论并集污染。**
同 as_of 不同源的宇宙块按 (as_of,ticker) 并集会造出 1700+ 名伪宇宙（B112 实测）；
拼接规则只能是「同源优先 + 异源补新块」，不得混合。

**落点：** 内容 1 → `evaluator.md §38`；内容 2 → `evaluator.md §39`；内容 3 → `evaluator.md §40`；内容 4 → `planner.md §spec 冻结输入条款落笔前必须核实全窗口可得性`（spec 起草 checklist 区新节）；内容 5 → `generator.md §50`；内容 6 → `generator.md §51`。

---

**框架版本：** v0.9.56 → **v0.9.57**。CHANGELOG v0.9.57。**活跃候选队列清空。**
