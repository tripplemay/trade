# B078 — A股 data-refresh 卡死修复（每日刷新挂死 → A股 推荐/模拟盘冻结）Spec

**批次定位：** 生产缺陷修复（hotfix，B075 宽宇宙回归）。`workbench-data-refresh.service` 自 2026-06-22 拉 A股 时**挂死 3 天**（"activating"卡住、只烧 18s CPU=网络阻塞），堵住所有后续每日刷新 → A股 价格/宇宙冻在 06-22 → cn_attack 推荐每天重吐同一个 06-22 快照 → 模拟盘 06-23 跟完后无新推荐可跟。修=给 A股 拉取加超时+watchdog（杜绝挂死）+ 修 paper 负现金。

**来源：** 2026-06-26 用户报「A股 两策略推荐页每天有新股票但模拟盘不调仓」→ planner VM 生产诊断（铁律 9）→ 根因确认 → 用户确认立批。

---

## 0. 根因（planner VM 实测,焊死）

- **现象纠正**：A股 推荐**没在每天变,是冻在 06-22**（price_snapshot A股 / 统一 CSV / cn_pit_universe 最新都 06-22）。模拟盘**已正确跟到**（06-23 调仓,现持 06-22 推荐的 25 只小盘）。"不调仓"=之后无新推荐(数据冻结)。
- **铁证**：`data-refresh.service` `Active: activating (start) since 2026-06-22 02:30; 3 days ago`,Main PID 649789 仍在、CPU 仅 18s（阻塞死等）。最后日志 `Jun 22 02:30:37` 拉完美股 Tiingo → 卡在 A股 那步无输出。服务一直 activating → systemd 无法触发新刷新（timer Trigger=n/a）→ A股 永冻 06-22。
- **为何只 A股 冻**：美股价格走另一 timer `workbench-prices.timer`（Tiingo,06-25 仍跑）不受影响 → price_snapshot 美股=06-24、A股=06-22。
- **根因定位**：**B075 把 A股 宇宙扩到 1490 后,每日 data-refresh 的 A股 逐只 akshare 拉取无 per-call 超时 → 某只挂住 → 整个 service 死等 3 天**（B075 全量建宇宙曾跑 4h21min,日刷扛不住）。是 B075 宽宇宙回归。
- **次要 bug**：两 paper 账户 cash 负（-102/-103）——B074 剥 CASH sentinel 后满仓 cash≈0,06-23 调仓成本(印花税+滑点 206/205)无缓冲可扣 → 透支。

---

## 1. 复用清单（已核源码）

| 资产 | 位置 | 用法 |
|---|---|---|
| A股 价格 loader | `data_refresh/cn_hk_prices.py CnHkPricesLoader`（akshare lazy per fetch,逐只）| 加 per-call 超时 |
| 宽集市值/宇宙 fetch | `cn_marketcap.py` / `cn_universe.py`（逐只 best-effort）| 同加超时 |
| data-refresh 编排 | `data_refresh/cli.py fetch` + `refresh.py`（含 B075 §34 partial-failure exit-code 容忍）| 超时→fail-fast→§34 容忍→完成推进 |
| §34 partial-failure | generator.md §34（宽块错误单列+rate floor）| 超时纳入 partial-failure 计数 |
| paper 调仓成本 | `paper/mtm.py` + `paper/targets.py`（B074 剥 CASH sentinel）| 留交易成本缓冲 |
| acceptance/守门层 | `tests/acceptance/`（B071-B073）| 数据新鲜度守门 |

---

## 2. Feature 拆解（3 features：2 generator + 1 codex）

### F001 — A股 拉取超时 + watchdog（杜绝挂死,日刷恢复推进）（executor: generator）

1. **★per-call 超时**：A股 逐只 akshare 拉取（CnHkPrices/cn_marketcap/cn_universe）加 per-call timeout → 单只挂住即超时 fail → 计入 §34 partial-failure → **整轮完成并推进日期**（不再死等)。
2. **整体 watchdog 兜底**：service 加 `TimeoutStartSec`（或 job 级 deadline）——即便逻辑漏网,systemd 也在 X 时间后杀掉,杜绝再"activating"卡 3 天。
3. **日刷窗口可行性**：实测加超时后日刷 1490 只在合理窗口内完成 + 成功率;若仍太慢/大量超时 → 收口（分批/降低日刷 universe 到实际需要的/宽集 prices 解耦到周级,与 cn-universe 同 cadence）。
4. **部署 ops**：部署前/中 `systemctl stop` + 杀掉卡死 PID 649789（旧进程不会自己退,新码不生效）。
5. 单测（超时触发→partial-failure 计数→refresh 完成,确定性 fixture）。

**Acceptance：** A股 拉取有 per-call 超时（挂住→超时→§34 容忍→完成推进）+ watchdog 兜底;实测日刷在合理窗口完成 + A股 数据日期推进到当日;杀重启卡死进程。Gates：backend pytest/ruff 目录上下文/mypy CI-exact 0。

### F002 — paper 负现金修复 + 数据新鲜度守门（executor: generator）

1. **负现金修复**：paper 调仓为**交易成本预留现金缓冲**（不满仓到 cash=0;或调仓时从目标里扣留成本额）→ cash ≥ 0。修正 B074 剥 CASH sentinel 的副作用。
2. **★数据新鲜度守门**（acceptance/监控,复用测试基建）：断言/告警 **recommendation_snapshot as_of 距今 ≤ N 交易日** + **A股 price_snapshot 新鲜度** + **data-refresh service 不处于 stuck-activating > X 小时**——让"静默冻结"这类 bug 被 CI/监控抓（本次冻结 4 天无人知=正是该守的）。
3. 单测（负现金消除 + 新鲜度断言有牙齿）。

**Acceptance：** paper 调仓后 cash ≥ 0（留成本缓冲）;数据新鲜度守门（as_of 超期/service 卡住→红/告警,故意造陈旧→触发）。Gates 同 F001 + acceptance。

### F003 — Codex L2 真机验收 + signoff（executor: codex）

**真机/生产回归批次——signoff 含实测证据（§29）：**
- L1 全门禁（verifying 可跳 L1 复跑）。
- **L2 真机（VM,贴真返回）：** ① 部署修复 + 杀重启卡死进程 → `data-refresh.service` **不再卡死**（超时生效,贴日刷耗时/成功率,服务正常 Deactivated 而非永 activating）;② **A股 数据恢复每日推进**（price_snapshot/CSV/universe as_of 前进到当日,非冻 06-22）;③ cn_attack precompute as_of 前进 + 推荐刷新;④ **模拟盘恢复跟踪**（新推荐 → paper-mtm 调仓）;⑤ **负现金消除**（cash ≥ 0）;⑥ 新鲜度守门绿;⑦ 美股/Master/regime 零回归。
- 边界:research-only/no-broker/no 真金;HEAD≡prod;recent-errors=0。signoff 实测证据逐条（贴 service 状态前后 + 数据日期推进 + paper cash）。

---

## 3. 状态流转 + 不变量

- 混合批次：`planning → building(F001→F002) → verifying(F003) → done`。
- **不变量**：① 美股/Master/regime 数据 + paper 零回归;② research-safe / no-broker / no 真金 / 只读市场数据(§12.10.2 boundary r);③ A股 拉取超时不改数据正确性(超时仅防挂死,拿到的数据照常);④ §34 partial-failure 容忍不变;⑤ ruff 目录上下文 / mypy CI-exact;⑥ 数据新鲜度守门不误报(正常日刷不触发)。
- **诚实边界**：① 超时修的是"不挂死",若 1490 日刷本就太重(大量超时)→ F001 须收口宽集日刷策略(诚实记可行 universe 规模,呼应 B075 feasibility);② paper 负现金是 B074 满仓副作用,留缓冲解;③ 本批不改 cn_attack 策略逻辑(仍研究态)。
- **后续**：若 F001 实测 1490 日刷不可行 → 宽集 prices 日刷策略重估（解耦/降规模）单列;数据新鲜度监控可扩为生产 healthcheck。
