# B043 AI Explanation Layer Signoff 2026-06-10

> 状态：**PASS**
> 触发：B043 F005 复验完成

---

## Scope

B043 为 Recommendations / Backtest / Risk 三页面增加 grounded AI explanation，并要求守住 no-AI 硬边界、请求路径外生成、以及降级不阻塞页面主流程。

---

## L1

```text
backend pytest (B043 targeted): 81 passed
frontend vitest (B043 targeted): 38 passed
```

本地另行验证了受保护页面登录态通路：`/risk`、`/recommendations`、`/backtest` 在临时 `NEXTAUTH_SECRET` / `ALLOWED_USER_EMAIL` + minted `authjs.session-token` 下均可打开，对应 API 返回 `200`。

---

## L2

### Production / Auth / Data Path

- `GET https://trade.guangai.ai/api/health` → `version=c866115c1ecfa1f1e2a9750628f230d3a8e2642c`
- 匿名访问受保护 API：
  - `/api/execution/risk-panel` → `401`
  - `/api/recommendations/current` → `401`
  - `/api/backtests/data-range` → `401`
- 已登录生产浏览器会话下，Recommendations / Risk / Backtest 页面均可正常打开；Network 面板确认：
  - `/api/execution/risk-panel` → `200`
  - `/api/recommendations/current` → `200`
  - `/api/recommendations/news?sleeve=satellite_us_quality` → `200`

### Risk Explanation

生产 `/risk` 实测显示：

- `主组合回撤 59.60%`
- `Kill-switch 阈值 15%`
- explanation 正文直接引用上述真实值，并解释 `momentum / risk_parity / satellite_us_quality / unclassified` 为主要 drawdown 来源

判定：文本为真实风险状态重述，无收益预测、无执行指令、无替代 quant 结论。

### Recommendations Per-Position Rationales

生产 `/recommendations` 实测显示已填充 per-position rationale，非占位。抽样：

- `GLD`：目标 `22.09%`，解释引用 `target weight 0.220856`、`momentum sleeve planning weight 0.4`、`signal date 2026-03-31`
- `SGOV`：目标 `21.95%`，解释引用 `target weight 0.219523`、`risk_parity sleeve planning weight 0.3`
- `JNJ`：目标 `21.33%`，解释引用 `target weight 0.213333`、`momentum sleeve 0.4`，并明确 `not a prediction of future performance`

判定：文本 grounded 在真实权重 / sleeve / signal date 上，且明确不是收益预测。

### Backtest Explanation

生产 `/backtest` 实测运行 `Master Portfolio / 旗舰组合` 后显示：

- `CAGR 19.34%`
- `Sharpe 1.63`
- `Calmar 13.61`
- `Max Drawdown -1.42%`
- `Turnover 3.60`
- `88 trades`

explanation 正文逐项引用这些真实指标，并将结论限定在 `2025-06-08` 到 `2026-06-08` 的历史窗口内。

判定：文本为历史结果总结，无前瞻收益承诺、无下单建议。

### Graceful Degrade

- 生产 `/recommendations` 自然呈现 `账户缺失` 场景：页面仍可渲染风险横幅、目标权重、per-position rationale 和门控结果，仅 `当前持仓` 区块诚实留空并提示需要 `accounts/me.json`
- 该降级证明 explanation 不是页面硬依赖，主页面在缺失账户 bootstrap 时仍可正常工作
- 未在 production 人为制造 LLM 不可用 / budget 超限，因为这会越过本轮 read-only / non-destructive 授权边界；相关 fallback 由 L1 用例覆盖

---

## High-Level Findings

- PASS：三页面 explanation 已在真 VM 正面出现，且均引用真实输入值，不是 placeholder
- PASS：Recommendations 修复了“占位 rationale 被幂等复用”的生产问题；当前生产样本均为真实 explanation
- PASS：Risk explanation 定时链路已实际产出内容，不再停留在空 snapshot
- PASS：no-AI 边界抽样通过，未见执行建议、收益预测或替代量化推导

---

## Ops 副作用记录

本批次无数据库 ops。

---

## Harness 说明

本批经 Harness 状态机 `planning → building → verifying → reverifying → done` 交付。
本次签收将把 `progress.json` 更新为 `status: "done"`，并写入 `docs.signoff`。

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `c866115c1ecfa1f1e2a9750628f230d3a8e2642c` |
| Main HEAD (`git rev-parse HEAD`) | `0f835aab49e6ebd9c61443eabb3bb4383f09de71` |
| Diff (`git log --oneline <deployed>..HEAD`) | `0f835aa chore(B043): prod status — c866115 deployed, 3 explanation surfaces real-LLM verified on VM` |

判断：HEAD 比 production 多 1 个元数据 commit；`git diff --name-only c866115..HEAD` 仅含 `.auto-memory/project-status.md`，产品代码无漂移，可接受。

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本签收 commit 仅含 signoff 报告、`progress.json`、`.auto-memory/project-status.md` 等状态机/证据文件，未推产品代码；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。 |

---

## Decommission Checklist

本批次不含 decommission。

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 本轮未在 production 主动制造 LLM outage / budget-cap 以观察 explanation fallback；该类破坏性验证超出当前授权边界 | low | 若后续需要演练，可在专门 staging 或用户单独授权窗口执行 |

---

## Framework Learnings

本批次无新增 framework learnings。

---

## Conclusion

Yes。B043 F005 复验通过，可以签收。
