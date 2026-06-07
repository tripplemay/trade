# B045-OPS1 Trade Wheel Deploy Reliability Signoff 2026-06-07

> 状态：**PASS**
> 触发：B045-OPS1 F002 首轮验收（fresh deploy → smoke check 验证）

---

## Scope

B045-OPS1：修复 trade wheel deploy 可靠性（B045 signoff S4），加 deploy 后 smoke import check 铁律。F001 修 deploy.sh（`--force-reinstall --no-deps` + smoke check），F002 Codex L2 真机验证。

---

## L1 结果

```
backend safety guard tests: 38 passed
  - test_trade_package_install_wiring.py (4)
  - test_recommendations_request_self_contained.py (2)
  - test_market_scheduler_scope.py (32)

deploy.sh bash -n syntax: OK
ruff/mypy: N/A (纯 shell 改动)
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Fresh deploy dispatch | `gh workflow run "Workbench Deploy" --ref main` → run [27081690834](https://github.com/tripplemay/trade/actions/runs/27081690834) **success** |
| Deploy log smoke import check | `→ smoke import check: trade precompute modules` / `trade smoke import OK` |
| Prod `/api/health` | `version=d75eabf...` db ok |
| VM trade version auto-matched | `pip show trade` → **Version: 0.2.0**（无手动 force-reinstall） |
| VM smoke import | `import trade.backtest.master_portfolio; import trade.data.data_root` → **OK** |
| Manual trigger precompute | `systemctl start workbench-recommendations.service` → **saved=6 data_source=mixed error=None**（无 ModuleNotFoundError） |
| Auth `/api/recommendations/current` | **200**，6 positions |
| Auth `/api/debug/recent-errors` | `{"count":0,"records":[]}` |
| Prod HEAD ≡ main HEAD | 同为 `d75eabf`，零 diff |

---

## S4 Resolution

| B045 signoff S4 | 状态 |
|---|---|
| trade wheel deploy 须手动 force-reinstall | **已解决** — `--force-reinstall --no-deps` 自动装 trade 0.2.0 |
| 无 deploy 后 import 验证 | **已解决** — smoke import check 在 deploy.sh 中硬验证 |
| 静默安装失败 | **已解决** — smoke check 失败 → `::error::` + exit 1，deploy 硬失败 |

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version | `d75eabf68d5d0652dbe006068dd7f50acf6a9eb0` |
| Main HEAD | `d75eabf68d5d0652dbe006068dd7f50acf6a9eb0` |
| Diff | **0 commits** — 完全对齐 |

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | signoff + status machine |
| Post-signoff dispatch 是否需要 | **否** |
| 接受不同步声明 | 本签收 commit 仅含 signoff 报告 + 状态机更新；符号机元数据 diff 接受不同步（v0.9.25）。 |

---

## Decommission Checklist

本批次不含 decommission — N/A。

---

## Soft-watch

无。

---

## Framework Learnings

### 新规律

- **smoke-import-after-install 是可靠的 deploy 兜底**：pip 返回 0 不证明模块可 import（version 同号 / pip cache / dep 解析失败均静默）。deploy 后 import 关键模块 + 失败硬报是低成本高收益的防御。本批已列入 v0.9.36 铁律 + deploy.sh 实施。
  - 来源：B045 S4 → B045-OPS1 F001/F002
  - 建议写入：已写入 `framework/README.md` §venv 多包安装 + `deploy.sh`

---

## Conclusion

**Yes — 签收 PASS。** B045-OPS1 F002 全 acceptance 通过：

- L1：38/38 guard tests passed
- L2：fresh deploy (27081690834) success，deploy log 显示 `trade smoke import OK`
- L2：VM trade version 0.2.0 自动匹配，无需手动 force-reinstall
- L2：precompute 正常运行（saved=6，无 ModuleNotFoundError）
- L2：/current 200，recent-errors={count:0}
- Production HEAD ≡ main HEAD（d75eabf，零 diff）
- **B045 signoff §Soft-watch S4：已解决**
