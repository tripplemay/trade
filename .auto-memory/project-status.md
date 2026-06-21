---
name: project-status
description: 项目当前状态快照（覆盖写，≤30 行）— 当前批次、计划、决策、遗留、永久硬边界、Framework 状态
type: project
---

## 当前状态
- **当前：B071 verifying（2026-06-21，generator F001-F004 全 done，交 Codex F005 元批次验收）** = 测试自动化基建 Phase 0+1（地基批，★最高 ROI）。把 Codex L2「真实数据回归行为」桶下沉 CI。
- **F001 门禁确权（纯 doc）**：`docs/dev/B071-gate-authority-audit.md` 逐 7 workflow 实测，结论=L1 全门禁在 push+PR 全跑→**Codex verifying 复跑 L1 冗余可跳 L2**；补 `safety-eval`（job 名，≠workflow 名 `AI Safety Eval`）入 branch-protection required + path-scoped required 卡死语义。
- **F002 golden 真数据** `data/fixtures/golden/`：25 优质（真 SEC）+13 ETF（真价）2019-2023 含 2020/2022 危机窗，3.74MB，`_freeze.py` 从 gitignored snapshot 裁 bit-identical（剔 CAT/GOOGL 无窗内 SEC）。
- **F003 注入 seam + 确定性 + N 策略两两不同**：loader.py/us_quality engine.py/precompute.py 补 `fixture_dir`；5 策略重跑 bit-identical + ★N 策略两两不同非退化（B050）。**★★用户授权修 us_quality 真实复权 bug**（raw open 买/adj close 估值→真数据-99% 假亏；修 `_wide_open` 用复权 open，合成 adj==close 故向后兼容，golden 上 -26.7% 合理；**亦影响生产 VM us_quality 回测，已随绿 CI 自动部署**）。
- **F004 验收即代码**：`tests/acceptance/` 两处（trade ①②⑤ + backend ②③④⑥）6 不变量永久回归 + python-ci/workbench-backend 显式 acceptance CI step + testing-strategy.md 约定。
- **门禁**：本机 CI-exact 全绿（ruff/mypy 两侧 + root 1031 + backend 1474/17skip + acceptance 5+5）；F003 CI 全绿已部署；F004 Python CI 绿，backend/frontend CI 跑中。

## 遗留 / soft-watch
- **Codex F005 重点**：①L1 全门禁 ②★mutation 核 acceptance 有牙齿（改坏每条不变量→对应 acceptance 必须红）③golden 确定性（重跑 bit-identical）④门禁确权属实 ⑤零回归 ⑥signoff 流程确认（verifying 跳 L1 复跑、复发不变量 acceptance CI 守、只审新颖/模糊，守铁律 4）。
- **proposed-learnings 留 3 条 B071**（待 done 阶段 Planner 裁）：①复权 bug 规律+合成 adj==close 系统性掩盖 ②records 引擎 raw-close 估值轻微失真（用户裁本批不修）③验收即代码常态化约定入 role-context。
- **B070 follow-on（非本批）**：2 因子（quality）去偏 baostock 基本面管线；港股 P3（backlog B055）。

## 永久硬边界
- B045 market data refresh (r) 只读 + §12.10.2 AST 守门；research-safe / no-broker / no-AI 预测 / no 自动下单；hk_china 仍 ETF proxy。
- golden 只进测试 fixture seam，不碰生产 data_root/unified 真数据路径。

## Framework 状态（最新 4 版）
- **v0.9.48**（B066）：generator.md §28 停牌 ffill+NaN 安全读价禁 `or 0.0` / §29 多变体退化空仓必须红旗。
- **v0.9.47**（B065）：generator.md §19.1 ruff 本地须目录上下文 `python -m ruff check .`。
- **v0.9.46**（B064）：generator.md §27 前端「本机绿≠CI 绿」二坑。
- **v0.9.45**（B061+B062+B063）：★evaluator FULL PASS 系统性退化三实例。

## 已知 gap
- 本机 python3=3.9.6，用 `.venv/bin/python`；ruff 本地须 `python -m ruff check .`。backend 测试跑前需 `cd workbench/backend && .venv/bin/python -m pip install ../..`（装新 trade）。golden 必须落 `data/fixtures/**` 才 commit。
