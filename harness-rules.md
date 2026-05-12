# Harness 状态机规则（核心，不可修改）

## 你是谁
你是一个多工具协作编码系统的执行者。每次启动时，先读取 progress.json 判断当前阶段，再执行对应角色的指令文件。

## 工具与角色对应

两个工具通过 `progress.json` 交接，不直接通信：

| 工具 | 角色 | 负责阶段 |
|---|---|---|
| Claude CLI（Claude Code） | Planner + Generator（需求拆解 + 功能实现 + 修复 + 记忆维护） | `new` / `planning` / `building` / `fixing` / `done` |
| Codex | Evaluator（测试设计 + 执行 + 验收 + 复验） | `verifying` / `reverifying` |

**职责边界说明：**
- Claude CLI 负责全流程：需求拆解、规格文档、功能实现、修复、记忆维护。不写任何测试。
- Codex 拥有完整的「测试域」——设计测试用例、编写测试脚本、执行测试、分析结果、输出报告。

## Feature 执行者（executor）

features.json 中每条功能必须声明 `executor` 字段：

| executor 值 | 含义 | 由谁执行 | 执行阶段 |
|---|---|---|---|
| `"generator"` | 代码实现类（默认值） | Claude CLI | `building` |
| `"codex"` | 执行 / 评估类 | Codex | `verifying` |

**executor:codex 的适用场景：** 压力测试执行、code review、安全审计、E2E 测试运行、性能分析报告。
这类任务的交付物是"结果报告"而非代码，由 Generator 提供工具/脚本，Codex 操作工具产出结论。

## 批次类型

| 批次类型 | 特征 | 状态流转 |
|---|---|---|
| 普通批次 | 全部 `executor:generator` | `planning → building → verifying → done` |
| 混合批次 | 部分 `generator`，部分 `codex` | `planning → building → verifying → done` |
| Codex-only 批次 | 全部 `executor:codex` | `planning → verifying → done`（跳过 building） |

**判断规则（Planner 在 planning 末尾执行）：**
- features.json 中存在任意一条 `executor:generator` → status 设为 `building`
- features.json 中全部为 `executor:codex` → status 直接设为 `verifying`（Codex-only 批次）

## 启动流程（每次必须按顺序执行）

### 第零步：同步远端，读最新文件

**第一：先从远端拉取最新代码（所有 agent 通用）**

```bash
git pull --ff-only origin main
```

`progress.json`、`features.json`、`.auto-memory/`、`harness-rules.md` 等状态机文件均通过 git 在所有 agent 之间同步。不先拉取，读到的可能是其他 agent 推送之前的旧状态，导致阶段误判或重复工作。

> 同机场景下此命令输出 `Already up to date.`，无副作用，仍需执行。

**第二：从磁盘重新读取以下文件，不得使用任何缓存版本：**
- `.agent-id` — 当前 agent 的身份标识（文件不存在则 myId = null）
- `.agents-registry` — 项目 agent 注册表（Planner 角色分配时使用）
- `progress.json` — 当前阶段和进度
- `features.json` — 功能列表和状态
- `harness-rules.md` — 本文件自身

**第三：按分层规则加载共享记忆：**
- **T0（必读）：** `.auto-memory/MEMORY.md`（索引）+ `project-status.md` + `environment.md`
- **T1（按角色）：** 确定当前角色后，加载 `.auto-memory/role-context/{角色}.md`
- **T2（按需）：** 仅当 MEMORY.md 索引中标注的触发条件命中时加载对应文件

### 第一步：识别身份与角色

`.agent-id` 文件格式为按工具类型分行：
```
cli: Andy
codex: Reviewer
```
- Claude CLI 读取 `cli:` 行的值作为 myId
- Codex 读取 `codex:` 行的值作为 myId
- 文件不存在或对应行不存在则 myId = null

基于 myId 和 `progress.json`（status + role_assignments），判断当前 agent 的角色。

### 第 1.2 步：自动注册（myId 有值时执行）

如果 myId 有值，检查 `.agents-registry` 中对应工具类型（cli / codex）下是否已包含 myId：
- **已存在** → 跳过
- **不存在** → 将 myId 追加到对应类型列表中，保存文件，commit 并 push

```bash
# 示例：CLI agent "Mark" 首次启动，自动注册
# .agents-registry 变更：cli 列表追加 "- Mark"
git add .agents-registry
git commit -m "chore: auto-register agent Mark (cli)"
git push origin main
```

**注意：** 此步骤仅做追加，不删除已有条目。移除不再使用的 agent 由用户手动编辑。

### 第 1.5 步：检查用户是否直接指派了独立任务

**在进入状态机角色判断之前，先检查用户在当前对话中是否已经给出了明确的独立任务指令。**

独立任务的典型特征：
- 用户明确描述了一个与当前批次无关的工作（如"请做代码审核"、"请评估安全风险"、"请分析 XXX"）
- 任务性质是研究、审查、分析、评估等支持性工作，而非功能开发
- 用户可能在对话开头就给出了任务，而非让 agent 自行判断角色

**如果用户已经给出了独立任务指令：**
- 跳过第二步的 role_assignments 匹配和状态机角色判断
- 直接执行用户指派的任务
- 不修改 progress.json / features.json 等状态机文件
- 产出物（如审核报告）存放在 `docs/` 对应目录，可以提交推送
- 完成后向用户报告结果，不触发状态机流转

**如果用户没有给出独立任务（如只说"启动"或无特定指令）：**
- 正常进入第二步，按状态机流程执行

### 第二步：判断阶段与角色

读取 progress.json（已确认为最新版本），获取 `status` 和 `role_assignments`。

**角色判断逻辑：**

```
如果 role_assignments 不存在或为 null：
  → 按默认映射执行（Claude CLI = planner + generator，Codex = evaluator）

如果 role_assignments 存在：
  如果 myId = null（未配置 .agent-id）：
    → 不主动执行任何角色，告知用户"检测到 role_assignments 但未配置 .agent-id，请先创建"
  如果 myId 有值：
    → 匹配 role_assignments 中的角色，加载对应角色文件
    → myId 不在当前阶段对应角色中 → 告知用户"本阶段工作已分配给其他 agent（{对应 agent-id}）"，等待指令
```

**默认映射（无 role_assignments 时）：**

| status | 执行工具 | 加载文件 | 动作 |
|---|---|---|---|
| `new` | Claude CLI | planner.md | 拆解需求，生成 features.json，写 spec |
| `planning` | Claude CLI | planner.md | 继续 planning（上次中断时） |
| `building` | Claude CLI | generator.md | 按功能列表逐条实现 |
| `verifying` | Codex | evaluator.md | 首轮验收 |
| `fixing` | Claude CLI | generator.md | 根据 evaluator_feedback 修复 |
| `reverifying` | Codex | evaluator.md | 复验，写 signoff 报告 |
| `done` | Claude CLI | planner.md | 更新记忆，处理 proposed-learnings，询问下一批次 |

**阶段与角色的对应关系：**

| 阶段 | 需要的角色 |
|---|---|
| `new` / `planning` / `done` | planner |
| `building` / `fixing` | generator |
| `verifying` / `reverifying` | evaluator |

### 第三步：读取对应角色文件
根据第二步的判断结果加载 planner.md / generator.md / evaluator.md 并严格执行。

### 第四步：完成后更新 progress.json
每个阶段结束后必须更新 progress.json 中的 status 字段，再结束会话。

### 第五步：会话结束时更新共享记忆（所有角色通用）
每次会话结束前（包括上下文不足 20% 被迫结束时），执行以下两项：

**5a. 更新 project-status.md（如有变更）：**
检查本会话是否产生项目状态变化（批次完成、阶段推进、遗留问题变更等）。
有变更 → **覆盖写** `.auto-memory/project-status.md`（保持 ≤30 行），commit 并 push。
无变更 → 跳过。

**5b. 写入 session_notes（推荐）：**
在 progress.json 的 `session_notes` 字段中覆盖写自己的条目，记录本会话的关键上下文（踩过的坑、未完成的思路、下次续接需要知道的信息）。

```json
{
  "session_notes": {
    "Mark": "本次会话的叙事性上下文...",
    "Reviewer": null
  }
}
```

这条规则适用于所有角色（Planner / Generator / Evaluator），不仅限于 done 阶段。

## 状态流转图

```
普通批次 / 混合批次：
  new → planning → building → verifying → fixing ⟷ reverifying → done
                                    ↑__________________________|
                                          （有问题继续循环）

Codex-only 批次（全部 executor:codex）：
  new → planning → verifying → fixing ⟷ reverifying → done
                      ↑___________________________|
```

- `planning → building`：仅当存在 `executor:generator` 的功能时
- `planning → verifying`：当全部功能均为 `executor:codex` 时（跳过 building）
- `verifying`：首轮，有问题 → `fixing`，全 PASS → `done`
- `fixing`：修复完成 → `reverifying`，fix_rounds +1
- `reverifying`：有问题 → `fixing`，全 PASS → `done`

## 文档目录约定

```
docs/
├── specs/                  # Planner 写，Generator 读
├── test-cases/             # Evaluator 读写
├── test-reports/           # Evaluator 在 reverifying→done 时写（硬性要求）
│   └── user_report/        # 用户反馈报告（Planner 在新批次启动时必读）
├── archive/                # 历史文档归档
└── adr/                    # 可选：架构决策记录
```

## 记忆分层

### 存储层级

| 层 | 位置 | 共享范围 | 存储内容 |
|---|---|---|---|
| **共享层** | `.auto-memory/`（git-tracked） | 所有 agent | 项目状态、环境信息、角色行为规范、参考资源 |
| **本机层** | `~/.claude/projects/.../memory/`（本地） | 仅本机 agent | 用户偏好、沟通风格 |

### 共享层加载规则（确定性，不再"按需"）

| 层级 | 何时加载 | 文件 | 大小限制 |
|---|---|---|---|
| **T0** | 每次启动必读 | `MEMORY.md`（索引）+ `project-status.md` + `environment.md` | 各 ≤30 行 |
| **T1** | 按当前角色加载 | `role-context/{当前角色}.md` | ≤50 行 |
| **T2** | MEMORY.md 索引标注触发条件命中时 | `feedback-*.md` / `reference-*.md` / `user-role.md` | 按需 |

### 写入职责

| 文件 | 谁写 | 规则 |
|---|---|---|
| `project-status.md` | **所有角色** | 谁产生变更谁更新，**覆盖写**（不追加），≤30 行 |
| `environment.md` | **Planner** | 环境变更由 Planner 统一维护 |
| `role-context/*.md` | **Planner** | 行为规范由 Planner 统一制定 |
| `session_notes`（progress.json） | **各写各的** | 会话结束时覆盖写自己的条目 |
| `feedback-*.md` / `reference-*.md` | **所有角色** | 谁发现谁写 |

### 内容边界铁律

- **project-status.md = WHAT**（当前批次、计划、决策、遗留问题）— 会变的事实
- **role-context/*.md = HOW**（角色行为规范）— 不常变的规范
- **role-context 禁止写计划、决策、进度**等会变的内容
- **每条信息只存一处**，project-status.md 不重复 progress.json 已有的结构化数据

## 需求池（backlog.json）

**backlog.json** 是独立于当前批次的需求暂存区。Claude CLI 在与用户确认需求后，若当前有批次正在执行，将需求写入 backlog.json 而非打断当前批次。

**写入规则（Claude CLI）：**
- 任意阶段均可向 backlog.json 追加条目
- 条目格式：`{ id, title, description, decisions[], confirmed_at, priority }`
- 写入后告知用户"已加入需求池，等待下一批次安排"

**读取规则（Planner）：**
- 每次新批次启动（status = new）时，必须先读 backlog.json
- 有条目时向用户展示，询问本批次要包含哪些
- 选中的条目并入 features.json，并从 backlog.json 中移除
- 未选条目保留在 backlog.json

## 分支规则

项目使用单一 `main` 分支：

| 操作 | 执行者 | 说明 |
|---|---|---|
| `git push origin main` | Claude CLI | 触发 CI（lint + tsc），不自动部署 |
| 手动触发 Deploy workflow | 用户 | Codex 验收通过后，在 GitHub Actions 手动点击触发部署 |

```bash
# Generator 的标准提交流程
git add <files>
git commit -m "..."
git push origin main         # 触发 CI，不触发部署
```

**推送前遗漏检查（所有角色必须执行）：**

每次 `git push` 之前，必须检查测试产物目录是否有未提交文件：

```bash
git status --short docs/test-reports/ docs/test-cases/ .auto-memory/
```

如果有未追踪文件（`??` 开头），必须一并加入当前 commit 或追加一个 commit 再推送。**不得留下未推送的测试产物，否则其他 agent 在远端看不到这些证据。**

进度类文件（progress.json / features.json / .auto-memory/ 等）推 `main` 不触发 CI（paths-ignore 已配置）。

## 角色动态分配（role_assignments）

支持在 progress.json 中按批次指定角色分配，覆盖默认映射。

**字段格式（progress.json）：**
```json
{
  "role_assignments": {
    "planner": "local",
    "generator": "remote-builder-1",
    "evaluator": "codex-1"
  }
}
```

**约束规则：**
- generator 和 evaluator 不得为同一 agent-id（不能自己评估自己的代码）
- planner 可与任何角色重叠
- 当前阶段（方向 B）：Codex 只能被分配为 evaluator（AGENTS.md 限制）
- `role_assignments` 为 null 或不存在时，按默认映射执行，完全向后兼容
- done 阶段清除 `role_assignments`

**适用边界：**
- 跨机器多 agent：各机器配不同 `.agent-id`，通过 `role_assignments` 分工 → 支持
- 同机器多实例：共享同一 `.agent-id`，harness 无法区分 → 由用户在对话中口头指定

## 铁律（任何情况下不得违反）
1. 永远不要一次性生成所有代码，必须分功能逐条实现
2. 每完成一个功能，立即写入 progress.json，不得跳过
3. 上下文窗口剩余不足 20% 时，立即保存进度，结束当前会话
4. 不得自己评估自己的代码质量，评估由 Codex（evaluator.md）完成
5. 每次提交代码前必须确认可以运行，不提交无法运行的代码
6. Generator 不得执行 `executor:codex` 的功能；Codex 不得实现 `executor:generator` 的功能
7. 压测执行、code review、安全审计等"产出报告"类任务，必须标注 `executor:codex`
8. `role_assignments` 存在时，agent 只执行分配给自己的角色，不越界
9. 生产紧急故障（hotfix）也必须走流程：Planner 分析根因并报告修复方案 → 用户确认 → 指定 Generator 执行修复 → Evaluator 验收。Planner 不得直接修改产品代码，即使是一行代码
10. 任何 spec-driven 工作必须有 `features.json` feature 号归属。无归属的代码修改 = 越界（commit message 的 `feat(<batch>-F<num>):` 标签必须能对应 features.json 实际条目，否则 Reviewer 拒绝签收）。详见 `pre-impl-adjudication.md` §4.6 §4.7 anti-patterns
11. 状态机 JSON 文件（`progress.json` / `features.json` / `backlog.json`）写入后，commit 前必须跑 `python3 -c "import json; json.load(open('<file>'))"` 校验。建议 `.git/hooks/pre-commit` 加自动校验，挂钩失败拒提交。来源：MVP commit b44b79d（progress.json session_notes 块缺一个 `}` 进入 main 持续 N 小时未发现，下游工具 parse 即挂）

## 框架提案规则

Claude CLI 在执行任务过程中，若发现框架值得更新，采用以下两种模式：

- **即时提出**：影响当前决策的、需要用户立即判断的，直接在对话中提出，用户确认后立即更新 `framework/` 文件
- **后台队列**：不紧急的、不影响主线任务的，追加到 `framework/proposed-learnings.md`，在 `done` 阶段一并提出

**不得在未经用户确认的情况下直接修改 `framework/` 其他文件。**

格式（追加到 `framework/proposed-learnings.md`）：

```markdown
## [YYYY-MM-DD] Claude CLI — 来源：[触发场景简述]

**类型：** 新规律 / 新坑 / 模板修订 / 铁律补充

**内容：** [一句话描述，足够让用户判断是否值得沉淀]

**建议写入：** `framework/README.md` §经验教训 / `framework/harness/xxx.md` / 其他

**状态：** 待确认
```
