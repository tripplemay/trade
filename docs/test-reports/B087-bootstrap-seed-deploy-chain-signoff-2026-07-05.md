# B087 — bootstrap-seed deploy-chain 治本（CURATED_SYMBOL_NAMES 幂等 seed migration）Evaluator Signoff（2026-07-05）

> **裁定：全 PASS 2/2 → done。** F001（migration `0041_curated_symbol_names_seed` 幂等 seed + 2 单测，generator）+ F002（本独立验收，codex）。
> Evaluator 独立执行（代 Codex；授权 = 用户 /goal + B079–B086 先例），与实现完全隔离，最高怀疑度。
> insert-if-absent「不覆盖 akshare_spot」语义经 **mutation-check（注入 overwrite 看测试是否 FAIL）** 证实有牙 + **生产 VM 真机只读实测**逐点核验。
> **生产 release = `e1b0a03b0600f6ec21917d0ad189553bf128ad5e`**（`/srv/workbench/current` symlink 逐字符相等，F001 feat 提交，含 migration 0041）。其后 `d943133`（mark-done）仅改 `progress.json` + `features.json`（paths-ignore，非产品码）→ **生产产品码 ≡ HEAD 产品码**。
> 被验收提交：`e1b0a03`（migration 0041 + 2 单测 + F001 报告，共 3 文件 152 行，**零产品策略码**）。

## 0. 治本闭环（B080 F005 同源缺口的最后一块）

- **缺口根因**：deploy 链跑 `alembic upgrade head`（`workbench/deploy/scripts/deploy.sh:232`），**从不跑 bootstrap**。故 bootstrap-only 的 seed 在生产静默缺失（B080 F005 类）。审计（`docs/research/next-batch-prep-bootstrap-seed-audit.md`）确认 5 个 bootstrap seed 中**唯一真缺口 = `CURATED_SYMBOL_NAMES`**：`0027_b079_symbol_name` 只 `create_table` 不 seed → 部署后生产 curated 名 = **0**（US 名如 AAPL 只显原始 ticker）。trials/cards 已 migration-backed（0033/0036–0040 + 0028/0037），accounts/backlog = dev-only fixture（`path.exists()` 守卫，非生产必需）。
- **治本**：F001 加 data-migration 0041，走 alembic 部署链，落地生产。**闭环达成**——本批为 B080 F005 同源缺口的最后一块，其余同源 seed 均已 migration 化，与 TRIAL_BACKFILL（0033）同款「migration + bootstrap lockstep」纪律。

## 1. 验收结论表

| 验收项（features.json F002 + team-lead 追加） | 裁定 | 证据 |
|---|---|---|
| **① insert-if-absent 不覆盖 akshare_spot override（spec 点名最大陷阱）** | **PASS** | `upgrade()`（0041 line 46-55）先 `SELECT symbol FROM symbol_name` 取现存集合，仅对**不在集合**的 symbol `bulk_insert`（line 52 `if symbol not in existing`）→ 结构上永不覆盖既有行。**生产实测**：4 个 mainland A-share overlap（`600519.SH 贵州茅台` / `000858.SZ 五 粮 液` / `300750.SZ 宁德时代` / `601318.SH 中国平安`）在 curated dict 中也有英文名，但生产表中**全部保留 `source=akshare_spot` 中文名**（未被 curated 覆盖）；HK（akshare 不覆盖）如 `0700.HK Tencent` / `9988.HK Alibaba (HK)` 取 `curated`。优先级 akshare_spot > curated 不变 |
| **① 有牙（mutation-check）** | **PASS** | 将 `upgrade()` 变异为 `INSERT OR REPLACE`（覆盖既有行）→ `test_migration_insert_if_absent_preserves_akshare_override` **FAIL**（AAPL 的 akshare_spot 行被 clobber 成 curated，断言 `("AKSHARE LIVE NAME","akshare_spot")` 破）；`test_alembic_head_seeds_all_curated_names` 仍 pass（对覆盖不敏感，符合预期）。还原后 2 passed，`git status` 空 |
| **② 幂等（重跑无重复插入）** | **PASS** | insert-if-absent：首轮后全部 curated symbol 已在表，二次 `upgrade()` 计算出 `rows=[]` → 零插入。**本地 upgrade→downgrade→upgrade 循环实测**：re-upgrade 后 curated count / total 与首轮逐位相等、无 dupes。生产 `updated_at` 全 = 固定 stamp `2026-07-05 00:00:00`（无 `Date.now()`，replay 不漂移，line 35 `_STAMP`）|
| **② 可逆（downgrade 只删 curated 不误删 spot）** | **PASS** | `downgrade()`（line 58-60）`DELETE FROM symbol_name WHERE source='curated'` —— 按 source 过滤，akshare_spot 行不受影响。**本地实测**：注入 `600519.SH` akshare_spot 行 → upgrade head → downgrade 到 0040 → curated count=0、akshare 行仍在（`贵州茅台 / akshare_spot` 原样保留）→ re-upgrade 幂等复原 |
| **③ 生产落地（VM ssh 只读）** | **PASS** | `alembic_version` = **`0041_curated_symbol_names_seed`**（head 已进）；`SELECT source,COUNT(*) FROM symbol_name GROUP BY source` = **`akshare_spot│5203` + `curated│58`**（total 5261）。curated **58 > 0**（治本 production=0 达成）；akshare_spot **5203 = B080 时代基线不减**（insert-if-absent 未动日刷行 → 零回归）。抽样 `SPY→SPDR S&P 500 ETF Trust` / `AGG→iShares Core U.S. Aggregate Bond ETF` / `AAPL→Apple Inc.` / `MSFT→Microsoft Corporation` 值全正确 |
| **③ 计数自洽（58 = 68 − 10 mainland）** | **PASS** | curated dict = 68（US 27 + ETF 15 + CN/HK 26=[10 mainland + 16 HK]）。生产 curated=58 = 68 − 10 mainland（akshare_spot 覆盖全部 10 个 A股 → insert-if-absent 精确跳过）；落地 = 27 US + 15 ETF + 16 HK = 58。**逐点闭合**，即 insert-if-absent 在生产的活证 |
| **④ bootstrap 与 migration 同源 lockstep** | **PASS** | 两者均 seed **同一** `CURATED_SYMBOL_NAMES`（单一真相源 `workbench_api/symbols/names.py`，migration line 27 与 bootstrap line 80 同 import）。migration = 生产部署路径（insert-if-absent，安全）；bootstrap = 本地 dev lockstep（`_import_symbol_names`，`test_cn_hk_curated_names_match_trade_authority` guard 守漂移）。名集同源，无需改 bootstrap（见 §3 O1 语义差软观察） |
| **⑤ 零回归（不改日刷/upsert 优先级 + 产品策略码 0 行）** | **PASS** | F001 feat 提交 `e1b0a03` diff = **仅 3 文件**（migration 60 行 + 单测 70 行 + 报告 22 行），**无任何 trade/ 或 workbench_api 产品策略码改动**；`data_refresh/cli.py` 日刷 `upsert_names(..., source="akshare_spot")` 路径字节不变；`resolve_symbol_names`（DB 优先，`{**curated, **live}`）解析优先级不变。**full backend unit suite 1531 passed / 2 skipped / 0 failed**（本地实跑 12m56s）；bootstrap+symbol+names 相关子集 176 passed；B087 单测 2 passed |
| **⑥ CI 绿 + HEAD≡prod** | **PASS** | Workbench Backend CI（8m29s，全 pytest+mypy+ruff 作为部署门禁）+ Workbench Frontend CI + Workbench Deploy **均绿**（`e1b0a03`）。Python CI 未跑属**预期**：其 `paths-ignore` 含 `workbench/**`，本批改动全在 `workbench/backend` → 合法跳过（Backend CI 已覆盖 workbench_api mypy/ruff/pytest）。`/srv/workbench/current` → `e1b0a03…`（= 最后含产品码的提交）；HEAD `d943133` 相对之仅 `progress.json`+`features.json` 差异（paths-ignore）→ 产品码等价 |

## 2. 核心不变量复核（最高怀疑度）

**最大陷阱 = migration 覆盖 akshare_spot 真名（退化）→ 已双证排除：**
1. **静态 mutation-check**：注入 overwrite（`INSERT OR REPLACE`）后 insert-if-absent 断言测试 **FAIL** → 该断言有牙，能拦截退化回归。
2. **生产动态实证**：真机表中 4 个 A股 overlap symbol 全部保留 `akshare_spot` 中文名（`贵州茅台` 等），curated 只填补 akshare 不覆盖的 US/ETF/HK 空位（58 = 68 − 10 逐点闭合）。

**幂等 + 可逆**经本地 upgrade→downgrade→upgrade 循环实测（downgrade 只删 curated、akshare 行原样存活、re-upgrade 无 dupe），固定 stamp 保 replay 不漂移。

## 3. 软观察（非阻断，供后续批参考）

- **O1 — bootstrap `upsert_names` 语义 vs migration insert-if-absent（dev-only，非阻断）**：`_import_symbol_names`（`cli/bootstrap.py:200`）用 `upsert_names`（**覆盖**既有行），而 migration 0041 用 insert-if-absent（**不覆盖**）。**新鲜 dev DB 上二者等价**（无 akshare 行时 upsert==insert）；仅当本地「先跑 akshare 刷、再跑 bootstrap」这一非典型顺序下 bootstrap 会覆盖 akshare 中文名（**dev-only，生产不受影响**——生产走 migration 路径，永不跑 bootstrap）。名集同源已满足 lockstep 硬要求；如追求语义完全对齐，可下批让 bootstrap 也采 insert-if-absent（纯洁癖，非缺陷）。
- **O2 — VM 三个 systemd 服务 failed（pre-existing，B087 作用域外）**：`workbench-data-refresh`（Tiingo 价格 + SEC EDGAR，US 基本面）/ `workbench-prices` / `workbench-canonical-backtest` 处 failed 态。均为 **B087 前既存**、与 curated seed migration 无关（akshare_spot 5203 行为历史刷入既存基线）。本批不引入、不修复此三服务 → 不影响裁定。仅记录供运维侧知悉（非本批遗留）。

## 4. 结论

**B087 bootstrap-seed deploy-chain 治本 2 features 全 PASS → done。**
migration 0041 幂等 seed `CURATED_SYMBOL_NAMES`（68 条，固定 stamp）经 alembic 部署链落地生产（`alembic head=0041`），**insert-if-absent 语义**双证不覆盖 akshare_spot override（静态 mutation-check 有牙 + 生产 4 个 A股 overlap 保 `akshare_spot` 中文名实测）；生产 `curated=58 > 0`（治本 B080 F005 production=0 缺口）、`akshare_spot=5203` 基线不减（零回归日刷）、`58 = 68 − 10 mainland` 逐点闭合；upgrade→downgrade→upgrade 循环实测幂等 + 可逆（downgrade 只删 curated 不误删 spot）；bootstrap 与 migration 同源 lockstep（单一真相源 `names.py`）；**产品策略码 0 行**（F001 diff = 3 文件 = migration + 单测 + 报告）；full backend unit suite 1531 passed / 2 skipped / 0 failed（本地实跑）+ B087 单测 2 passed；CI 全绿（Backend/Frontend/Deploy `e1b0a03`，Python CI 因 `workbench/**` paths-ignore 合法跳过）+ 生产 release ≡ HEAD 产品码。两项软观察（O1 bootstrap upsert 语义差=dev-only / O2 三 systemd 服务 failed=pre-existing 作用域外）均非阻断。

**治本闭环达成**：本批为 B080 F005 同源 seed 缺口的最后一块——curated 名从「部署后生产=0」→「migration 落地 58 条」，与 trials/cards 的 migration-backed 纪律拉平。
