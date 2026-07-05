# Audit — data_refresh orchestration fragility (fetch_main silent-skip risk)

> **状态：read-only 审计发现，非 spec、非 active 批次。** 源起：B082 F004 evaluator 标注
> "dividend_lowvol 刷新排序脆弱性(今治本隔离，但 **refresh 编排整体脆弱**)→ backlog"。本文把该概括
> 落到**具体行**，供 planner 判定是否开 robustness 批次。**不动**状态机；无代码改动。

## 根因（B082 F004 ISSUE-1 的同类，尚未全治）

`workbench_api/data_refresh/cli.py::fetch_main` 的刷新步骤**顺序执行**，`run_refresh`（Tiingo US/CN 价格）
**无 per-call 超时**（evaluator 实测：2026-07 的 Tiingo 429 风暴让它 hang，systemd `TimeoutStartSec=1800`
到点杀整个进程）。**排在 `run_refresh` 之后的步骤，在 Tiingo hang 日永远不执行**——不是 raise 被吞，
是整进程被 systemd 杀在 `run_refresh` 里。

## 当前顺序 + 暴露面（fetch_main，B082 F003 fix 后）

| 顺序 | 步骤 | 依赖 Tiingo? | run_refresh hang 日 | 备注 |
|---|---|---|---|---|
| 1 | `run_dividend_lowvol_refresh` (L253) | 否(sina/csindex/chinabond/legulegu) | ✅ 已前移·安全 | **B082 F004 已治** |
| 2 | `run_refresh` (L262) | **是**(命门) | — hang 源本身 | 无 per-call timeout=根 |
| 3 | `run_fx_refresh` (L282) | **否**(FRED) | ⚠️ **静默跳过** | Tiingo 独立却在其后 → 同 ISSUE-1 病 |
| 4 | `run_cn_benchmark_refresh` (L291) | **否**(akshare CSI300) | ⚠️ **静默跳过** | 同上；cn_attack 对照报告 benchmark 断供 |
| 5 | `_build_cn_universe` (L301) | **是**(读 run_refresh 写的 prices CSV) | 跳过(但合理) | 真依赖 run_refresh 输出，不能前移 |

**结论：`run_fx_refresh` + `run_cn_benchmark_refresh` 是尚未治的两条 Tiingo-独立序列**——与被治的
dividend_lowvol 完全同病（独立数据源却排在无守护的 hang 源之后）。FX 断供 → backtest USD 换算用陈旧汇率；
CSI300 断供 → cn_attack 对照报告 "benchmark unavailable"。二者内部虽 best-effort（fetch 失败只 log），
但**进程被杀在 run_refresh 里时它们根本没机会跑**。

## 两个修复方案（planner 右尺寸）

1. **最小（同 B082 F003 裁定 A）**：把 `run_fx_refresh` + `run_cn_benchmark_refresh` 也**前移到 `run_refresh` 之前**
   （与 dividend_lowvol 并列）。`_build_cn_universe` 留后（真依赖 prices 输出）。零改 run_refresh，只重排独立步骤。
2. **治本（推荐持久解）**：给 `run_refresh` 的 Tiingo per-symbol/per-call fetch 加**超时**（CN A股序列 B078 F001
   已有 `fetch_timeout_seconds`，US/CN Tiingo 路径缺）。根除 hang → systemd 不再杀轮 → 顺序无关。
   代价更大（触 run_refresh 内部，需守 exit-code 语义字节不变 + 回归）。

## 建议

- **入 backlog**（evaluator 已建议）：一条 "data_refresh 编排健壮性" 项，优先**方案 1**（低风险、复用 B082 裁定 A 模式），
  方案 2 作 follow-up（Tiingo per-call timeout 是根，但风险面大，需独立批次守 run_refresh 回归）。
- **验收**：单测锁 fx/benchmark 在 run_refresh 之前调用（同 c53375f 的 dividend_lowvol 顺序+隔离测）；
  生产实测 Tiingo-不健康日 fx/benchmark 仍落地。
- **零回归**：run_refresh 及其 `resolve_exit_decision` 字节不变（同 B082 F003 fix 的守则）。
