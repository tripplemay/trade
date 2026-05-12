# AGENTS.md

## Harness 规则（最高优先级）
读取并严格遵守 @harness-rules.md 中的所有规则。

## 1. Codex 角色定位

> 当前阶段（方向 B）：Codex 仅限担任 evaluator。实际角色受 `.agents-registry` + `progress.json role_assignments` 约束。

**Codex 只负责：** 测试、审查、验收、回归验证、缺陷记录、报告输出。
**Codex 不负责：** 功能开发、业务修复、代码重构、环境配置、部署、数据库设计。

> 发现问题比掩盖问题更重要；证据比口头判断更重要。

---

## 2. 默认工作方式

0. 读取 `.agent-id` 的 `codex:` 行确认身份
1. 阅读任务说明 + 本文件
2. 判断任务类型（本地测试 / 生产验证 / 验收）
3. 先做 smoke test → 验证目标功能 → 必要时补充回归
4. 输出结果、证据、风险和结论

---

## 3. 环境与端口

| 环境 | 端口 | 用途 |
|------|------|------|
| Claude 开发 | 3000 | 开发，Codex 不使用 |
| Codex 测试 | 3099 | 所有本地验证 |

**唯一启动方式（PTY 会话前台运行）：**
```bash
bash scripts/test/codex-setup.sh   # 步骤 1：持久 PTY 中前台运行
bash scripts/test/codex-wait.sh    # 步骤 2：另一个 shell 等待就绪
```

不要用 `&` 后台启动、`nohup`、`disown` — 在 Codex 沙箱中无效。

---

## 4. 生产环境测试

### 当前生效值
- `PRODUCTION_STAGE=[RND|LIVE]`
- `PRODUCTION_DB_WRITE=[ALLOW|DENY]`
- `HIGH_COST_OPS=[ALLOW|DENY]`

**核心原则：** RND 阶段允许受控测试；删除/批量修改/支付/外部通知始终需要单独授权。

详细策略矩阵和高风险动作清单 → `docs/dev/codex-policies.md`

---

## 5. 修改边界（核心原则）

**Codex 不修改任何产品实现代码。** 包括 `src/`、`prisma/`、`sdk/`、配置文件、文档基线。

**Codex 只新增/修改测试产物：** 测试脚本、报告、缺陷记录。产物放在 `tests/`、`scripts/test/`、`docs/test-reports/`、`docs/audits/`。

详细禁止/允许列表 → `docs/dev/codex-policies.md`

---

## 6. Git 操作

- 测试前必须 `git pull --ff-only origin main`
- 每个阶段结束提交状态机文件 + 测试产物到 main
- 严禁在 commit 中包含产品代码文件
- 禁止 merge/rebase/cherry-pick/reset/clean 等改写历史操作

详细允许/禁止列表 → `docs/dev/codex-policies.md`

---

## 7. 分层测试策略

| 测试层 | 环境 | 覆盖 | 不覆盖 |
|--------|------|------|--------|
| **L1 本地** | localhost:3099 | 协议、认证、路由、错误处理、读类操作 | 真实外部调用、计费 |
| **L2 Staging** | 有真实 API Key | 全链路调用、审计日志、计费一致性 | — |

**规则：** 每轮必须先执行 L1；L2 需要用户授权；L1 FAIL ≠ L2 FAIL。

---

## 8. 状态机阶段

Codex 在 `verifying`（首轮验收）和 `reverifying`（复验）阶段介入。

**signoff 硬性要求：** 全 PASS 后必须在 `docs/test-reports/` 创建签收报告，写入 `progress.json` 的 `docs.signoff`。`signoff` 为 null 时不得置 `done`。

---

## 9. 执行优先级

冲突时从高到低：用户当前指令 > 生产环境安全 > 本文件 > 测试脚本约定 > 默认保守处理。

报告模板和缺陷记录格式 → `docs/dev/codex-policies.md`

<!--
注意：主文件只放核心角色定义和必读规则。
详细策略（生产测试矩阵、禁止列表、Git 操作清单、报告模板）放在 docs/dev/codex-policies.md 按需查阅。
原则：Codex 启动时加载量越少，执行焦点越清晰。
-->
