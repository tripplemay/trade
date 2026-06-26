# proposed-learnings 归档 — v0.9.54（2026-06-26）

> 来源批次：B078 A股 data-refresh 卡死修复（生产 hotfix，B075 宽宇宙回归，fix_rounds=1 done）。4 条 learning，用户 done 收尾批准沉淀。一次真实的 4 天 A股 数据冻结生产事故换来的硬核教训。

---

## 1. systemd Type=oneshot 默认 TimeoutStartSec=infinity = 永 activating 卡死根因（B078 F001）

oneshot service 的 `TimeoutStartSec` 默认禁用（infinity），与普通 service（90s）不同。ExecStart 内无超时阻塞网络读 → 永「activating」、timer Trigger=n/a、堵所有后续刷新（data-refresh 卡 3 天冻 A股 4 天）。诊断：`systemctl show -p ActiveState,SubState,ActiveEnterTimestamp`。每个 oneshot 数据刷新 service 须显式设 `TimeoutStartSec`。L2 部署须先 stop+杀卡死旧 PID。**落点：** `evaluator.md §32`（诊断）+ generator.md §38（超时）。

## 2. 宽集刷防挂死要包裹 ALL 真网络调用，bulk discovery 最易漏（B078 F001）

per-call 超时只包逐只不够：bulk 发现（`stock_zh_a_spot_em`）在逐只循环 BEFORE 跑、无超时 → 挂死则 0 数据、命门再冻（对抗式自审抓到，spec §1 只列逐只）。超时清单须含 (a)逐只 (b)bulk discovery (c)benchmark 所有真网络调用；daemon-线程+join(timeout) 原语（leak 线程 daemon 不阻塞退出；0/None=inline 零回归）。**落点：** `generator.md §38`。扩 §34。

## 3. paper 调仓成本要预留 round-trip(买+卖)（B078 F002）

`investable=equity*(1-cost_rate)` 只够买入腿；调仓 gross=买+卖 全程收费，高换手按卖出腿透支 ≈ held*cost_rate（B074 剥 CASH buffer 满仓后 cash -102/-103）。修：investable -= held_marked_value*cost_rate（卖出腿上界）→ 任意换手 cash≥0；from-cash 建仓 held=0 公式不变=建仓零回归。**落点：** `generator.md §39`。reverify cash +187.52 转正。

## 4. 静默冻结守门——as_of 业务日新鲜度 + service stuck-activating 双断言（B078 F002）

数据管道挂死最毒=无人报错（冻 4 天 precompute 每天重吐同快照、paper 照「跟」冻结目标）。把「快照 as_of 业务日年龄≤N」+「service 不 stuck-activating>X 时」做成纯函数+acceptance 守门（teeth：故意造陈旧→红；业务日免疫周末；teeth 测须 pin SHIPPED 默认阈在真实冻幅）。**落点：** `generator.md §40`。扩 §31 验收即代码。

---

**框架版本：** v0.9.53 → **v0.9.54**。CHANGELOG v0.9.54。
