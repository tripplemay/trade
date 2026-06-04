# Proposed-learnings 归档 — v0.9.32（2026-06-04）

> B034 二例合并沉淀：**请求路径 deploy-artifact 自包含铁律**。
> 两条原候选（2026-06-01 B034 F003 + 2026-06-04 B034 F004 L2）经用户在 B034 done 阶段确认合并沉淀。
> 正式落地见 `framework/harness/generator.md` §12.10 + `framework/harness/evaluator.md` §23 + `framework/templates/signoff-report.md` §L2 勾选行 + `framework/CHANGELOG.md` v0.9.32。

---

## 二例合并评估

| 维度 | 二例 (1) B034 F003 | 二例 (2) B034 F004 L2 |
|---|---|---|
| 泄漏点 | 请求路径 import-time：`import scripts.universe_us_quality`（pandas）| 请求路径 runtime：`open(repo-root/data/fixtures/.../universe.csv)` |
| 暴露环境 | frontend-CI 精简后端（不含根级 scripts/ + pandas）→ 500 | production VM（deploy artifact = 仅 workbench_api/）→ 500 FileNotFoundError |
| 唯一捕手 | Playwright e2e 真后端栈 | L2 真 VM authenticated 请求 |
| 同根 | **是** —— 请求路径依赖 deploy artifact 之外（repo-root scripts/ + data/fixtures/）的资源；本地 + CI 因完整 checkout 系统性掩盖 | |
| 修复模式 | stdlib-csv `ticker_match.equity_universe_tickers()` 替代 + AST 守门 `test_news_sleeve_tickers.py` | materialise universe 入 workbench_api/ 包内代码常量（commit `ec02894`）|

满足"等二例再合并"原则（参 v0.9.30 §12.9 B027+B029 / v0.9.20 BL-060）。与 v0.9.31 hold 的「B031 第三方 API spec invented endpoint live-validate」候选是**不同模式**（后者关于第三方 API envelope，仍单例 hold 等二例）。

---

## 原候选全文（闭环存档）

### [2026-06-01] Claude CLI — 来源：B034 F003 fix-round（Frontend CI Playwright 抓到 /api/recommendations/news 500）

**类型：** 新规律 / 新坑

**内容：** 请求路径（routes / services / 被其调用的 workbench_api 模块）严禁在 import 时或调用时 import `pandas` / 根级 `scripts` 包——这些是 CLI / 离线脚本依赖，精简生产 & frontend-CI 后端 install 不携带，导致请求 500。本地 dev 全装故 vitest（mock fetch）与本地手测均抓不到；**唯有 Playwright e2e 跑真后端栈才暴露这类 import-time 依赖泄漏**。B034 F003：`sleeve_tickers` 请求路径 import `scripts.universe_us_quality`（pandas）→ frontend-CI 500；改由 stdlib-csv 的 `ticker_match.equity_universe_tickers()` 解析同一真源修复，并加 AST 守门测试（`test_news_sleeve_tickers.py`）禁止该模块 import pandas/scripts。与 §12.8（runtime vs dev dep pinned，scan workbench_api/）互补——§12.8 抓 workbench_api/ 内 top-level 第三方 import，但抓不到「请求路径 import 根级 scripts 包（其内部再 import pandas）」这一层。

**建议写入：** `framework/harness/generator.md` §12.8 扩展子节「请求路径禁 import CLI-only 重依赖（pandas/scripts）；AST 守门 + e2e 真后端验证」+ §13/§18 e2e 价值补一句「真后端 e2e 是 import-time 依赖泄漏的唯一捕手」。可与既有「local vs prod」系列教训（§12.5/§12.7/§12.8/§12.9）并列。

**状态：** 已沉淀 v0.9.32（generator.md §12.10）

### [2026-06-04] Claude CLI — 来源：B034 F004 L2 blocker（production /api/recommendations/news 500 FileNotFoundError）

**类型：** 新规律（与 2026-06-01 候选合并 — 二例已凑齐）

**内容：** 请求路径（routes/services 及其调用链）**禁触 deploy artifact 之外的任何资源**——deploy 只下发 `workbench_api/` 包（含包内 `workbench_api/data/fixtures/*` 数据，如 B029 ticker_cik_map.json），repo-root 的 `scripts/` 与 `data/fixtures/` **均不在 release tree**。两类泄漏同根：(1) 2026-06-01 B034 F003：请求路径 `import scripts.universe_us_quality`（pandas）→ frontend-CI 精简后端 500；(2) 2026-06-04 B034 F004 L2：请求路径 `ticker_match._load_universe_names()` 运行时 `open(repo-root/data/fixtures/.../universe.csv)` → production VM 500 FileNotFoundError。两次本地 + CI（lint/vitest/pytest）全绿，因 checkout 含完整 repo；**唯 L2 真 VM（deploy artifact = 仅 workbench_api/）暴露**。修复模式统一：把所需数据 materialise 成 `workbench_api/` 内代码常量或包内数据文件 + CI drift/缺失守门测试（monkeypatch 资源缺失断言仍工作 = 精确复现 prod 失败的回归）。

**建议写入：** `framework/harness/generator.md` §12.8 扩展（或新 §"请求路径 deploy-artifact 自包含铁律"）：列「禁 import 根级 scripts / 禁读 repo-root data/fixtures / 数据须 materialise 入 workbench_api/ 包」+ 回归测试模板（monkeypatch 资源不存在）。`framework/harness/evaluator.md`：L2 必测「核心新路由真 VM authenticated 200（非仅 schema/health）」。`framework/templates/signoff-report.md` L2 段加「新增 user-facing 路由真 VM 200 验证」勾选项。

**状态：** 已沉淀 v0.9.32（generator.md §12.10 + evaluator.md §23 + signoff-report.md §L2 勾选行）

---

## 仍 hold 候选（未沉淀，等二例）

- **B031 第三方 API spec invented endpoint live-validate**（2026-05-27）：单例 hold；B033 F002 SEC EDGAR 按建议主动 live-validate 未再撞，二例未达成。复用窗口 B035 FRED + Alpha Vantage / B036。
- **B026 production-only React event edge**（2026-05-26）：单一案例 hold。
