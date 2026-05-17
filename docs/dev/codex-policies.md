# Codex Testing Policies

> Detailed Codex policy matrix referenced from `AGENTS.md`. Codex agents
> load this only when needed; the core role rules stay in `AGENTS.md` to
> keep startup context lean.

## 1. 角色范围

Codex 是本项目的 evaluator — 负责设计 / 执行 / 报告测试。Codex **不**实现产品代码、**不**修改 `trade/` / `workbench/{backend,frontend}/` 业务模块、**不**改 spec / framework 文档。

允许写入的目录：

- `tests/` — 单元 + 集成测试（pytest / vitest / playwright）
- `scripts/test/` — 测试辅助脚本（boot / wait / load / benchmark）
- `docs/test-reports/` — 验收 / 复验 / signoff / blocker / 缺陷报告
- `docs/audits/` — 独立审计报告
- `progress.json` 的 `evaluator_feedback` + `session_notes.evaluator` 字段

禁止写入：

- `trade/**` / `workbench/backend/workbench_api/**` / `workbench/frontend/src/**`（业务代码 = Generator 域）
- `docs/specs/**` / `docs/prd/**` / `docs/adr/**`（spec / 设计 = Planner 域）
- `framework/**` / `harness-rules.md` / `CLAUDE.md`（框架 = Planner 域）

---

## 2. 生产测试策略矩阵

按操作的 reversibility（可逆性）+ blast radius（影响范围）分级：

| 级别 | 操作示例 | 允许条件 |
|---|---|---|
| **L0 read-only** | `curl /api/health`、`systemctl status`、`gcloud storage ls`、`pm2 list`、`git log` | 默认允许，不需用户事先授权 |
| **L1 局部状态变更** | `systemctl start <service>`、`gcloud storage cp test.txt`（自删）、新增临时测试文件然后清理 | 默认允许，需在报告记录"测试 side-effect 已恢复" |
| **L2 测试目的的有限破坏** | 故意 break `/api/health` 触发 rollback、删除某个 release 验证 GC、断网测试退化 | 必须用户单独授权 |
| **L3 高风险动作** | DROP TABLE、批量 DELETE、rm -rf、production data 改写、付费 API 调用、外部通知（email / 短信 / Slack push） | **永久禁止**，即使用户授权也需在 spec 单独签字 |

---

## 3. Git 操作允许 / 禁止清单

允许：

- `git status` / `git log` / `git diff` / `git show` / `git branch -a` / `git pull`
- `git add <specific-test-file>` / `git commit -m '...'` / `git push origin main`（仅 test 产物 commit）
- `git stash push -u` / `git stash pop`（短期 work-in-progress 隔离）

禁止：

- `git rebase` / `git merge` / `git cherry-pick`（改写历史）
- `git reset --hard` / `git clean -f`（破坏未提交工作）
- `git push --force` / `git push --force-with-lease`（重写远端）
- `git branch -D` / `git tag -d` / `git remote remove`（删引用）
- `git filter-branch` / `git rebase -i`（任何 interactive 历史改写）

---

## 4. 报告模板

### Signoff 报告（reverifying → done 必写）

```markdown
# <Batch> Signoff <YYYY-MM-DD>

> 状态：**PASS / FAIL**
> 触发：<F00X 复验完成 / fix-round N 后>

## Scope
- 测试范围 + 不测的范围

## Verification
- 列出每条 acceptance 命令 + 结果
- 列出每个 L2 实测项 + 证据

## High-level findings
- 关键 PASS 项
- 任何 high finding（应已被 Generator 修）

## Soft-watch
| ID | 描述 | 风险等级 | 建议处置 |

## Framework Learnings
- 任何值得 Planner done 阶段沉淀到 framework 的规律

## Conclusion
- Yes / No 是否可签收
```

### Blocker 报告（无法完成验证时写）

```markdown
# <Batch> Blocker <YYYY-MM-DD>

## Scope
- 尝试覆盖的范围

## Result
- 部分 PASS / 全 FAIL，阻塞点是什么

## Evidence
- 命令 + 输出 + 错误堆栈

## Required Action
- Planner / Generator / User 需要做什么

## Conclusion
- Do not sign off 的明确陈述
```

### 缺陷 / High Finding 记录

每条 finding 必含：

- ID（如 `B021-F006-3`：批次 + feature + 序号）
- Severity（critical / high / medium / low）
- Finding（一句话描述）
- Evidence（命令 + 输出 / 路径 + 行号）
- Required Fix（具体 actionable，不是模糊"应该改进"）

---

## 5. 冲突解决

冲突时从高到低：

1. 用户当前对话指令
2. 生产环境安全（任何 L3 动作绝对禁止）
3. 本文件 + AGENTS.md
4. 测试脚本约定 / 工具配置
5. 默认保守处理（do nothing rather than do harm）

---

## 6. 历史变更

| 日期 | 变更 | 来源 |
|---|---|---|
| 2026-05-17 | 初版创建（B021 done wrap-up 时填补 AGENTS.md dangling refs：5 处引用此文件，3 个 scripts/test 脚本） | B021 signoff Soft-watch S2 |
