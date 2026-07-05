# B087 F001 — CURATED_SYMBOL_NAMES 幂等 seed migration（治本 B080 F005, done）

> **治本对象**：B080 F005 — bootstrap-only seed 不入 alembic 部署链 → 生产 curated 显示名 = 0（US 名如 AAPL 显原始 ticker，
> akshare_spot A股 刷不覆盖）。审计（docs/research/next-batch-prep-bootstrap-seed-audit.md）确认这是唯一真缺口。

## 实现：migration `0041_curated_symbol_names_seed`

- 幂等 seed 68 条 `CURATED_SYMBOL_NAMES`（`{symbol: name}`）入 `symbol_name`，`source="curated"`，固定 stamp（无 Date.now，防 replay 漂移）。
- **★insert-if-absent**：仅对 `symbol_name` 表中不存在的 symbol 插入 → **永不覆盖 akshare_spot override**（curated=fallback，akshare_spot=优先）。
- 复用 trials migration 0036–0040 模板（`bulk_insert` + 幂等存在性检查）。**bootstrap 已 lockstep**（`_import_symbol_names` 本地 seed 同名，无需改）。
- deploy 跑 alembic → 本 migration 让 curated 名**真正落地生产**（治本 production=0）。

## 测试 `tests/unit/test_b087_curated_symbol_names_seed.py`

1. `test_alembic_head_seeds_all_curated_names`：upgrade head → 68 条 curated 全落地（`== CURATED_SYMBOL_NAMES`），AAPL→"Apple Inc."，source 全 curated。
2. `test_migration_insert_if_absent_preserves_akshare_override`：upgrade 到 0040 → 注入 AAPL 的 akshare_spot 名 → upgrade head（跑 0041）→ **AAPL 仍 akshare_spot 名（未被覆盖）** + 其余 curated 落地 + 总数无重复。

## 验收：**done**
- 2 单测 pass + mypy 527 clean + ruff clean。
- **bootstrap + symbol 测 50 passed 零回归**（migration + bootstrap 双 seed 无冲突）。
- migration **upgrade→downgrade→upgrade 可逆 + 幂等**。
- 零回归：不改 akshare_spot 日刷/upsert 优先级（curated 仅 fallback）。
