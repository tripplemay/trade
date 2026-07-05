# Next-batch prep — bootstrap-seed deploy-chain audit (findings)

> **状态：DRAFT / 立项前审计（B086 verifying 期间安全 read-only 勘查）。** backlog `B0XX-bootstrap-seed-deploy-chain`（low, 运维治本）。
> 审计 `workbench_api/cli/bootstrap.py` 的 5 个 seed vs. 部署链（deploy 跑 **alembic only**, 非 bootstrap——故非 migration 的 seed = 生产静默缺）。

## 审计结果：**唯一真缺口 = `CURATED_SYMBOL_NAMES`**

| bootstrap seed | 部署链落地? | 结论 |
|---|---|---|
| `_import_trials`（HISTORICAL + B081–B085） | ✅ migration 0033 + 0036–0040 | deploy-safe |
| `_import_oos_cards`（B080/B082） | ✅ migration 0028 + 0037 | deploy-safe |
| `_import_symbol_names`（`CURATED_SYMBOL_NAMES`） | ❌ **bootstrap-only** | **★缺口** |
| `_import_accounts`（`accounts_path`） | N/A（`if not path.exists(): return`） | dev-only fixture, 非生产必需 |
| `_import_backlog`（`backlog_path`） | N/A（同上, 可选 JSON） | dev-only fixture, 非生产必需 |

- **★`CURATED_SYMBOL_NAMES` 缺口确认**：migration `0027_b079_symbol_name` **只 `op.create_table`（建表）不 seed 静态名**；`_import_symbol_names` 走 bootstrap
  的 `SymbolNameRepository.upsert_names(CURATED_SYMBOL_NAMES, source="curated")`。deploy 跑 alembic → 生产 curated 名 = 0（B080 F005 类）。
  **非阻断**：`source="akshare_spot"` 日刷 5203 行覆盖显示，静态 curated 只是英文 fallback。
- **accounts/backlog** 读可选 JSON（`path.exists()` 守卫）→ 本地 dev fixture，**非生产必需 seed**，无需 migration（审计确认即可, 文档化边界）。

## 批次 scope（tight, 小批 1–2 features）

- **F001 (g)**：加 data-migration（如 `0041_curated_symbol_names_seed`）**幂等 seed `CURATED_SYMBOL_NAMES`**（bulk_insert if absent, 同 trials migration 模式 0036–0040）；bootstrap 保持 lockstep；单测证幂等 + count。**不改 akshare_spot 日刷路径**（零回归）。审计文档化 accounts/backlog = dev-only（非缺口）。
- **F002 (codex)**：验证 migration 幂等落地生产 curated 名 > 0 + 与 akshare_spot override 优先级不变（curated 只作 fallback）+ 零回归。

## 复用
trials migration 模式（`0036_b081_*` … `0040_b085_*`）= 直接模板：`bulk_insert` + 幂等 id 检查 + bootstrap lockstep + `_N_` 计数单测。**scope 极小**（1 张表 1 组静态名的 idempotent seed migration）。
