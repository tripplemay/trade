# B048-OPS1 Alembic Deploy Reliability Signoff 2026-06-08

> 状态：**PASS**
> 触发：B048-OPS1 F002 首轮验收（fresh deploy → alembic==head 无需手动）

---

## Scope

B048-OPS1：修复 deploy alembic 自动升级可靠性（B048 signoff Finding #1 / S2）。F001 诊断根因+修 + deploy 后断言 alembic==head 硬失败。F002 Codex L2 真机验证。

---

## L1 结果

```
backend safety guard tests: 119 passed, 15 skipped
ruff: N/A (纯 shell 改动)
deploy.sh bash -n: OK
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Fresh deploy dispatch | `gh workflow run "Workbench Deploy" --ref main` → run [27119352795](https://github.com/tripplemay/trade/actions/runs/27119352795) **success** |
| Deploy log env loading | `→ loading env from /etc/workbench/workbench.env for alembic` |
| Deploy log alembic upgrade | `→ alembic upgrade head` |
| Deploy log assert head | `→ asserting alembic at head (B048-OPS1)` / `✓ alembic at head ['0011_b048_price_history'] (db=sqlite:////var/lib/workbench/db/workbench.db)` |
| Prod `/api/health` | `version=e0c035c...` db ok |
| `/api/recommendations/current` | **200**, 6 positions, 2 gates (kill_switch + min_equity) |
| `/api/execution/risk-panel` | state=green, dd=0.0, threshold=0.15, 6 sleeves |
| `/api/debug/recent-errors` | `{"count":0,"records":[]}` |
| Prod HEAD ≡ main HEAD | 同为 `e0c035c`，零 diff |
| No manual alembic upgrade | 本次 deploy 后无需手动 `alembic upgrade head` |

---

## B048 Finding #1 / S2 Resolution

| B048 Finding | 根因 | 修复 | 状态 |
|---|---|---|---|
| #1: alembic 0007-0011 需手动 upgrade | env 未导出→alembic 跑 scratch DB + assert 静默跳过 | 加 env 加载+ assert head 硬失败 | **已解决** |
| S2: deploy.sh 缺 alembic 自动升级 | 同 #1 | deploy 后断言 alembic==head | **已解决** |

---

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production | `e0c035c` |
| Main HEAD | `e0c035c` |
| Diff | **0 commits** — 完全对齐 |

---

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| Post-signoff dispatch | **否**（状态机元数据 diff） |

---

## Conclusion

**Yes — 签收 PASS。** B048-OPS1 F002 全 acceptance 通过：

- L1：119 guard tests passed
- L2：fresh deploy alembic upgrade + assert head 跑过 (0011)
- L2：无需手动 `alembic upgrade head`
- L2：所有 API 正常（/current 200, risk-panel 200, errors=0）
- L2：Production HEAD ≡ main HEAD (e0c035c)
- **B048 Finding #1 / S2：已解决**
