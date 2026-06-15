# B063 Reverify Signoff 2026-06-15

> **状态：** ✅ **REVERIFY PASS → B063 DONE**  
> **批次：** B063 — hk_china 真数据 Batch 2（FX 层 + real-data 策略 + 回测对比 = 决策点）  
> **Finding 闭合：** B063-F004-CORE-1（Planner 否决 Codex『框架就绪当 FULL PASS』后 Generator 真跑）  
> **Evaluator：** Claude CLI（本轮代 Codex，因 Codex 连续 3 批推诿真跑被路由到 Generator 执行后，Evaluator 角色仍须确认）

---

## 1. 复验目标（required_fix 逐条核）

| 项 | 要求 | 核查结论 |
|---|---|---|
| (1) VM 真跑产出真数字 | proxy vs real 的 CAGR/Sharpe/MaxDD/vol/turnover/cost 同口径 USD | ✅ CLOSED |
| (2) S2 §8 质量验证 | 深度/复权/akshare-baostock 交叉源<0.5%/HK 源，非「CSV 有行」 | ✅ 真跑+诚实裁定 NOT PASS |
| (3) 诚实偏差分析 + draft go/no-go | PIT 是否真做到/残余选择偏差/集中度 vs 数据源归因 | ✅ CLOSED |
| (4) commit 报告 | 报告 + artifacts 入 git | ✅ commit 70a3918 |

---

## 2. Finding B063-F004-CORE-1 闭合确认

### 2.1 核心交付物验证

**报告文件**：`docs/test-reports/B063-hk-china-real-data-batch2-fx-backtest-comparison-report-2026-06-15.md`  
**对比 JSON**：`docs/test-reports/B063-artifacts/b063_comparison.json`（VM 真跑产物，Evaluator 本地读取验证）

#### 真执行数字（from artifact JSON，本地解析确认）

```
proxy (MCHI/FXI/KWEB/ASHR):
  CAGR         = +2.77%  ✅
  Sharpe       =  0.550  ✅
  MaxDD        = -0.96%  ✅
  defensive    = 12/20   ✅

real (26 名个股 top_n=6):
  CAGR         = -0.06%  ✅
  Sharpe       = -0.322  ✅
  MaxDD        = -0.42%  ✅
  defensive    = 20/20   ✅
  avg_holdings =  0.0    ✅（核心发现）
  forced_defensive = 0   ✅（非数据缺口，是真实信号）
```

这是 **真执行数字**（JSON timestamp `2026-06-15T02:49:46Z`，VM 真跑产物）。与上轮 signoff 的「框架就绪/后续执行路径 1-3」完全不同，是明确的闭合。

### 2.2 最重要诚实发现（报告 §5 确认）

- **real 策略 20/20 季度 regional_risk_off 全防守、0 选股**（forced_defensive=0 = 数据覆盖完整，是 2021-24 中国熊市真 risk-off 信号 + 前~4 季 200D MA 无 warmup 人为防守）
- real 的 -0.06% = **SGOV 现金 − 摩擦**，不是选股结果
- proxy/real 差异主因 = **risk-off bellwether 选型**（KWEB/MCHI/FXI vs 3 mega-cap 腾讯/阿里/茅台）这个策略构造差异，**非数据源**
- **核心假设「真个股 vs ETF」根本没被测到** ← 这是最重要的诚实点，报告 §5.1 明确披露

这与 spec §2/§3 要求的诚实归因完全一致：不把策略构造差异误记为「真数据更差」。

### 2.3 S2 §8 质量验证（真跑 + 诚实裁定）

- **跑了**：ashare_quality_check.py 全 26 名 universe，2 轮（artifacts 均在 git）
- **深度**：可覆盖样本均 8.45 年 ✅
- **cross-source A股**：偏差 2.1%–60.8%（0/5 distinct 通过 <0.5% 容差） ❌
- **HK**：东财端点 ConnectionError 全挂（B062 已知，quality 工具未改 sina） ❌
- **裁定**：**S2 §8 NOT PASS**——诚实裁定，支持 NO-GO，与报告结论一致

关键区分（报告 §3.1 vs §3.2）：
- backtest 用的 unified CSV 数据 26/26 名完整（sina 端点，B062 fix af57842）= backtest 可信
- S2 §8 cross-source 验证 = 工具端点缺陷（非 backtest 数据缺陷），但裁定仍是「未达质量闸」

---

## 3. L1 门禁核查

| 门禁 | 本机结果（.venv Python 3.11） | 说明 |
|---|---|---|
| **trade pytest** | ✅ **887 passed** | 全套单元测试通过（Generator VM 报 891，差 4 在 VM-only 或时序覆盖） |
| **B063 专项测试** | ✅ 13 passed | test_hk_china_comparison + test_hk_china_real_backtest + test_hk_china_backtest |
| **mypy strict（B063 新模块）** | ✅ 0 errors | hk_china_comparison_runner / hk_china_comparison / hk_china_real |
| **ruff（B063 新文件）** | ✅ All passed | 4 个新 py 文件全 clean |

---

## 4. 边界守住

| 边界 | 核查方式 | 结论 |
|---|---|---|
| **live Master 不碰 hk_china_real** | `test_master_does_not_import_real_strategy` 通过（`hk_china_real` 不在 master_portfolio.py） | ✅ |
| **trade 离线（无 network import）** | grep hk_china_comparison_runner / hk_china_comparison / hk_china_real — 无 akshare/requests/httpx | ✅ |
| **no-broker** | 全流程只读 CSV → 内存回测 → JSON，无 broker/order/ticket | ✅ |
| **US / Master 不破** | 887 tests pass，master guard test PASS | ✅ |
| **研究态不碰 live 推荐** | hk_china 仍 proxy；real-data 策略纯增量研究模块 | ✅ |

---

## 5. Batch 3 go/no-go（基于报告真数字）

**裁定：NO-GO / 未证实**

理由三条（报告 §6 精简）：
1. 无正面证据真个股优于 proxy（real -0.06% vs proxy +2.77%）
2. 更关键：核心假设根本没测到（real 全程持现金，不是选股 vs ETF 的比较）
3. 方法学未就绪：①200D 闸无 warmup；②risk-off bellwether 不同口径让结果不可比

**这是有效结论**，不是失败：诚实地回答了「没测出更好、且这一版方法学没真正测到」，数据地基（FX 层/HK-CN lookup/PIT 框架/对比 harness）不白费，可复用于 A 股策略/lookup。

---

## 6. 签收结论

### Status：✅ **REVERIFY PASS → B063 DONE**

| 维度 | 状态 |
|---|---|
| **Finding B063-F004-CORE-1** | ✅ CLOSED（真跑真数字 + 诚实报告 + commit） |
| **L1 gates** | ✅ 887 passed / mypy strict clean / ruff clean |
| **边界守住** | ✅ 全部 5 项通过 |
| **go/no-go 已产出** | ✅ NO-GO（诚实结论，归 Planner 最终决定） |
| **S2 §8** | ⚠️ NOT PASS（真跑裁定；cross-source 工具端点缺陷；支持 NO-GO；非 backtest 阻塞） |

**对比上轮 signoff（被 Planner 否决）的变化**：
- 上轮：「框架就绪 / READY for execution」+ 无数字
- 本轮：**真执行数字（JSON artifact）+ 诚实偏差分析（§5）+ Batch 3 NO-GO 建议（§6）**

**B063 所有 4 features 验收完毕。交 Planner done 阶段：读真报告 → go/no-go 最终决定 → 需求池规划。**
