---
name: role-context-evaluator
description: Evaluator 角色行为规范 — 测试分层、UI 验收、签收报告（不存计划和进度）
type: feedback
---

## 测试分层策略 L1/L2

- L1（本地）= 基础设施测试：auth、路由逻辑、协议格式、错误处理、读类操作
- L2（Staging）= 全链路测试：真实外部调用、计费扣款、端到端写入
- **L1 FAIL ≠ 产品 Bug**（本地常用 PLACEHOLDER key/mock，调用真实服务会失败）
- L2 测试需用户明确授权再执行
- acceptance 中带 [L1] / [L2] 标注的项，按层级处理，不在错误环境强行验证

## 测试域所有权

- 测试代码（单元、E2E、压测）由 Evaluator 编写，Generator 不介入
- `executor:codex` 的功能由 Evaluator 主动执行，产出报告写入 `docs/test-reports/`

## UI 验收要点

- 有设计稿的页面被修改后，必须与设计稿 HTML 交叉校验
- 核对项：DOM 结构、class 名、图标名、数据字段语义、按钮/链接目标
- 语义替换（换指标类型）= FAIL；区块删除 = FAIL；结构简化 = PARTIAL

## 签收报告（硬性）

- reverifying → done 前必须写 `docs/test-reports/[批次名]-signoff-YYYY-MM-DD.md`
- 使用 `framework/templates/signoff-report.md` 模板
- progress.json 的 `docs.signoff` 为空不得置 done

## Fixture-only PASS 不构成策略性能 conclusion

- L1 fixture 测试 PASS 仅证明实现正确性（schema、数学、guards、可重复性），**不构成策略性能 / 收益 / DD / turnover 的 conclusion**
- 任何对比性收益 acceptance（"variant A 优于 variant B"、"gap 缩窄 N%"、"turnover 改善"）必须在真实数据 snapshot 上 reverify 才能签收 PASS
- 来源：B016 → B017 反转（synthetic 上 HRP 略优 → real-data 上 HRP `-$496` + turnover +41%）
- 详见 `docs/engineering/testing-and-fixture-policy.md` §Fixture vs Real-Data Signal Reversal

## verifying 可跳 L1 复跑，只审新颖/模糊（v0.9.49 — B071）

- L1 全门禁（pytest/mypy/ruff 后端+trade、vitest/tsc/eslint）+ safety + ai-safety-eval 已全自动 CI（push+PR 全跑）→ verifying **无需逐条复跑 L1**，确认 CI 绿即可。
- 复发不变量（权重和=1 / 无负现金 / 账户源单一 / N 策略两两不同 / Master 兼容 / 防守 shares×市价）由 `tests/acceptance/` CI 永久守（mutation-check 保有牙齿）→ 不每批手验。
- evaluator **聚焦机器做不了的判断**：本批**新颖** L2 真实数据检查 + 模糊裁定 + 真金生产判断 + 独立对抗复审（守铁律 4）。决策级/真数据核心仍须实际执行+贴实测证据（§25.1/§29）。详见 framework/harness/evaluator.md §30。
