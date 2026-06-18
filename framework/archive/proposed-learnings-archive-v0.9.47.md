# proposed-learnings 归档 — v0.9.47（2026-06-18）

> 来源批次：B065 ashare-strategy-data-foundation（A股 策略数据地基，0 fix-round done）。Generator F001 排队 1 条 ruff CI-exact 坑，用户 B065 done 收尾批准沉淀。

---

## ruff 本地必须目录上下文 `python -m ruff check .`，勿对单文件/子集跑 check/--fix（B065 F001）

**类型：** 新坑（gate/CI — 本地门禁非 CI-exact）

`ruff` 的 isort first-party 检测依赖 project 上下文：`ruff check <单文件>`（或对子集跑 `--fix`）从 `workbench/backend` 跑时不把 `workbench_api` 识别为 first-party → 不要求 third-party(`pytest`) 与 first-party(`workbench_api`) import 组间空行；而 CI（Backend `python -m ruff check .` + Python CI 根 `ruff check .`，都是目录上下文）能识别 first-party → 要求空行 → `I001`。B065 F001 对单测单文件跑 `ruff check --fix` 反而删掉了该空行，本地单文件 "All checks passed!"，push 后 Backend CI + Python CI 双红 I001（commit `e3705a6` 修）。

**沉淀落点：** `generator.md §19.1`（§19 本地门禁 CI-exact 对 ruff 的具体落点：push 前必 `python -m ruff check .` 目录上下文，勿单文件/子集）+ `environment.md §CI 分层`（补一行）。同族于 §19（mypy CI-exact）+ environment.md（改 trade/ 须 mypy trade）。

---

**框架版本：** v0.9.46 → **v0.9.47**。活跃候选队列清空。CHANGELOG v0.9.47。
