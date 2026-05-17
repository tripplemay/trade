# Generator 角色指令

## 你的任务
从 features.json 中取出下一条 `executor:generator` 且 `status:pending` 的功能，实现它，测试它，提交它。

**executor:codex 的功能不属于你的职责范围，跳过不处理。**

**文档约定：**
- 实现前先读 `docs/specs/` 下对应规格文档
- **测试边界：按下表分工矩阵执行（v0.9.9 — Generator 角色测试边界矩阵化沉淀，2026-05-04）**

  | 测试类型 | 写代码 | 跑/收报告 | 备注 |
  |---|---|---|---|
  | 单元 / 集成测试（Generator 自己实现的代码）| **Generator** | Evaluator | 与实现同 commit；feature acceptance 显式列入则属 Generator 范围 |
  | E2E 流测试（跨多 feature / Playwright UI 流）| Evaluator | Evaluator | 端到端验证 |
  | 压力测试 / 性能测试 | Evaluator | Evaluator | 报告型产出，标 `executor:codex` |
  | Code review / 安全审计 | Evaluator | Evaluator | 报告型产出，标 `executor:codex` |
  | 回归测试（修 bug 时同 commit 补）| **Generator** | Evaluator | 强制 |

  **铁律：** Generator 写测试 ≠ 自评。Evaluator 跑测 + L1+L2 + 签收报告 = 评估。这与 harness 铁律 #4「不得自己评估自己代码」一致。

- 不写测试用例文档（`docs/test-cases/`）、不写 signoff 报告（由 Evaluator 负责）
- 不执行压力测试、code review、安全审计等"产出报告"类任务（由 Codex 负责）
- **`scripts/*.ts` 实装后 staging 端到端跑一次 dry-run** 见 `framework/harness/database-patterns.md §7`（mock-only 单测不抓 schema 类型不匹配类 bug，必须 prod-shaped 数据下验证）

## 执行步骤

### 1. 读取当前状态
- 打开 progress.json，确认 status 为 `building` 或 `fixing`
- 打开 features.json，**筛选 `executor:generator`（或无 executor 字段）且 status 为 `pending` 的功能**
- 找到 current_sprint 对应功能（如果为 null，取筛选后的第一条）
- 打开对应功能的 acceptance 标准
- 读取 `docs/specs/` 下的规格文档，了解实现约束
- 如果所有 pending 功能都是 `executor:codex`，说明 Generator 的工作已完成，直接推进到步骤 5

### 2. 如果是修复模式（status = "fixing"）
- 读取 progress.json 中的 evaluator_feedback
- 针对每条 FAIL / PARTIAL 的功能修复代码
- 不要改动其他无关部分

### 2.5 开工前审计 — Pre-Implementation Adjudication（2026-04-19 采纳）

**触发条件（命中任一即必须先提审计）：**

- spec 文字含糊（如 "必须使用 12 个组件" 没定义 "使用"）
- 多份参考源（设计稿 HTML / designMd / spec / Stitch 渲染）描述不一致
- 组件 API 需要决策（props 粒度 / 单组件 variant vs 拆多组件）
- 跨页变体（同功能多种布局）
- 非 token 色使用（品牌色是否扩 @theme）
- 发现原型 bug（是否回修源）
- 数据模型 gap（需要新 migration 或字段）

**审计流程：**

1. 在 `docs/specs/{batch}-{feature}-*.md` 按 `framework/harness/pre-impl-adjudication.md` §2.2 模板写审计文档
2. push 到 main，commit message 明示 "等 Planner 裁决后才开工"
3. **未收到 Planner 裁决前不实现代码**（可以写 skeleton / stub，但不提交）
4. Planner 在同文档末尾追加裁决段 + 修订相关 spec
5. git pull 看到裁决，按决议开工
6. 实现时严格按裁决执行，不自行解释

**无需审计的场景：** spec 清晰无歧义的简单 feature（如加一个 button 或修改文案），直接开工即可。**复杂度匹配 feature 风险。**

**审计被 Planner 驳回时：** Planner 裁决选了 C 方案（审计未列出）→ 按 C 实现；Planner 认为审计过度（feature 其实简单）→ 按 spec 直接开工。

完整 pattern + 模板详见 `framework/harness/pre-impl-adjudication.md`。

### 3. 实现功能
- 每次只实现一个功能（id 对应的那条）
- 实现前先思考：这个功能影响哪些文件？
- 实现后检查：acceptance 标准中的每一条是否都满足？

**设计稿页面保护规则（任何修改已有设计稿页面的批次，无论 acceptance 是否提及设计稿，均必须遵守）：**

修改 `design-draft/` 目录下有对应原型的页面时，不得改变页面的布局结构（grid 比例、区块位置、组件形态），除非 Planner 在 planning 阶段明确标注为「布局变更」。具体地：
- 不得将全宽布局改为分栏布局（或反之）
- 不得将顶部横排卡片移至侧边栏（或反之）
- 不得将 `<select>` 下拉改为 `<input>` 文本框（或反之）
- 不得自创设计稿中不存在的 UI 区块

**移除某个区块**（如清理假数据面板）是允许的，但移除后**不得用自创布局填充**，应保持剩余区块的原有位置和比例。

**UI 重构批次的额外要求（当 acceptance 中包含"设计稿还原"时，必须执行）：**

**核心原则：完全还原 HTML 代码。** 原型 HTML 中的 DOM 结构、class 名、元素类型、文本内容、图标名、数据字段语义，原样复制到 React 组件中。这是机械性的「翻译」，不是创造性的「重写」。

**唯一允许的改动：**
- 硬编码文本 → i18n 翻译函数（保持相同文案语义）
- 硬编码数据 → API 动态绑定（保持相同字段语义，如原型写 Avg Latency 就必须展示延迟）
- HTML 标签 → 对应的 React/shadcn 组件
- 静态页面 → 添加交互逻辑（onClick、useState 等）

**不允许的改动：**
- 替换指标类型（原型写 Avg Latency 就不能换成 Total Count）
- 替换图标（原型用 `more_horiz` 就不能换成 `chevron_right`）
- 删除原型中的区块（即使当前数据不支持，也要保留结构，用 "—" 占位）
- 改变按钮/链接的目标语义（原型链接到 Documentation 就不能改成链接到创建页）
- 用自己认为"更合理"的数据替换原型的字段设计

**执行流程：**

1. **Read 原型文件**：`Read design-draft/xxx/index.html`，通读完整 HTML 源码
2. **逐行翻译**：将原型 HTML 逐块转写为 React 组件，保持结构、class、图标、字段语义完全一致
3. **动态化**：将硬编码数据替换为 API 调用，保持相同的字段语义
4. **完成后逐行核对**：再次 Read 原型 HTML，逐元素确认实现与原型一致

**不读原型直接根据 acceptance 文字描述编码 = 必然 FAIL。** acceptance 是验收标准的摘要，不是实现的完整规格；原型 HTML 才是 source of truth。

### 4. 简单自测
运行项目，确认：
- 项目能启动
- 新功能按 acceptance 标准工作
- 没有破坏已有功能

### 4.5 CI 检查（每次 push 后必须执行）

每次 `git push origin main` 之后，**必须**检查 CI 运行状态：

```bash
# 等待 10 秒让 CI 启动，然后检查最新一次运行
gh run list --limit 3 --branch main
```

**判断规则：**
- 如果最新一次运行状态为 `completed / success` → 继续下一个功能
- 如果状态为 `in_progress` → 等待完成后再检查（可用 `gh run watch`）
- 如果状态为 `failure` → **立即停止新功能开发**，优先修复 CI 失败：
  1. 查看失败详情：`gh run view <run-id> --log-failed`
  2. 修复代码
  3. 提交并推送修复
  4. 再次检查 CI 直到通过
  5. 通过后才继续下一个功能

**铁律：不得在 CI 红色状态下继续开发新功能。CI 失败修复优先级高于一切。**

### 5. 更新记录
将 features.json 中该功能的 status 改为 "completed"，更新 progress.json。

**JSON 文件编码要求：** 写入 progress.json / features.json 时，必须使用标准 ASCII 双引号 `"`（U+0022），禁止使用中文弯引号 `""` `''`（U+201C/U+201D/U+2018/U+2019）。弯引号会导致 JSON 解析失败，阻塞整个状态机流转。

**building 模式：**
```json
{
  "status": "building",
  "completed_features": "N+1",
  "current_sprint": "下一条 pending 功能的 id 或 null（如全部完成）",
  "last_updated": "当前时间"
}
```

**fixing 模式（修复完成后）：**
```json
{
  "status": "reverifying",
  "fix_rounds": "N+1",
  "last_updated": "当前时间",
  "evaluator_feedback": null
}
```

### 6. 上下文检查
每完成一个功能后检查上下文使用量。如剩余不足 20%：
- 保存所有文件
- 更新 progress.json
- 告知用户「请重新启动 Claude Code 继续」，然后结束

### 7. 框架提案（可选）
实现过程中如果遇到以下情况，在 `framework/proposed-learnings.md` 末尾追加一条提案：
- 发现某个通用模式（可复用到其他项目）
- 踩到意外的技术约束或陷阱
- acceptance 标准的写法有缺陷（太模糊 / 无法验证）
- 某条铁律在实践中需要补充说明

**不得直接修改 `framework/` 其他文件**，只能追加到 `framework/proposed-learnings.md`。格式：

```markdown
## [YYYY-MM-DD] Claude CLI — 来源：F-XXX

**类型：** 新规律 / 新坑 / 模板修订 / 铁律补充

**内容：** [一句话描述，足够让用户判断是否值得沉淀]

**建议写入：** `framework/README.md` §经验教训 / `framework/harness/evaluator.md` / 其他

**状态：** 待确认
```

### 7. Handoff 说明（存在 executor:codex 功能时）
当所有 `executor:generator` 功能完成后，如果存在 `executor:codex` 的功能，在 progress.json 中写入 `generator_handoff`，说明：
- Generator 已完成哪些工具 / 脚本
- Codex 需要执行哪些 executor:codex 功能
- 已知的注意事项（脚本用法、环境变量、预期产出物路径）

## 完成标准
- **building 模式：** 所有 `executor:generator` 的功能 status 均为 "completed"（`executor:codex` 功能保持 pending，由 Codex 处理）→ 将 progress.json status 改为 "verifying"
- **fixing 模式：** 所有被标为 FAIL/PARTIAL 的 `executor:generator` 功能已修复 → 将 progress.json status 改为 "reverifying"，fix_rounds +1

---

## 8. Alpha / Beta / RC 依赖必须 ambient `.d.ts` shim 兜底

**背景：** KOLMatrix B5 fixing-1（commit f8fca4b）暴露：

- F006 引入 `@visx/wordcloud@4.0.1-alpha.0`（唯一支持 React 19 peerDeps 的版本）
- CI run typecheck 全绿（首次 npm install 时 .d.ts 正常解析）
- Reviewer 本地 typecheck FAIL：`Cannot find module '@visx/wordcloud'` + `Parameter 'd' implicitly has an 'any' type`
- 根因：alpha tag 在 npm install / npm ci 跨循环 .d.ts resolve 不稳定（不同 Node / npm 版本可能解到不同 .d.ts 文件，甚至 0 个）

**规律：** 任何 `alpha` / `beta` / `rc` / `next` / `experimental` tag 依赖**必须同时建 ambient shim**：

```typescript
// src/types/<package>.d.ts
declare module "<package>" {
  // 镜像 upstream 公共 surface
  export type BaseDatum<T = unknown> = T;
  export interface CloudWord { /* ... */ }
  export interface WordcloudProps<T> { /* ... */ }
  export const Wordcloud: <T extends BaseDatum>(props: WordcloudProps<T>) => JSX.Element;
}
```

upstream types 加载时本地 shim 是 no-op override（runtime 不动）；upstream types 漂移 / 没解到时 shim 兜底。

**Spec 起草 checklist（Planner）：** 任何引入 alpha/beta/rc tag 依赖的 spec § dependencies 段必须 explicit 列出：

- [ ] 依赖名 + 精确版本号（含 alpha tag 后缀）
- [ ] **要求 Generator 同步建 `src/types/<package>.d.ts` ambient shim**
- [ ] shim 文件路径写入 spec acceptance（验收 = shim 文件存在 + npm ci 后 typecheck 全绿）

**Generator 实战：** 显式 param type annotation 是 belt-and-suspenders 兜底，比依赖泛型推断稳：

```typescript
// 显式 type annotation（即便 generic 推断应该够，alpha .d.ts 不可信时双保险）
fontSize={(d: WordcloudDatum) => d.value}
{(cloudWords: CloudWord[]) =>
  cloudWords.map((w: CloudWord, i: number) => ...)}
```

来源：KOLMatrix B5 fixing-1（commit f8fca4b）。

---

## 9. Dev environment prerequisites — Playwright / Chromium 类前端项目

**背景：** 项目首次 boot 含 Playwright 测试链时，本机依赖缺失 + 用户级代理设置常常打架。

**WSL / Ubuntu 22.04+ 上 Playwright Chromium 必装系统库：**

```bash
sudo apt-get install -y libnss3 libnspr4 libasound2t64
# 24.04+ 是 libasound2t64；22.04 可能仍是 libasound2，按 distro 调
npx playwright install chromium
```

**用户代理 + sudo env 透传陷阱：**

很多开发本机配 `http_proxy=127.0.0.1:10808` / `https_proxy=...`（Clash / v2rayN / mihomo 类）。`sudo` 默认 sanitize 环境变量（`env_reset`），代理被剥掉 → `apt-get` 直连墙外的 ports.ubuntu.com 卡死超时。**首次安装会被误判为环境损坏。**

修复 2 选 1：

```bash
# 选项 A（推荐）：sudo -E 让 sudo 透传当前 env
sudo -E apt-get install -y libnss3 libnspr4 libasound2t64

# 选项 B：写 /etc/apt/apt.conf.d/95proxies（持久化）
echo 'Acquire::http::Proxy "http://127.0.0.1:10808";' | sudo tee /etc/apt/apt.conf.d/95proxies
echo 'Acquire::https::Proxy "http://127.0.0.1:10808";' | sudo tee -a /etc/apt/apt.conf.d/95proxies
```

**Spec / README 起草 checklist：** 任何引入 Playwright（或 Cypress / chromedriver 等带 headless Chromium 依赖）的批次，spec 必须在 prerequisites 段显式列：

- [ ] 系统库列表（含 distro 差异说明）
- [ ] sudo 代理透传提示（`sudo -E ...` 或 95proxies）
- [ ] `npx playwright install <browser>` 默认仅装 chromium（CI 配置一致）

来源：B020 F001（commit `dc0c4c6`）首次本机 boot 卡 90 分钟才发现是 sudo 剥代理。

---

## 10. GitHub Actions Node runtime forward-compat（2026-09-16 deadline）

**背景：** GHA 2026-06-02 changelog 宣布 `actions/checkout@v4` / `actions/setup-node@v4` / `actions/setup-python@v5` / `actions/cache@v4` 等 JS-based actions **默认运行时从 Node 20 切到 Node 24**。

- 2026-06-02：可通过 env var `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` 强制 Node 24（手动 opt-in，测兼容）
- 2026-09-16：完全移除 Node 20 runtime；不显式 opt-in 但仍依赖 Node 20 的 action 红屏

**Spec / workflow 起草强制要求：**

任何新增 `.github/workflows/*.yml` 必须在顶层 `env:` 块加：

```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
```

理由：

1. 6 月即可切到 Node 24，让你提前 3 个月发现兼容性问题
2. 9 月 deadline 之前所有 workflow 都走过 Node 24，零突发
3. 显式标注 = 后人 review 时知道这是有意识的版本决策

**Generator 实施 checklist：** 添加新 workflow 时 grep `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`；缺则补；CI 第一次跑就跑在 Node 24 上。

**Pre-flight `PLACEHOLDER-REPLACE-ME` grep 必须 scope 到 deployable source（v0.9.24 sub-pattern）：** 任何 deploy workflow 加 "refuse placeholder values" pre-flight 步时，grep 范围 **只能** 是实际部署到生产的源码目录（如 `workbench/`），**不能** 是整个 repo `.`。整 repo grep 会误命中文档里讨论该 check 的 spec / runbook / workflow 自身（B021 F004 第一次跑就 fail 在这上）。配合 `--exclude="*.md"` + `--exclude="*.lock"` 进一步 narrow。

```yaml
- name: Pre-flight — refuse placeholder values in <app>/ source
  run: |
    if grep --recursive --line-number --fixed-strings \
        --exclude-dir=node_modules --exclude-dir=.next \
        --exclude-dir=__pycache__ --exclude-dir=.venv \
        --exclude="*.md" --exclude="*.lock" --exclude="package-lock.json" \
        "PLACEHOLDER-REPLACE-ME" <app>/; then
      echo "::error::Refusing to deploy: PLACEHOLDER-REPLACE-ME found in deployable source." >&2
      exit 1
    fi
```

来源：B020 F002（commit `393e180`）；GHA changelog 2026-06-02；B021 F004 fix（commit `7227688`）。

---

## 11. Python 编码约定 — ruff strict mode 常见陷阱

**ruff `SIM300` (Yoda condition detection) + uppercase const + 构造函数右值：**

```python
# ❌ ruff SIM300 误判：UPPERCASE 在左 + frozenset() 调用在右 → 推断为 "constant on right"
assert ALLOWED_ENV_VARS == frozenset()

# 正确写法（任选）：
assert len(ALLOWED_ENV_VARS) == 0
assert not ALLOWED_ENV_VARS
assert ALLOWED_ENV_VARS == frozenset[str]()  # PEP 585 typed constructor 不算 Yoda
```

ruff 的 SIM300 把"右侧是 callable（`frozenset()` / `set()` / `dict()`）"判为 constant，提示反着写。但常量在左本来就是符合阅读习惯（"check X equals empty"）。改用 `len(...) == 0` / `not ...` 更稳健。

**Generator 实战习惯：** 凡是 strict ruff（含 SIM 规则集）的项目，对集合/字典 emptiness 断言一律用 `len(...) == 0` 或 truthiness `not ...`，不写 `X == Collection()`。

来源：B020 F003（commit `6184a1b`）`test_settings_env_allowlist.py`。

---

## 12. systemd + Linux infra 部署 gotchas（v0.9.24 — B021 沉淀）

### 12.1 `/etc/<app>/` 目录 traversal 权限

systemd 服务以非 root 用户跑、读 `/etc/<app>/config.json` 类文件时，**目录必须 setup 给 app user 能 traverse**：

```bash
# ❌ 反例（B021 F006 fix-round 5 阻塞 1 小时）
sudo chmod 750 /etc/workbench           # owner=root, group=root
sudo install -m 644 ...                 # 文件 644 看起来谁都可读
# 结果：deploy user not in root group → 无 x bit on dir → `open()` fails
# uvicorn: "Path '/etc/workbench/uvicorn-logging.json' does not exist"
```

```bash
# ✓ 正解 2 选 1
sudo chmod 755 /etc/<app>/              # everyone 可 traverse
# OR
sudo chmod 750 /etc/<app>/              # owner=root, group=<app>; app user in <app> group
sudo chgrp <app> /etc/<app>/
```

文件级敏感数据（含 secret）单独用 chmod 640 root:<app> 控制可读性，目录可以宽。

### 12.2 systemctl restart 多 service 一行 ≠ sudoers per-service whitelist

deploy 用户的 sudoers 通常 whitelist 单 service：

```
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart workbench-backend.service
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart workbench-frontend.service
```

这种 whitelist **不匹配**一行 restart 两个 service 的命令：

```bash
# ❌ sudoers 不允（"sudo: a password is required"）
sudo /bin/systemctl restart workbench-backend.service workbench-frontend.service

# ✓ 拆成两行
sudo /bin/systemctl restart workbench-backend.service
sudo /bin/systemctl restart workbench-frontend.service
```

**Generator 规律：** deploy.sh 类脚本中 systemctl restart 多 service 必须拆成多行；或者 sudoers 写通配（不推荐，权限过宽）。

### 12.3 PrivateTmp=true + snap-confined binaries 不兼容

systemd unit `PrivateTmp=true` 给 service 独立 /tmp namespace（安全 best-practice）。但 snap-confined binaries（如 `/snap/bin/gcloud`）**看不到** systemd 私有 /tmp namespace — snap 自己的 mount namespace 与 systemd 的私有 tmpfs 冲突。

**症状：** 脚本在 /tmp 写文件后调 snap binary 处理这个文件，binary 报"file not found"或卡死。systemd 日志只见前半 + service exit code 1。

**修法 2 选 1：**
- 用 apt 装的 binary 替代 snap（推荐，§12.4 详述）
- 设 `PrivateTmp=false`（接受弱 tmpfs 隔离）

### 12.4 snap-confine 在 systemd non-root 服务里炸 → cloud CLI 走 apt 不走 snap

snap-confine（snap 沙箱 wrapper）需要 `CAP_DAC_OVERRIDE` 引导。systemd non-root service 默认通过 `NoNewPrivileges=true` 剥所有 capability，导致 snap-confine 启动 fail：

```
required permitted capability cap_dac_override not found in current capabilities
```

**症状：** `/snap/bin/<cli>` 在 systemd 跑挂，命令行手跑成功（deploy user shell 有 /etc/profile.d 注入 + 完整 capability set）。

**修法：** 同类 cloud CLI **改装 apt 版本**。systemd 默认 PATH 自动包含 `/usr/bin`，apt 装的 `/usr/bin/<cli>` 不需要 capability hack。

```bash
# 加 Google Cloud APT repo（Ubuntu 22.04 jammy）
curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
  sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt-get update -qq
sudo apt-get install -y google-cloud-cli
which gcloud  # → /usr/bin/gcloud (not /snap/bin/gcloud)
```

systemd unit 不需要 `Environment=PATH=/snap/bin:...`，让默认 PATH 选 /usr/bin/gcloud。

来源：B021 F005 fix-round 7（commit `7a50804`）。

---

## 13. Frontend SSR vs Browser context（v0.9.24 — B021 沉淀）

**触发：** B021 F006 fix-round 5 — Codex L2 reverify 失败因生产首页登录后显示 `Backend unreachable: Failed to fetch`。根因：`workbench/frontend/src/app/(protected)/page.tsx` 的 `HEALTH_URL` 默认硬编码 `http://127.0.0.1:8723/api/health`。SSR build 时这个值被 inline 进 client bundle，浏览器在用户笔记本上 fetch 127.0.0.1:8723（用户机器，不是 VM）必失败。

**规律：** Next.js / Nuxt / Remix 等同构框架中，组件代码可能在 **server 侧（SSR / build）** 也可能在 **client 侧（浏览器）** 执行，两者对 "localhost" 的语义完全不同。

| 上下文 | "localhost" 是谁 |
|---|---|
| SSR (build / Node runtime) | 跑 build 的机器（CI runner 或部署 VM） |
| Client (browser) | 用户的笔记本 |

**Generator 规约：**

1. **配置 URL 一律走 same-origin 相对路径**（`/api/health` 而非 `http://...`），让浏览器请求自动 hit 同一 host，由反代回 backend。
2. **必须跨 origin 时用 `NEXT_PUBLIC_*` env**，且 **build-time 注入**（CI workflow 的 `env:` 块或 `next build` 命令前 export）。runtime 注入到 systemd EnvironmentFile **对 client bundle 无效** — bundle 在 build 时已 freeze。
3. **加 regression test 守 build artifact**：grep `.next/static/` 不应出现 `127.0.0.1` / `localhost:` 字面串：

   ```bash
   if grep -rE 'http://(127\.0\.0\.1|localhost):' workbench/frontend/.next/static/ 2>/dev/null; then
     echo "::error::Build artifact ships localhost URLs — would fail in browser"
     exit 1
   fi
   ```

4. **Dev mode rewrite proxy** 让 `/api/*` 转发到 dev backend，使 same-origin 路径在开发也工作：

   ```javascript
   // next.config.mjs
   export default {
     async rewrites() {
       return process.env.NODE_ENV === 'development'
         ? [{ source: '/api/:path*', destination: 'http://127.0.0.1:8723/api/:path*' }]
         : [];
     },
   };
   ```

来源：B021 F006 fix-round 5（commit `4eb9c48`）`workbench/frontend/src/app/(protected)/page.tsx` + `next.config.mjs`。
