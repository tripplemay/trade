---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **B102 ✅ done（2026-07-07, 1g+1c, Workflow-build）** insider-buying **小盘 sleeve** first-look（复用 B101 增持事件 + 扩 fetch 非流动小盘 qfq 价格重测，收口 B094/B099/B101 反复留下的"小盘未测"caveat）→ **小盘 NO-GO**。★裁定 **全 PASS 2/2**。独立验收（代 Codex, 隔离, 最高怀疑度, 真 530 股面板复算非 fixture）：★★命门1 = **NO-GO 证据基础扎实性（本批命门，F001 初稿曾 INCONCLUSIVE data-incomplete 后改判 NO-GO）→ 裁定 NO-GO 成立不降级**：小盘 fetch 完成 **530/800 名(66.2%)**、覆盖 **32.7% 小盘事件**、**13/~101 打分月**（多数月 <20 名被弃）=覆盖确属残缺，但报告 foreground 而非隐藏（66.2%/32.7%/13月/33.8%退市/薄横截面均明标 caveat），裁定与覆盖匹配；NO-GO 非过度断言因①正确 scoped 到"免费数据部署决策"+付费 ¥200 门显式保留②决定性负面证据独立于覆盖=IC 噪音(13 月度 h5 IC 离散±0.45 t=1.18 不显著)+事件簿全 horizon×全 30-80bp 网格净负③幸存者33.8%退市=乐观上界仍 fail=保守；**自写独立 IC 实现(不 import generator run())逐位吻合**(h5+0.0863/t1.18, h20+0.0345, h60−0.0020)+bit 可复现。命门2 PIT 无前视（verbatim B101 公告月 M+1 入场 + 3 cohort 抽核入场晚于最晚公告 + 单测）。命门3 外推边界（报告保留付费日频 top_inst 门=免费全否≠¥200无效, latency-cutting 呼应 B099 滞后元凶）。命门4 无扫参(仅成本敏感度带)+0 产品码+L1 12 测+ruff 净+CI(python-checks/backend@58a9798 success)+Deploy 成功 HEAD≡prod。signoff docs/test-reports/B102-insider-smallcap-first-look-signoff-2026-07-07.md。2 软观察（非阻断）见下。
- **★含义（免费 smart-money 四角度全 NO-GO，免费空间穷尽）**：游资(B094)/机构建仓(B099, 滞后元凶)/insider 流动大盘(B101, 信号真空)/**insider 小盘(B102, 净成本全负乐观上界仍 fail)** 均无可部署 edge。→ **未测=付费 ¥200/日 Tushare 日频 top_inst**（用户真实目标唯一干净决定性测试：幸存者干净+批量快+**T+1 及时性**砍掉免费研究吸收的 ~1 月滞后），仍待用户决策。
- **B101–B074 ✅**（免费信号四支 NO-GO / 残差引擎 A/B INCONCLUSIVE B100 / 生产 canary / etc）。活生产 API=`trade.guangai.ai`（非 astock）。
- **接续**：★战略决策待用户（免费策略研究全无强 edge，免费空间收口）。backlog 剩：A股聪明钱[**付费 ¥200 日频 top_inst** 待用户] + residual-engine（B100 INCONCLUSIVE, 采纳待用户）。34+ learnings 待用户确认。★key 曾对话明文暴露→建议轮换。

## 遗留 / soft-watch
- **B102 S1/S2/S3**（非阻断）：13 打分月时间聚集(10 个 2017-2019, 2021-2023 零覆盖)报告未点明→强化 coverage-limited 但不翻转部署裁定 / "optimistic upper bound" 措辞非严格(excess 相对量幸存者同抬两端, 非 load-bearing) / 复算 json 本机 gitignored(md+coverage.json 承载全数字, 已 bit 复现)。
- **B101 S1/S3**（归档）：小盘 sleeve 未测门（B102 已收口）/ look-ahead 对照验收侧新增 / 复算 json gitignored。**B100/B098–B081**：见旧注归档。

## 永久硬边界
- B045 market data refresh (r) 只读+§12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；**hk_china 仍 ETF proxy（B093 NO-GO 坐实）**。
- cn_attack 仍研究态/OOS 红卡/edge 微弱不可配资。冻结再验证 pipeline **永不** validated→True（仅人工解红卡；三重守门）。**残差动量 B100 A/B INCONCLUSIVE，不切入。**
- golden 只进测试 fixture seam，不碰生产真数据路径。**smart-money 免费信号四角度 first-look 均 research-only（0 产品码），无一切入生产；免费空间已收口。**

## Framework 状态（最新 3 版）
- **P5-F2**（c5694f7, 2026-07-06）：evaluator.md §33 固化独立对抗评审触发点（承接 §30）；test-automation roadmap P0–P5 全完→backlog 移除。
- **v0.9.54**（B078）：generator.md §38-40 / evaluator.md §32 systemd oneshot 卡死诊断。
- **v0.9.53**（B077）：§36 §23 派生字段 measured-not-assumed / §37 first-look 覆盖-门控裁定 / evaluator.md §31 date-bomb。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装 trade；改 trade/ 后须重装）。
