# B088 F001 — vol-targeting 控制律(open-loop/smoothing/feedback) + turnover 对比（done）

> BL-B013-D1：open-loop vol-targeting turnover spike → smoothing/feedback 减 turnover 维持控波。
> **零策略/flagship 改动**：新建研究模块 `trade/analysis/vol_targeting.py`（纯 numpy/pandas），risk_parity 产品默认不动。

## 模块：三控制律（先验禁扫参 target=0.08 / halflife=21 / k=0.5）

| 变体 | 公式 | 意图 |
|---|---|---|
| `open_loop_exposure` | `e_t = min(target/rv_t, max)` | baseline（同 risk_parity），rv 跳变→exposure spike |
| `smoothed_exposure` | `e_t = min(target/ewma(rv,halflife)_t, max)` | 平滑 rv 估计 → 平滑 exposure |
| `feedback_exposure` | `e_t = e_{t-1} + k·(openloop_t − e_{t-1})` | partial-adjust 比例控制（k=1→open-loop, k<1 减突变） |

## turnover 对比（合成 regime-vol 序列, seed=42, 可复现, 客观可测）

| 变体 | turnover | vs open-loop | realized vol | vs target |
|---|---|---|---|---|
| open_loop | 9.67 | 100% | 0.0886 | 1.11x |
| **smoothed** | **4.46** | **46%（−54%）** | 0.1044 | 1.30x |
| **feedback** | **8.50** | **88%（−12%）** | 0.0906 | 1.13x |

## 结论（诚实, 与文献一致, 可测非主观 edge）

- **turnover 减是控制律机械性质**（合成序列客观证）：smoothing **−54%** turnover，feedback **−12%**。
- **★权衡诚实披露**：
  - **smoothing**：turnover 大减（−54%），但**控波略松**（realized 1.30x vs open-loop 1.11x target）——平滑 rv 估计牺牲一点跟踪。
  - **feedback**：turnover 小减（−12%），但**控波几乎不损**（1.13x ≈ open-loop 1.11x）——更温和权衡。
- **realized vol 普遍 1.1–1.3x target（高于 target）**：21 日 rv 估计**滞后 regime 切换**（切换期 exposure 用旧 vol → 超配）——vol-targeting 已知估计滞后局限，诚实标注（非本控制律引入）。
- **含义**：要大减 turnover 选 smoothing（接受控波略松）；要保控波选 feedback（turnover 小减）。真策略集成（对真 US 收益 + 入 risk_parity 可选）留 follow-up。

## 验收：**done** — 4 单测(控制律 + turnover 减机械性质) pass + ruff + mypy clean + 零回归(不改 risk_parity/策略产品码).
复现：`python -m scripts.research.b088_vol_targeting_demo`。
