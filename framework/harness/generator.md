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

**`npm audit --omit=dev` 必须进 CI gate（v0.9.25 sub-pattern）：** 任何含 npm 依赖的项目，frontend CI 必须加 `npm audit --omit=dev --audit-level=high` step。high 及以上 severity 上游 advisory 立即 fail workflow。

```yaml
- name: npm audit (production deps only, high-severity gate)
  working-directory: workbench/frontend
  run: npm audit --omit=dev --audit-level=high
```

理由：B022 F014 fix-round 2 Codex reverify 才发现 Next.js + Playwright direct deps 各有 high severity advisory，但本地开发没看到。CI 早点 fail 让 Generator 立即升级，比 reverify 时被 Codex 截到再 fix 省一轮。

来源：B022 F014 fix-round 2 blocker #5。

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

### 12.5 deploy.sh 必须 source systemd EnvironmentFile 才跑 alembic（v0.9.25 — B022 沉淀）

**触发（B022 F014 fix-round 4 最严重 prod bug）：** SSH session 跑 alembic 的环境变量集合**不等于** systemd service 启动时加载的环境变量集合。systemd unit 通过 `EnvironmentFile=/etc/workbench/workbench.env` 显式 inject 给 backend service；但 deploy.sh 通过 SSH 调进来的 shell 没有这个文件 sourced，Settings 类回退到 `DEFAULT_DEV_DB_URL = "sqlite:///./workbench-dev.db"`，alembic 在 release 目录里建一个 scratch DB（每个 release SHA 一个），**真正的生产 DB 从未被迁移**。Runtime backend service 看到的是正确 DB URL（因为 systemd 加了 env），但 schema 来不到。结果：B022 page 写路径 hit `no such table: snapshot_meta / backlog_entry`。

**规约：** 任何 cloud deploy 脚本在跑 migration 之前必须**显式 source 生产 env file**：

```bash
ENV_FILE="${WORKBENCH_ENV_FILE:-/etc/workbench/workbench.env}"
if [[ -r "${ENV_FILE}" ]]; then
  echo "→ loading env from ${ENV_FILE} for alembic"
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
else
  echo "  warning: ${ENV_FILE} not readable; alembic will use DEFAULT_DEV_DB_URL" >&2
fi

echo "→ alembic upgrade head"
(cd "${RELEASE_DIR}/backend" && "${VENV_PYTHON}" -m alembic upgrade head)
```

`set -a` + source + `set +a` 让 env 变量只对 alembic 子进程可见，不污染父 shell。

### 12.6 deploy.sh 必须 post-alembic schema-assert（v0.9.25 — B022 沉淀）

**配套（同源 B022 F014 fix-round 4）：** 即便 12.5 修了 env source，仍可能因未来的 env file 路径 drift / WORKBENCH_DB_URL 写错而 silent fail。加 post-alembic schema assert 在 release symlink flip 之前立即捕捉。

```bash
if [[ -n "${WORKBENCH_DB_URL:-}" ]]; then
  echo "→ verifying schema (account / backlog_entry / snapshot_meta)"
  "${VENV_PYTHON}" - <<'PY'
import os, sys
from sqlalchemy import create_engine, inspect
url = os.environ["WORKBENCH_DB_URL"]
engine = create_engine(url)
present = set(inspect(engine).get_table_names())
required = {"account", "backlog_entry", "snapshot_meta"}
missing = required - present
if missing:
    print(f"  ✗ schema check FAILED: missing tables {sorted(missing)} in {url}", file=sys.stderr)
    sys.exit(1)
print(f"  ✓ schema check passed: {sorted(required)} present in {url}")
PY
fi
```

**Generator 规约：** 任何含 DB migration 的 deploy.sh 必须同时 (12.5) source env file + (12.6) post-migration schema-assert。`required` 表名集合需要随 spec 演化（B022 是 3 表，B023 / 后续可能加），acceptance 应要求 assert 列表与 alembic 当前 head 实际表名一致。

来源：B022 F014 fix-round 4（commit `8d9a948`），deploy.sh 实际改动作为 reference impl。

### 12.7 chore-only main commit 必须可手动 dispatch deploy（v0.9.27 — B025 沉淀）

**触发：** B025 F006 在 round-3 / round-4 连续两轮被 `Production HEAD ≡ main HEAD` 阻塞。根因不是产品代码漂移，而是 **fixing → reverifying → done 的状态机本身会推 chore commit**（`progress.json` / `features.json` / `.auto-memory/**` 改动），而原 deploy workflow 只接 `workflow_run: ["Workbench Frontend CI", "Workbench Backend CI"]` 链触发；状态机文件 paths-ignore 不跑这两个 CI，因此 chore commit 后 production 永远落后一个 SHA，**等价性永远不成立**。

每轮 evaluator 在 reverifying 阶段写 signoff/blocker commit 后，main 又会前进 1 个 chore commit；deploy 又落后。这是 framework race condition，不是评估失误。

**规约：**

1. **任何 cloud-deployed 批次的 deploy workflow 必须含 `workflow_dispatch` trigger**（不限于 `workflow_run`），让 Evaluator / Planner / Generator 都能手动 dispatch 一次让 production 与 HEAD 等价。Generator 在 spec 实施时若 deploy workflow 只有 `workflow_run` 触发，应在 cloud-deploy 类批次的 building 阶段主动补 `workflow_dispatch` trigger（不需新批次）。

   ```yaml
   # .github/workflows/<app>-deploy.yml
   on:
     workflow_run:
       workflows: ["App Backend CI", "App Frontend CI"]
       types: [completed]
       branches: [main]
     workflow_dispatch:           # ← 加这一条
       inputs:
         force_deploy:
           description: 'Force deploy even if no recent CI run'
           required: false
           default: 'false'
   ```

2. **Generator 推 chore commit（状态机 fixing→reverifying / reverifying→done）后**，若 batch 是 cloud-deployed，必须紧接一行：

   ```bash
   gh workflow run "<App> Deploy" -r main
   ```

   并把 workflow run 链接写入下一条 session_notes / handoff，让 Evaluator 复验时知道生产已追上。**不要假设下一个 CI run 会把 production 推到位**——状态机 chore commit 通常不触发 CI。

3. **Evaluator 复验 Production HEAD ≡ main HEAD 之前**，先 `curl /api/health.version | jq -r .version` + `git rev-parse HEAD`，若不等价且 diff 仅含状态机文件（v0.9.25 §Production/HEAD 等价性 判断规则），可直接接受；若 diff 含产品文件或 spec 文件，自行 `gh workflow run "<App> Deploy" -r main` 等绿后再签收，不必再让 Generator 起新 fix-round。

**反面案例（B025 F006 round-3 / round-4）：** round-3 commit `f45ac46`（Generator 状态机推 reverifying）→ production 仍 `afa154d` → Codex 标 reverify3-blocker。Generator round-4 commit `abaaf6e` 引入 `workflow_dispatch`（先前 `afa154d` 已上线），但 main 又前进到 `b34092d`（Codex 写 signoff 的 commit）→ 再次落后。最终 Codex 自己 dispatch deploy 让 production 追到 `abaaf6e` 才完成 Production/HEAD 等价性判定（`b34092d` 仅 signoff metadata 入 `git diff` 接受不同步）。整条 race 本可在 round-1 时就用本规则避免。

**来源：** B025-us-quality-momentum-satellite F006 round-3 / round-4 deploy drift；commits `afa154d`（workflow_dispatch 上线）+ `abaaf6e`（最终签收前 SHA）+ signoff `docs/test-reports/B025-us-quality-signoff-2026-05-25.md` §Soft-watch S2 + §Framework Learnings 新规律。

### 12.7.1 paths-trigger gap — Production HEAD drift 第二种形态（B028 微沉淀）

**背景：** §12.7 沉淀时关注的是**状态机 chore commit**（`progress.json` / `features.json` / `.auto-memory/**`）落在 CI workflow `paths-ignore` 范围外造成 production drift。**B028 F004 fix-round 1 发现第二种形态**：commit 改的是**产品代码本身**（`trade/data/loader.py` + `scripts/validate_snapshot.py`），但这些路径**不在任何 CI workflow 的 `paths:` 触发集合内**（Workbench Backend CI 只 trigger `workbench/backend/**`；Workbench Frontend CI 只 trigger `workbench/{frontend,backend}/**`），所以 `workflow_run`-triggered Workbench Deploy 没 arm，production 落后 main HEAD。

**规约（Planner 起 spec 时硬要求 spec-time pre-flight）：**

1. **Planner 起 spec 时 grep 改动文件落点**：明示 batch 涉及的所有路径（如 "本批次会动 `workbench/backend/**` + `trade/**` + `scripts/**` + `pyproject.toml`"）。
2. **若任何产品代码路径**不在任何 CI workflow `paths:` 内，**spec acceptance 必须二选一：**
   - **(a) 同 batch 内修 CI workflow `paths:` 配置**让该路径 trigger CI（结构性修复；一次修一劳永逸；记得 audit 不让 docs-only chore commit 误触）
   - **(b) Generator 推每个含该路径的 commit 后必跑 `gh workflow run "Workbench Deploy" -r main`**（dispatch 兜底；与 §12.7 状态机 chore commit 同机制）
3. **Evaluator L2 §Production/HEAD 等价性 检查时**：若 production drift 且 git diff 含**产品代码路径**（非状态机），不自动接受不同步，必须确认是否因 paths-trigger gap → 走 §12.7 dispatch 兜底 + 在 spec follow-up 加 (a) 配置修复。

**反面案例（B028 F004 fix-round 1）：**

| 现象 | 根因 | 修法 |
|---|---|---|
| Production HEAD `8338fc0` 落后 main HEAD `e730a0b`；git diff 含 `trade/data/loader.py` 产品代码改动 | F003 commit `420fa3e` 改 `trade/` + `scripts/` 两路径都不在 Workbench Backend CI / Frontend CI `paths:` 内 | Codex dispatch Workbench Deploy（run `26429877249`）兜底 + Planner done 阶段同 commit 修 workbench-backend.yml `paths:` 加 `trade/**` + `scripts/**` + `pyproject.toml` 结构性根治 |

**v0.9.27 §12.7 + §12.7.1 系列覆盖的「Production HEAD drift」全形态：**

| 形态 | 触发原因 | 防御 |
|---|---|---|
| 状态机 chore commit | `progress.json` / `features.json` / `.auto-memory/**` 改动落 `paths-ignore` 内 | §12.7：workflow_dispatch + chore commit 后 dispatch |
| **产品代码 paths-trigger gap** | `trade/**` / `scripts/**` / 顶层 `pyproject.toml` 等不在任何 CI workflow `paths:` 内 | **§12.7.1：spec-time pre-flight + 结构性修 paths 配置 / dispatch 兜底** |

**来源：** B028-real-data-backfill F004 fix-round 1；commits `420fa3e`（F003 触发 paths-trigger gap）+ `15dfb4b`（F004 blocker 记录）+ workflow run `26429877249`（dispatch deploy 兜底）+ signoff `docs/test-reports/B028-real-data-backfill-signoff-2026-05-26.md`。Codex 标"本批次无 framework learnings"，Planner 在 done 阶段重新评估为 §12.7 既有规则的延伸 sub-pattern，不 bump 版本但收紧 spec-time pre-flight 责任。

### 12.8 pyproject runtime vs dev dependency hygiene（v0.9.29 — B027 沉淀）

**触发：** B027 F002 fix-round 1 — Codex L2 production smoke 失败，根因是 `httpx` 在 `pyproject.toml` 的 `[project.optional-dependencies].dev` 而不是 `[project].dependencies`。**本地 pytest 全过**（pytest 走 dev install 含 extras），**production wheel install 缺 transport 层**（wheel install 默认只装 `[project].dependencies` 不装 extras），Tiingo adapter 启动时 ImportError。Generator round-1 commit `468d380` 把 httpx 移到 runtime + 加 safety regression test 守门。

**规律：** Python 应用引入新 third-party 依赖时，**必须区分 `[project].dependencies`（runtime 必需，wheel install 自动装）vs `[project.optional-dependencies].dev / test / docs`（仅本地 dev / CI test 用）**。判断规则：

| 依赖类型 | 判断 | 放哪 |
|---|---|---|
| 业务代码 import（`workbench_api/`、`trade/` 等 source tree）| **runtime 必需** | `[project].dependencies` |
| 测试代码 import（`tests/`）| **仅 dev** | `[project.optional-dependencies].dev` |
| 既被 source 又被 tests import | **runtime 必需**（按 source 范围判定）| `[project].dependencies` |
| Type checker / linter / formatter（mypy / ruff）| 仅 dev | `[project.optional-dependencies].dev` |
| Stub packages（`types-*`）| 仅 dev | `[project.optional-dependencies].dev` |

**规约（任何 Python 应用批次 spec 涉及新 dep 引入时）：**

1. **加新 import 前先判断 runtime / dev**：grep source tree（`workbench_api/**/*.py` / `trade/**/*.py`）是否有该 import；有 → runtime；只在 `tests/` → dev。
2. **加 safety regression test 守门** — 新建 `tests/safety/test_runtime_dependencies_pinned.py`（如不存在），walk source tree 用 `ast` 收集每个 top-level third-party import，断言 each 在 `[project].dependencies` 中（exempts stdlib + 一小 explicit transitive list 如 `pydantic_core` 等隐式依赖）。pin 关键 dep（如 httpx）确保 future 重构不能 silently undo。
3. **Spec acceptance 必含**：任何 batch spec 引入新 dep 时，acceptance 显式列出 dep 名 + runtime/dev 归类 + safety regression 测试是否需要 extend。

### 12.8.1 Safety regression test 模板

```python
# tests/safety/test_runtime_dependencies_pinned.py
"""Guard against pyproject runtime/dev dependency misclassification.

Production wheel install only carries [project].dependencies; if any source
file imports a package only listed in [project.optional-dependencies].dev,
production startup raises ImportError. This regression test walks the source
tree at CI time and asserts every top-level third-party import is declared
in [project].dependencies.

Failure mode prevented: B027 F002 fix-round 1 commit 468d380 (httpx had been
in [project.optional-dependencies].dev; production wheel install lacked it;
TiingoSnapshotLoader raised ImportError on first call).
"""
from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

# Standard library packages that source tree may import without pyproject declaration
STDLIB_MODULES = set(sys.stdlib_module_names)

# Packages that come transitively with other runtime deps (no need to declare
# explicitly in pyproject); add new entries only when you confirm transitivity.
TRANSITIVE_ALLOWLIST: set[str] = {
    "pydantic_core",  # via pydantic
    # Add as confirmed
}

# Source roots to scan (relative to repo root)
SOURCE_ROOTS = ("workbench_api", "trade")

# Critical dependencies that must always appear in [project].dependencies.
# Pin via this list to prevent silent un-promotion in future refactors.
CRITICAL_RUNTIME_DEPS: set[str] = {
    "httpx",     # B027 Tiingo adapter
    "fastapi",   # backend framework
    "uvicorn",   # ASGI server
    # Extend as batches grow
}


def _load_runtime_deps(pyproject_path: Path) -> set[str]:
    data = tomllib.loads(pyproject_path.read_text())
    deps = data["project"]["dependencies"]
    # Strip version specifiers, extras, env markers
    names = set()
    for dep in deps:
        name = dep.split(";")[0].split("[")[0]
        for op in ("==", ">=", "<=", "~=", "!=", "<", ">", " "):
            name = name.split(op)[0]
        names.add(name.strip().replace("-", "_"))
    return names


def _walk_top_level_imports(source_root: Path) -> set[str]:
    imports: set[str] = set()
    for py_file in source_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    imports.add(node.module.split(".")[0])
    return imports


def test_all_source_imports_in_runtime_dependencies():
    repo_root = Path(__file__).parents[2]
    pyproject = repo_root / "pyproject.toml"
    runtime_deps = _load_runtime_deps(pyproject)

    missing: set[str] = set()
    for root_name in SOURCE_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for imp in _walk_top_level_imports(root):
            imp_normalized = imp.replace("-", "_")
            if (
                imp_normalized in STDLIB_MODULES
                or imp_normalized in TRANSITIVE_ALLOWLIST
                or imp_normalized in runtime_deps
                or imp_normalized.startswith(SOURCE_ROOTS)  # first-party imports
            ):
                continue
            missing.add(imp_normalized)
    assert not missing, (
        f"Source imports not declared in [project].dependencies: {sorted(missing)}. "
        f"Move them from [project.optional-dependencies].dev to [project].dependencies "
        f"(see framework/harness/generator.md §12.8 for the runtime/dev judgment rules)."
    )


def test_critical_runtime_deps_pinned():
    repo_root = Path(__file__).parents[2]
    runtime_deps = _load_runtime_deps(repo_root / "pyproject.toml")
    for dep in CRITICAL_RUNTIME_DEPS:
        dep_normalized = dep.replace("-", "_")
        assert dep_normalized in runtime_deps, (
            f"Critical runtime dep {dep!r} missing from [project].dependencies. "
            f"Restore it; future refactors must not silently de-promote (B027 lesson)."
        )
```

### 12.8.2 反面案例（B027 F003 fix-round 1）

| 现象 | 根因 | 修法 |
|---|---|---|
| 本地 `pytest 273 passed`，production wheel 启动 `ImportError: No module named 'httpx'` | `httpx>=0.27` 在 `[project.optional-dependencies].dev`；production wheel install 默认不装 extras | commit `468d380` 移到 `[project].dependencies` + 加 `tests/safety/test_runtime_dependencies_pinned.py` 守门 |
| Codex L2 §7 smoke 失败（`TiingoSnapshotLoader().health_check()` 调用前就崩）| 同上 | 同上 |

**来源：** B027-real-data-snapshot-foundation F003 fix-round 1；commits `468d380`（httpx 提升到 runtime）+ Generator handoff at `49462d6` + signoff `docs/test-reports/B027-real-data-snapshot-foundation-signoff-2026-05-26.md`。

**类比 v0.9.X 系列「local vs prod」教训：**

| 版本 | 现象 | 防御 |
|---|---|---|
| v0.9.25 §12.5 | 本地 alembic OK，production deploy.sh 没 source env file → 跑 scratch DB | deploy.sh source EnvironmentFile |
| v0.9.27 §12.7 | 本地 commit push，chore-only commit 不触 CI / deploy → production HEAD drift | workflow_dispatch + chore commit 后 dispatch |
| v0.9.27 §20 (evaluator.md) | 本地 Playwright pass，production VM stale dev process 让 dismiss UI 失败 | lsof check + kill 再启 |
| **v0.9.29 §12.8（本节）** | **本地 pytest pass，production wheel install 缺 dev extras → ImportError** | **runtime vs dev 判断 + safety regression test 守门** |

---

### 12.9 production secret 三处接线铁律（v0.9.30 — B027 + B029 二例合并沉淀）

**触发：** B027 引入 `TIINGO_API_KEY` 时 + B029 引入 `SEC_EDGAR_CONTACT_EMAIL` 时**两次完全相同的踩坑**——Generator spec acceptance 写"`deploy.sh` 加 pre-flight check"和"`.env.example` 加 secret 注释"，但**漏了 `bootstrap-env.yml` workflow 同步加 secret**，结果 production VM 的 `/etc/workbench/workbench.env` 拿不到新 secret，Generator 必须 fix-round 补 commit（`dcf1463` for B027 / `ef421e9` for B029）。

满足"等二例再合并沉淀"原则（B026 React event edge 仍单一案例 hold；本节是 B027+B029 真正二例）。

**规律：** Production 上一个新 secret 完整生效需要 **3 处同步接线**（缺任何一处都让 deploy 后 secret 不可用）：

```
┌──────────────────────────────────────────────────────────────┐
│ 新 production secret 三处接线（每次新加 secret 必查 + 同 commit 完成）│
├──────────────────────────────────────────────────────────────┤
│ 1. .env.example                                              │
│    加 `<SECRET_KEY>=<placeholder>` 注释行                    │
│    说明用途 + 获取方式（如 dashboard URL）                    │
│                                                              │
│ 2. workbench/backend/workbench_api/config.py (or settings.py)│
│    加 `os.environ["<SECRET_KEY>"]` 读取 + 缺时 raise         │
│    RuntimeError 含修复指引                                   │
│                                                              │
│ 3. workbench/deploy/scripts/deploy.sh                        │
│    加 pre-flight check：                                     │
│    `if [ -z "${<SECRET_KEY>}" ]; then echo "missing"; exit 1; fi` │
│                                                              │
│ 4. .github/workflows/bootstrap-env.yml          ← B027/B029 漏的 │
│    把 GitHub Secret 写入 production VM 的                    │
│    `/etc/workbench/workbench.env`：加一行                    │
│    `<SECRET_KEY>=${{ secrets.<SECRET_KEY> }}`                │
└──────────────────────────────────────────────────────────────┘
```

**规约（Planner 起 spec acceptance 时硬要求 + Generator 实施时 checklist）：**

1. **Spec acceptance 必含**：任何引入新 production secret 的 spec acceptance（如 F00X spec §(N) 引入 `XYZ_API_KEY`）**必须同时列出 4 处接线**——明确写"`bootstrap-env.yml` 加一行 inject"，不可省略以为 deploy.sh 已 cover。
2. **Generator 实施 checklist**：写 spec implementation 时第一件事 grep `bootstrap-env.yml` 既有 secret 列表 + 加新 secret 到同位置；不要等 deploy 失败再补。
3. **Planner pre-impl 审计**：若 spec acceptance 列出 `.env.example` + `deploy.sh` pre-flight 但漏 `bootstrap-env.yml`，Planner 在裁决时主动补该项（参考 v0.9.X §pre-impl 范式）。
4. **Evaluator L2 验证**：production VM 上 `cat /etc/workbench/workbench.env | grep <SECRET_KEY>` 必含此 secret；若漏走 §12.7 dispatch 兜底 + 后续 fix-round 补 bootstrap-env.yml。

**反面案例对比表：**

| 批次 | Secret | Spec 漏 bootstrap-env.yml | Fix commit |
|---|---|---|---|
| **B027** | `TIINGO_API_KEY` | F002 acceptance 写 deploy.sh pre-flight 但没 bootstrap-env.yml | `dcf1463 fix(B027-F002): bootstrap-env.yml — include TIINGO_API_KEY in env file` + `c46bda3 chore(B027): note env-file deploy gap + operator action in handoff` |
| **B029** | `SEC_EDGAR_CONTACT_EMAIL` | F001 acceptance 写 deploy.sh pre-flight 但没 bootstrap-env.yml | `ef421e9 fix(B029-F001): wire SEC_EDGAR_CONTACT_EMAIL into bootstrap-env.yml` + `1e21e9f chore(B029): F001 production-side aligned` |

**预防价值：** 本规则保护后续任何引入 secret 的批次（B031 LLM gateway `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `COHERE_API_KEY` 至少 3 个 secret；B033 News ingest 若引入付费 RSS；Phase 4 long-tail batches）不再撞同一个坑。Generator 主动按 §12.9 checklist 走 ≈ 1 个 fix-round 节省。

**与 v0.9.X 系列 "deploy hygiene" 教训汇总：**

| 版本 | 现象 | 防御 | 哪一层 |
|---|---|---|---|
| v0.9.25 §12.5 | deploy.sh 没 source env file → alembic 跑 scratch DB | deploy.sh source EnvironmentFile | deploy script |
| v0.9.25 §12.6 | alembic 跑后 schema 不一致 | deploy.sh post-alembic schema-assert | deploy script |
| v0.9.27 §12.7 | chore-only commit 不触 CI / deploy | workflow_dispatch + chore commit 后 dispatch | deploy workflow |
| v0.9.27 §12.7.1 | 产品代码 paths-trigger gap → deploy drift | spec-time pre-flight + 结构性修 paths 配置 | deploy workflow |
| v0.9.27 §20 (evaluator.md) | production VM stale dev process | lsof check + kill 再启 | runtime process |
| v0.9.29 §12.8 | pytest pass 但 wheel install 缺 dev extras | runtime vs dev 判断 + safety regression test | packaging |
| **v0.9.30 §12.9（本节）** | **新 secret 漏 bootstrap-env.yml inject → production env 缺 secret** | **三处接线铁律 + Planner pre-impl 主动补 + Generator checklist** | **secret 注入** |

**来源：** B027 F002 fix-round 1 commits `dcf1463` + `c46bda3` + B029 F001 fix-round 1 commits `ef421e9` + `1e21e9f`；B029 done 阶段 Generator handoff 主动建议沉淀（Codex signoff 标"本批次无 framework learnings"，Planner 重新评估为 B027+B029 真二例满足合并沉淀原则）。

---

### 12.10 请求路径 deploy-artifact 自包含铁律（v0.9.32 — B034 二例合并沉淀）

**触发：** B034 News↔ticker 批次 F003 + F004 两次**同根**踩坑——请求路径（routes / services 及其调用链）依赖了 **deploy artifact 之外的资源**：

- **二例 (1) B034 F003**（commit `d1c2b30`）：请求路径 `import scripts.universe_us_quality`（内部 import pandas）→ frontend-CI 精简后端 install 不含根级 `scripts/` 包 + pandas，`/api/recommendations/news` 500。本地全装 + vitest（mock fetch）均抓不到，**唯 Playwright e2e 跑真后端栈**暴露 import-time 依赖泄漏。改由 stdlib-csv 的 `ticker_match.equity_universe_tickers()` 解析同源修复 + AST 守门测试。
- **二例 (2) B034 F004 L2**（commit `ec02894`）：请求路径 `ticker_match._load_universe_names()` 运行时 `open(repo-root/data/fixtures/.../universe.csv)` → production VM 500 FileNotFoundError。本地 + CI（lint/vitest/pytest）全绿因 checkout 含完整 repo，**唯 L2 真 VM** 暴露。改由 materialise universe 入 `workbench_api/` 包内代码常量修复。

满足"等二例再合并沉淀"原则（参 v0.9.30 §12.9 / v0.9.20 BL-060）。注意：本节与 v0.9.31 hold 的「B031 第三方 API spec invented endpoint live-validate」候选是**不同模式**——后者仍单例 hold。

**规律：** Production deploy artifact **只下发 `workbench_api/` 包**（含包内 `workbench_api/data/...` 数据，如 B029 `ticker_cik_map.json`）；repo-root 的 `scripts/` 与 `data/fixtures/` **均不在 release tree**。任何请求路径在 import 时或运行时触碰这些 repo-only 资源都会在 production 500，而本地 + CI 因完整 checkout **系统性掩盖**。

```
┌──────────────────────────────────────────────────────────────┐
│ 请求路径 deploy-artifact 自包含（新 user-facing 路由必查）        │
├──────────────────────────────────────────────────────────────┤
│ ✅ 在 release tree（请求路径可依赖）：                            │
│    workbench_api/**            （含包内 workbench_api/data/*）   │
│ ❌ 不在 release tree（请求路径严禁 import / open）：             │
│    repo-root scripts/**        （CLI / 离线脚本，含 pandas）     │
│    repo-root data/fixtures/**  （仅完整 checkout / CI 存在）     │
│ 修复模式：所需数据 materialise 成 workbench_api/ 包内            │
│           代码常量或包内数据文件 + 缺失守门回归测试             │
└──────────────────────────────────────────────────────────────┘
```

**规约：**

1. **Spec acceptance 必含**：新增 user-facing 路由的 spec acceptance 必须声明「请求路径自包含」——所需数据 materialise 入 `workbench_api/` 包，不得 import 根级 `scripts/` 或读 repo-root `data/fixtures/`。
2. **Generator 实施 checklist**：请求路径禁 `import scripts.*`、禁 `open(<repo-root>/data/...)`；数据进 `workbench_api/` 包（代码常量或包内 data 文件）。
3. **守门回归测试**：monkeypatch 资源缺失（删/改 repo-root path）断言请求路径仍工作 = 精确复现 prod deploy-artifact 缺口的回归（B034 用 AST 守门 `test_news_sleeve_tickers.py` 禁 import pandas/scripts）。
4. **Evaluator L2 验证**：必测核心新路由真 VM **authenticated 200**（非仅 schema / health）；deploy artifact = 仅 `workbench_api/`。

#### §12.10.1 扩展：自包含审计覆盖**所有生产执行路径**，不止请求路径（v0.9.34 — B038 沉淀）

**触发：** B038 Home 今日市场新闻 F003 L2 — `news/cli.py` 的 `_default_universe()` 运行时 `import scripts.universe_us_quality`（同 §12.10 二例 (1) 同根）。该缺陷**自 B033 起已存在**，但 news ingest 一直是 **manual-only CLI**（边界 (q) production-disabled），从未在 production 跑过，所以本地 + CI + 既有 L2 **全部系统性掩盖**。B038 把该 CLI 接入 `workbench-news.timer`（边界 (q)→(r) 收编）后，**首次在 production 执行 → `workbench-news.service` oneshot `ModuleNotFoundError`**。修复：复用包内 `ticker_match.equity_universe_tickers()`（值等价）+ AST 守门 `test_news_ingest_self_contained.py`（扫全 `workbench_api/` 包无 `scripts.*` import）。commit `d99c0af`。

**规律（§12.10 的 scope 扩展）：** §12.10 原表述聚焦「**请求路径**」，但 deploy-artifact 自包含铁律对**任何会在 production 真实执行的代码路径**都成立——**请求路径（routes/services）+ scheduled/timer-invoked CLI 及其 import 闭包**。一段 manual-only 的 CLI/module 看似"非请求路径、不受 §12.10 约束"，但**一旦被接入 production 运行路径（systemd timer / cron / 任何自动触发），它及其完整 import 闭包立即落入 §12.10 边界**，必须重新审计自包含性。

**规约（补 §12.10 规约 5）：**

5. **把 manual-only CLI 接入 production 自动执行路径（timer/scheduler）时，必须把该 CLI 及其 import 闭包按 §12.10 重新审计**——不能因为"它原来只 manual 跑、本地一直 OK"就豁免。Spec acceptance（如 B038 F001）+ Generator checklist + 守门测试（AST 扫该 CLI 模块无 `scripts.*` import / 不 `open(repo-root/...)`）三处都要覆盖**新接入的执行路径**，不止请求路径。Evaluator L2 必须**手动 trigger 一次该 timer 的 service** 验真（不能只看 timer enabled），观察 oneshot 是否 `ModuleNotFoundError`/`FileNotFoundError`（配 evaluator.md §24 timer 接线检查同步做）。

#### §12.10.2 enforcement 模型：当被禁包被有意打进 artifact，§12.10 从「物理缺席」转「AST 守门」（v0.9.35 — B044 沉淀）

**触发：** B044 真实评分基础——`/api/recommendations/current` 需调 `trade/` 包的 master_portfolio 真实评分，但 `trade/` 不在 deploy artifact（wheel `packages=["workbench_api"]`）。用户批架构 A：**把 `trade/` 装进 VM venv**（precompute CLI 直接 import trade/ 评分写 DB，请求路径只读 DB）。这使 `trade/` **从此物理存在于 artifact**——§12.10 原本靠「`trade/` 物理缺席 → 请求路径想 import 也 import 不到」的天然保护**失效**。

**规律：** §12.10 有两种 enforcement 模式：
- **模式 1（默认）物理缺席**：禁止的根级包/数据**不进 artifact**，请求路径物理上 import/读不到。最强，零信任。
- **模式 2（被迫）AST 守门**：当某禁包**被有意打进 artifact 供 job 使用**（如 B044 的 `trade/` 供 precompute），物理保护失效 → **必须显式 AST 守门**断言「请求路径模块（routes/services 调用链）不 import 该包；仅指定 job 模块（如 `recommendations/precompute.py`）允许」。守门成为唯一防线。

**规约（补 §12.10 规约 6）：**

6. **把一个原本 artifact 之外的包打进 artifact（供 precompute/job 用）时，必须同 commit 落 AST 守门**——`tests/safety/test_<feature>_request_self_contained.py` 断言请求路径调用链零 import 该包，仅 allowlisted job 模块允许（B044 `test_recommendations_request_self_contained.py`：routes/services/recommendations 无 `import trade`，仅 `recommendations/precompute.py` 允许）。Spec acceptance 必声明此守门；Evaluator L2 验守门跑过 + 请求路径行为不依赖该包（即使 import 误入也不会在请求时触发重依赖）。**默认仍优先模式 1**（能不打进 artifact 就不打）；仅当 job 确需该包且运维取舍倾向单机 timer（非 CI 算→ingest）时走模式 2 + 守门。

#### §12.10.3 wheel `packages=[...]` 只打包源码树——运行时读的非包数据文件必须 force-include（v0.9.39 — B034/BL-B011-S2 二例合并沉淀）

**触发：** BL-B011-S2 F004 fresh deploy — us_quality + hk_china 两个 satellite 策略的 loader 运行时读 **repo-root `data/fixtures/<strategy>/universe.csv`**，但 trade wheel 的 `packages=["trade"]` **只打包 `trade/` 源码树（含 `trade/data/fixtures/` 3 个 json），不含 repo-root `data/fixtures/`** → VM wheel 装时 loader raise → **两个 satellite 双双 stub**（data_source 卡 mixed）。**editable 本地装（repo_root=真实仓库根，fixture 在）系统性掩盖；唯 wheel-on-VM fresh deploy 暴露。** 修：pyproject `[tool.hatch.build.targets.wheel.force-include]` 把 `data/fixtures/{...}` 打进 wheel（落 `site-packages/data/fixtures/`，与 loader 的 `_REPO_ROOT/data/fixtures` 解析一致）+ 版本 bump + 守门 `test_trade_wheel_bundles_fixtures.py`（断言 force-include 配置在，防再丢）。

**规律：** `packages=[...]` / hatch wheel target **只抓包源码树**；包在**运行时 `open()` 的非包数据文件**（repo-root `data/fixtures/` / 任何包目录外的 CSV/JSON）**不会自动进 wheel**——必须 `force-include`（或 materialise 进包目录）。这是 §12.10「请求/执行路径自包含」在**打包层**的实例：editable/完整 checkout 掩盖，wheel/VM 暴露（同 §12.10 二例的 local-vs-prod 掩盖机理）。**二例（两个 wheel）：** B034 workbench_api wheel 缺 repo-root data → §12.10 原案；BL-B011-S2 trade wheel 缺 repo-root `data/fixtures/` → 本节。

**规约（补 §12.10 规约 7）：**

7. **任何把含 fixture/数据-文件-loader 的包打成 wheel 时**：① loader 读的非包数据文件 `force-include` 进 wheel（pyproject hatch `force-include`），落点与 loader 解析路径一致；② 同 commit 落守门测试（构 wheel / 模拟 site-packages 断言数据文件 resolve，如 `test_trade_wheel_bundles_fixtures.py`）；③ **优先 materialise 进包目录**（如 `trade/data/fixtures/`，随 `packages` 自动进）而非依赖 repo-root + force-include——前者更稳。Evaluator L2 fresh deploy 验该 loader 不 stub（数据 resolve）。

**与 §12.8 / §12.9 关系：** §12.8 抓 `workbench_api/` 内 top-level 第三方 import（runtime vs dev）；§12.10 抓「**生产执行路径**（请求路径 + timer/scheduled CLI）触碰 deploy artifact 之外（根级 `scripts/` + `data/fixtures/`）」这一层——互补，非重叠。

**与 v0.9.X 系列 "local vs prod" 教训补一行：**

| 版本 | 现象 | 防御 | 哪一层 |
|---|---|---|---|
| **v0.9.32 §12.10（本节）** | **请求路径 import 根级 scripts / 读 repo-root data/fixtures → prod 500（本地+CI 掩盖）** | **请求路径数据 materialise 入 workbench_api/ 包 + 缺失守门 + L2 真 VM 200** | **deploy artifact 边界** |
| **v0.9.34 §12.10.1（B038）** | **manual-only CLI 接入 timer 后首次 prod 执行 → `import scripts.*` ModuleNotFoundError（B033 起隐患，manual-only 期全程掩盖）** | **接入自动执行路径时 CLI 及 import 闭包按 §12.10 重审 + AST 守门 + L2 手动 trigger service 验真** | **deploy artifact 边界（扩到所有生产执行路径）** |
| **v0.9.35 §12.10.2（B044）** | **被禁包 `trade/` 被有意打进 venv 供 precompute → 物理缺席保护失效，请求路径理论上可 import** | **同 commit 落 AST 守门（请求路径零 import 该包，仅 job 模块 allowlist）；默认仍优先模式 1 不打进 artifact** | **enforcement 模型（物理缺席→AST 守门）** |
| **v0.9.39 §12.10.3（B034/BL-B011-S2）** | **wheel `packages=[...]` 只打源码树，包 loader 运行时读的 repo-root `data/fixtures/` 没进 wheel → VM wheel 装 loader raise → 策略 stub（editable 本地掩盖）** | **pyproject `force-include` 数据文件进 wheel（或 materialise 进包目录）+ 守门测试断言 wheel 含数据 + L2 fresh deploy 验不 stub** | **打包层（wheel force-include 非包数据）** |

**来源：** B034 F003 fix-round（commit `d1c2b30`）+ F004 fix-round 1（commit `ec02894`）；signoff `docs/test-reports/B034-news-ticker-embedding-signoff-2026-06-04.md` §Framework Learnings first-class 列入 + proposed-learnings 二例合并；B034 done 阶段用户确认沉淀。

---

## 12.11 deploy 步骤的「成功」必须 post-step assert 验证 intended end-state（v0.9.38 — B022/B045-OPS1/B048-OPS1 三例合并沉淀）

**规律：** deploy 步骤的成功**不能靠「命令返回 0」或「守门条件通过」判定**——命令可能静默 no-op，守门条件本身可能在变量空/资源缺时**静默跳过**。每个有 intended end-state 的 deploy 步骤，**必须紧跟一个 post-step ASSERT 验证那个 end-state，不等则 `::error::` + 非零退出硬失败**（不被 `--quiet` / `set -e` 之外的静默路径吞）。

**三例（均致 production 静默破坏）：**

| 实例 | deploy 步骤 | 静默失效机理 | intended end-state assert |
|---|---|---|---|
| **B022 F014**（v0.9.25 §12.6 前身）| `alembic upgrade head` | env 未加载 → 跑 `DEFAULT_DEV_DB_URL` scratch DB，prod 永不迁移 | post-alembic schema-assert（required 表存在）|
| **B045-OPS1**（v0.9.36）| `pip install --force-reinstall <wheel>` | 同版本 skip / dep 重解析失败，新模块没落 VM | deploy 后 `python -c "import <关键模块>"` smoke check |
| **B048-OPS1**（v0.9.38 本节）| `alembic upgrade head` | env 未导出 `WORKBENCH_DB_URL` → scratch DB + post-alembic schema-check 被 `if [[ -n VAR ]]` **静默跳过** | deploy 后断言 `alembic current == heads` + required 表加全 + env-url 空硬失败（堵 scratch） |

**规约：**

1. **写/改任何 deploy 步骤时，同 commit 配 post-step assert**：包安装→import 关键模块；DB 迁移→`alembic current==heads` + required 表存在；version 升级→`pip show`/version 匹配；env 依赖→变量非空否则硬失败（不静默跳过）。
2. **守门条件（`if [[ -n VAR ]]` / `if [[ -f X ]]`）不得在「应该有但没有」时静默跳过关键步骤**——该情形是 error 不是 skip：变量空/文件缺 → `::error::` + exit，而非默默不做。
3. **assert 用 INTENDED end-state，不是 step 退出码**：B048-OPS1 的 alembic 步骤退出码 0，但跑的是 scratch DB——只有断言 prod DB 的 revision/表才暴露。
4. Evaluator L2 验 deploy log 含这些 assert 且跑过；fresh deploy（非手动补救）后 end-state 达成。

**与 v0.9.36 关系：** v0.9.36 README §「venv 多包安装」是本规则在「包安装」步骤的具体实例；本节是跨所有 deploy 步骤的泛化（alembic / install / version / env 通用）。

**来源：** B048-OPS1 F001/F002（commit `e0c035c`，deploy.sh env-url 硬失败 + alembic==head 断言 + required 表扩）+ signoff `docs/test-reports/B048-OPS1-alembic-deploy-reliability-signoff-2026-06-08.md`；三例合并（B022 F014 + B045-OPS1 v0.9.36 + B048-OPS1），过「等二例再合并」门槛。

---

### §12.11.1 env-硬失败守门是「入口级」不变量——每个新写生产 DB 的 CLI/job/service 入口都必须重新套用（v0.9.40 — B048-OPS1/B047-OPS1 二例沉淀）

**规律：** §12.11 的 env-硬失败守门（env 未导出 `WORKBENCH_DB_URL` → `::error::` 不静默写 scratch DB）是 **deploy.sh 单点**的守门——它**不会传递覆盖任何绕过 deploy.sh 的入口**。`get_engine()` 经 `settings.WORKBENCH_DB_URL` 在 env 未设时**静默回落 `DEFAULT_DEV_DB_URL`（dev scratch）**，所以**每个新增的、会写生产 DB 的进程入口（manual CLI / 新 job / 新 service ExecStart）都是一个独立的「裸入口」，必须各自重新套 env-硬失败守门**。假设 deploy.sh 的守门覆盖了它们 = B047 根因。

**二例（同一 scratch-DB 写入 bug，不同入口层）：**

| 实例 | 入口 | 机理 | 修 |
|---|---|---|---|
| **B048-OPS1**（v0.9.38 §12.11）| deploy.sh `alembic upgrade head` | env 未导出 → alembic 跑 scratch | deploy.sh env-url 空硬失败 |
| **B047/B047-OPS1**（本节）| **新增 CLI 入口** `python -m workbench_api.backtests.canonical` / worker `main` | 绕过 deploy.sh，`get_engine()` 静默回落 scratch；B047 re-verify 裸跑 canonical 写 scratch、API 读 prod → `/api/reports` 0（且**被误诊为读路径代码缺陷**）| 入口内调 `require_production_db(entrypoint=...)`：`WORKBENCH_DB_URL` 解析为默认 dev → `ScratchDatabaseError` → `::error::` + 非零退出**先于任何 DB 访问**；放行=显式非默认 URL 或显式 dev opt-in（`WORKBENCH_ALLOW_DEV_DB=1`）|

**规约：**

1. **新增任何会写生产 DB 的进程入口（CLI `main` / job / 新 service）时，入口处第一件事是 env-硬失败守门**（在开 session / `get_engine()` 之前）：prod DB env 缺失 → 响亮非零退出，**绝不静默回落 scratch**。抽共享守门（如 `require_production_db()`）复用，别每入口手写。
2. **守门必须先于 DB 访问**：测试 monkeypatch `get_engine=boom` 证明守门在触 DB 前就拦截（B047-OPS1 `test_require_production_db.py` 实例）。
3. **放行 dev/test**：显式 `WORKBENCH_DB_URL`（非默认）或显式 opt-in env，避免误伤本地/CI。
4. **判缺陷前先排除「验证操作自身的 env/DB-path 错误」**（与 evaluator.md §25 对偶）：B047 的「读路径 bug」实为裸跑写错 DB——代码无辜。

**来源：** B047-OPS1 F001（commit `8a3e325`，`db/require_production_db.py` + canonical/worker main 守门）+ B047 signoff §⟳⟳ Planner 裁定（根因=env→scratch DB 非读路径缺陷）+ B047-OPS1 signoff。二例合并（B048-OPS1 deploy.sh 层 + B047-OPS1 CLI 入口层），过门槛。

## 12.12 narrow-sudoers 通配符落盘类授权须经 root 属 wrapper 防路径穿越（v0.9.45 — B037-OPS1 沉淀）

**坑：** sudoers 通配符授权 `install` / 文件落盘类命令时，`fnmatch(3)` **不带 `FNM_PATHNAME`**——`*` 会匹配 `/`。目标参数 `.../prefix-x/../escape.suffix` 能字面匹配 `.../prefix-*.suffix` pattern，却经内核 `..` 解析**逃逸目标目录**（root 写任意文件）。

**规约（通用缓解）：** 把受限文件落盘交给一个**根属、调用方不可写的 wrapper 脚本**（接受裸名 / 拒绝含 `/` / 正则锁前缀+后缀 / 固定目标目录与模式），sudoers 只授权该 wrapper——既保留通配符的零手工耐久性，又把路径穿越彻底关在 shell 层。

**案例（B037-OPS1）：** 落地 `workbench/deploy/sudoers/workbench-install-unit`（security-reviewer 裁决）。复用窗口：未来任何 deploy 用户 narrow-sudoers 扩权（新增需 root 落盘的运维动作）。属 §12.9（secret 三处接线）/ §12.10（deploy-artifact 自包含）的 deploy/ops hardening 系列。

**来源：** B037-OPS1 F001 security-reviewer 裁决（单例，用户 2026-06-18 批 v0.9.45 全部沉淀）。

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

5. **Dev rewrite 必须覆盖生产 nginx `/api/*` 路由全集（v0.9.25 sub-pattern）：** 上面的 catch-all `/api/:path*` 是好做法。如果 next.config 用了 explicit per-route rewrites（如 `/api/health` + `/api/protected-test` 单独列），**加新 API endpoint 时必须同时**：

   - 扩 `next.config.mjs` 的 rewrites 列表（或换 catch-all）
   - 加 E2E 断言新 endpoint 不返 404（仅 200/401/422 等业务码合法）

   B022 fix-round 1 第 3 个 blocker 就是 dev rewrite 只配了 health + protected-test 2 个 endpoint，新加的 6 个 page API 全 404，但 Playwright E2E 不在 API 错误上 fail，让 bug 漏到 reverify 阶段才暴露。规约：**生产 API 路径与 dev rewrite 配置必须 1:1 对应**，加一个 endpoint 必须扩两处。

来源：B021 F006 fix-round 5（commit `4eb9c48`）`workbench/frontend/src/app/(protected)/page.tsx` + `next.config.mjs`；B022 F014 fix-round 1 blocker #3。

---

## 14. FastAPI 运行时观测 ergonomics（v0.9.25 — B022 沉淀）

### 14.1 SSE long-lived 请求需独立 session lifecycle

**症状（B022 F011 fix-round 2）：** SnapshotRefresh 用 SSE 流式 progress 给前端。FastAPI 默认 dependency-injected DB session 在请求结束时 close。但 SSE 请求"永远不结束"直到 stream 完，期间任何 DB write 会被 close 一次后再 reopen，导致并发问题 + connection pool 漏。

**规约：** 任何 SSE / WebSocket / long-polling endpoint **必须显式管理 DB session**（不用 FastAPI Depends），手动 open at start of stream + close in finally clause + 短小事务模式：

```python
@router.post("/api/snapshots/refresh")
async def refresh(...):
    async def stream():
        try:
            yield "event: start\n\n"
            # ... subprocess ...
            with SessionLocal() as session:  # short transaction
                session.add(SnapshotMeta(...))
                session.commit()
            yield "event: done\n\n"
        finally:
            # cleanup
            ...
    return StreamingResponse(stream(), media_type="text/event-stream")
```

### 14.2 全局未捕获异常 logger + /api/debug/recent-errors

**触发（B022 F014 fix-round 2 → fix-round 4）：** 生产 backend 出 `no such table: snapshot_meta` 等 OperationalError，但用户只看到 frontend 500，无法回溯。/api/health 全绿（health 不查这些表）。Codex L2 reverify 没工具找根因。

**规约：** FastAPI app 启动期注册全局异常 hook + 环形缓冲 + 只读 debug endpoint：

```python
# observability/error_buffer.py
from collections import deque
from datetime import datetime, timezone
_RING = deque(maxlen=50)

def record(exc: BaseException, request_path: str) -> None:
    _RING.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "path": request_path,
        "exc_type": type(exc).__name__,
        "exc_msg": str(exc)[:500],
        "request_id": REQUEST_ID_VAR.get(""),
    })

def snapshot() -> list[dict]:
    return list(_RING)

# app.py
@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    error_buffer.record(exc, request.url.path)
    logger.exception(...)
    return JSONResponse({"detail": "internal error"}, status_code=500)

# routes/debug.py — auth-gated, single-allowlist
@router.get("/api/debug/recent-errors", dependencies=[Depends(require_authenticated_user)])
def recent_errors():
    return {"count": len(snapshot()), "errors": snapshot()}
```

**Generator 规约：** 任何 FastAPI cloud app 起 spec 时必须含这 3 件套（global handler + ring buffer + auth-gated debug endpoint）。Codex L2 reverify 用 `GET /api/debug/recent-errors` 在每个真实写路径后核 `count=0`。

来源：B022 F014 fix-round 2 `c2f22d5` + fix-round 4 `8d9a948`。Codex L2 用此 endpoint 验证缺表修复后写路径不再触发 OperationalError。

---

## 15. i18n middleware chain — next-intl + NextAuth + locale cookie 持久（v0.9.26 — B024 沉淀）

**适用：** Next.js App Router 项目同时使用 `next-intl` (≥v3) 与 NextAuth v5 `auth()` middleware wrapper 时的串联与持久化。B024 F001 装这套时一次踩 4 个非显然坑，固化为框架规约避免下次重蹈。

### 15.1 双模块拆分：`src/i18n.ts`（server-only）+ `src/i18n-config.ts`（pure）

`getRequestConfig` / `getLocale` / `getMessages` 等 server-only API import `next/headers`，**任何 import 它们的模块都不能被 client / middleware bundle 加载**——webpack 会报 `'next/headers' is only allowed in Server Components ... pages/ directory not supported`。

**规约：** 一开始就拆双模块：

```ts
// src/i18n.ts — server-only, 含 next/headers
import { getRequestConfig } from 'next-intl/server';
import { isLocale, LOCALES, DEFAULT_LOCALE } from './i18n-config';
export default getRequestConfig(async () => {
  const locale = await resolveLocale();
  return { locale, messages: await loadMessages(locale) };
});

// src/i18n-config.ts — pure, 客户端 + 中间件都可 import
export const LOCALES = ['zh-CN', 'en'] as const;
export const DEFAULT_LOCALE = 'zh-CN' as const;
export type AppLocale = (typeof LOCALES)[number];
export const isLocale = (v: unknown): v is AppLocale => /* ... */;
export const LOCALE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
export const negotiateFromAcceptLanguage = (header: string | null): AppLocale => /* ... */;
```

**LocaleSwitcher / middleware 必须 import `@/i18n-config`，不能 import `@/i18n`** ——否则 webpack 立刻红屏。

### 15.2 middleware chain：先 NextAuth wrapper，再 ensureLocaleCookie 三分支都调

NextAuth v5 的 `auth()` wrapper 提供"已授权/未授权/公开"三个分支；i18n 的 cookie 协商必须在三个分支都执行，否则匿名首访（未授权重定向 path）就漏写 `NEXT_LOCALE` cookie，再次访问仍走 default 协商。

**规约：** 抽 `src/lib/locale-cookie.ts`，三分支都调：

```ts
// middleware.ts
import { auth } from '@/auth';
import { ensureLocaleCookie } from '@/lib/locale-cookie';

export default auth((req) => {
  const res = /* compute response based on auth */;
  ensureLocaleCookie(req, res);  // 公共、未授权重定向、已授权三分支都要调
  return res;
});

// src/lib/locale-cookie.ts
export function ensureLocaleCookie(req: NextRequest, res: NextResponse): void {
  const existing = req.cookies.get('NEXT_LOCALE')?.value;
  if (existing && isLocale(existing)) return;
  const negotiated = negotiateFromAcceptLanguage(req.headers.get('accept-language'));
  res.cookies.set('NEXT_LOCALE', negotiated, {
    maxAge: LOCALE_COOKIE_MAX_AGE,
    sameSite: 'lax',
    path: '/',
  });
}
```

cookie 规约：`maxAge=365d`、`SameSite=Lax`、`path=/`、name 固定 `NEXT_LOCALE`。

### 15.3 LocaleSwitcher 用原生 `<select>` 而非 Radix portal

Radix `Select` portal 在 SSR 期间会触发 hydration mismatch（dropdown content 走 portal 渲染时机与服务端不一致）。**用原生 `<select>` + `onChange` 写 cookie + `useTransition` + `router.refresh()`** 简单稳健：

```tsx
'use client';
import { useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { LOCALES, LOCALE_COOKIE_MAX_AGE, type AppLocale } from '@/i18n-config';

export function LocaleSwitcher({ current }: { current: AppLocale }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <select
      value={current}
      onChange={(e) => {
        document.cookie = `NEXT_LOCALE=${e.target.value}; Path=/; Max-Age=${LOCALE_COOKIE_MAX_AGE}; SameSite=Lax`;
        start(() => router.refresh());
      }}
      disabled={pending}
    >
      {LOCALES.map((l) => <option key={l} value={l}>{l === 'zh-CN' ? '中文' : 'English'}</option>)}
    </select>
  );
}
```

### 15.4 layout.tsx 改 async + NextIntlClientProvider + `<html lang={locale}>`

```tsx
// src/app/layout.tsx
import { NextIntlClientProvider } from 'next-intl';
import { getLocale, getMessages } from 'next-intl/server';

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
```

`<html lang>` 必须按 locale 切，否则浏览器/无障碍工具仍按默认语言识别。

### 15.5 TS AppConfig 类型链 — typo 触发 tsc 报错

```ts
// src/types/intl.d.ts
import type zhCNMessages from '../../messages/zh-CN.json';
declare module 'next-intl' {
  interface AppConfig {
    Messages: typeof zhCNMessages;
    Locale: 'zh-CN' | 'en';
  }
}
```

之后 `t('common.foo.typo')` 在 tsc 阶段直接报错。**Messages 类型挂哪一语种 JSON 都行**（messages bundle key set bit-identical 是单独的 CI 守门），习惯挂 default locale。

### 15.6 vitest middleware 测试用 node env，不能加 happy-dom

`NextRequest` 的 cookie 解析在 happy-dom 环境下异常（response cookies 写不进 request cookie view，测断言全错），看似 next-intl 的 bug，实为 jsdom/happy-dom 对 `Request`/`Response` Web API 的兼容缺陷。

**规约：** middleware-locale 类 spec 文件**不要**加 `@vitest-environment happy-dom`/`jsdom`，走默认 node env：

```ts
// tests/unit/middleware-locale.spec.ts — 不加 @vitest-environment
import { NextRequest, NextResponse } from 'next/server';
import { ensureLocaleCookie } from '@/lib/locale-cookie';

describe('ensureLocaleCookie', () => {
  it('writes NEXT_LOCALE cookie when missing', () => {
    const req = new NextRequest(new URL('http://localhost/'), {
      headers: { 'accept-language': 'zh-CN,zh;q=0.9' },
    });
    const res = NextResponse.next();
    ensureLocaleCookie(req, res);
    expect(res.cookies.get('NEXT_LOCALE')?.value).toBe('zh-CN');
  });
});
```

LocaleSwitcher / 组件测试仍用 happy-dom（React Testing Library 必需），只 middleware/Edge runtime 类用 node env。

### 15.7 反面案例汇总（B024 F001 一次踩这 4 个）

| 现象 | 根因 | 修法 |
|---|---|---|
| `'next/headers' ... pages/ directory not supported` | LocaleSwitcher 间接 import `@/i18n` 拉到 next/headers | 拆双模块（15.1），client 走 `@/i18n-config` |
| middleware-locale.spec.ts 全红 | spec 头加了 `@vitest-environment happy-dom` 致 NextRequest cookie 解析异常 | 删指令走默认 node env（15.6） |
| 匿名首访漏写 `NEXT_LOCALE` cookie | NextAuth 未授权重定向分支没调 `ensureLocaleCookie` | 三分支都调（15.2） |
| dropdown SSR hydration warning | Radix portal SSR mismatch | 换原生 `<select>`（15.3） |

**来源：** B024-i18n-zh-cn F001 commits `fde867d` + `9e398a1`；B024 signoff §Framework Learnings 候选 β。配套 planner.md §"i18n 中文按钮禁词扩集" + §"i18n disclaimer / compliance 文案双语永存" 是 Spec 层守门。

---

## 16. Feature decommission ≠ env flag off — 四处清理铁律（v0.9.31 — B030 沉淀）

**触发：** B030 F003 关 B026 synthetic data banner，Generator 走 v0.9.30 §12.9 「production secret 三处接线」模式（`.env.example` + `.env.production` + `bootstrap-env.yml` frontend env file）让 banner build-time disable。**Codex F004 verify L1 grep `研究原型` / `SyntheticDataBanner` 仍命中 production HTML bundle**，标 blocker。

根因调查（fix-round 1）：
- React 组件正确 dead-code-eliminate 到 `return null`（env=false 路径）
- **但** `syntheticBanner.headline` i18n keys 仍 ship 在 messages JSON RSC payload
- **且** `(protected)/layout.tsx` 仍 import + 渲染 `<SyntheticDataBanner />`（即使 component 返回 null，组件名仍出现在 layout chunk）

Codex grep 命中 **i18n bundle 字面值 + chunk name**，不是渲染 DOM。本批次 spec 当初按"env flag 关 = 完全 disable"的假设过于乐观。

**真正的 decommission 需要 4 处清理（即使 env flag 已 false）：**

```
┌────────────────────────────────────────────────────────────────┐
│ Feature decommission 四处清理铁律（每次退役 UI surface 必查）        │
├────────────────────────────────────────────────────────────────┤
│ 1. Layout / Page JSX                                           │
│    从所有 import + JSX 渲染处移除组件引用                        │
│    （仅 env flag 控制 → 组件名仍在 chunk；移除 import 才彻底）    │
│                                                                │
│ 2. i18n messages JSON                                          │
│    删除组件用到的所有 namespace keys（如 syntheticBanner.*）     │
│    （keys 留在 messages JSON 会随 RSC payload ship；grep 命中）  │
│                                                                │
│ 3. 组件文件保留 + decommission notice + 重启路径                 │
│    Component file 不删，加 "DECOMMISSIONED YYYY-MM-DD" 注释 +    │
│    reactivation playbook（hardcoded 双语 + useLocale 替代        │
│    useTranslations 让重启不依赖 i18n keys 恢复）                 │
│                                                                │
│ 4. 守门测试（presence guard + isolation guard）                  │
│    (a) tests/safety/<feature>-decommissioned.spec.ts —          │
│        断言 layout 无 import + messages 无 keys                  │
│    (b) tests/unit/<feature>-component.spec.tsx —                │
│        组件 isolation 测试（验证重启路径仍可用）                  │
│    (c) legacy E2E presence assertion → absence assertion        │
│        （v0.9.31 §22 evaluator.md 同源规则）                     │
└────────────────────────────────────────────────────────────────┘
```

**规约（Planner 起 decommission 类批次 spec 时硬要求 + Generator 实施 checklist）：**

1. **Spec acceptance 必含四处清理**：任何关 UI feature / 切换 layer / 退役组件的 spec acceptance 不能只写 "env flag = false"，必须显式列 4 处清理 + 守门测试 acceptance。
2. **Generator 实施 checklist**：从 layout 移 import 开始（不是从 env flag 开始）；删 i18n keys；组件文件保留并加 decommission notice；最后才改 env flag（env flag 是双保险不是主路径）。
3. **Planner pre-impl 审计**：若 spec 写 "v0.9.30 §12.9 4 处接线 env=false" 而未列 4 处清理，Planner 在裁决时主动补该项（参考 v0.9.X §pre-impl 范式）。
4. **Evaluator L2 验证**：production HTML grep 组件名 + i18n keys 字面值 0 命中（不只是浏览器看不到 DOM）；详见 evaluator.md §22。

**反面案例（B030 F003 verify → F004 fix-round 1）：**

| 阶段 | 现象 | 根因 | 修法 |
|---|---|---|---|
| F003 实施 | `.env.example` + `.env.production` + `bootstrap-env.yml` 三处接线让 banner build-time disable；本机 build grep 通过 | 仅按 v0.9.30 §12.9 secret 三处接线模式做 env flag；layout 仍 import + i18n keys 仍 ship | — |
| F004 Codex verify | production HTML grep `研究原型` / `SyntheticDataBanner` 命中 → blocker | i18n bundle 字面值 + layout chunk name 仍存在 | — |
| F004 fix-round 1 | layout 移 import + messages 删 keys + 组件加 decommission notice + 6 guard + 9 isolation tests + legacy E2E presence→absence | 完整执行四处清理 | ✓ |

**与 v0.9.30 §12.9 secret 三处接线对比：**

| 维度 | v0.9.30 §12.9 secret 三处接线 | **v0.9.31 §16 decommission 四处清理** |
|---|---|---|
| 场景 | 新加 production secret | 退役 UI feature |
| 自动化机制忽略的层 | `bootstrap-env.yml` workflow inject | layout import + i18n keys + legacy E2E |
| Manual 清理需要 | 4 处（.env.example / config.py / deploy.sh / bootstrap-env.yml）| 4 处（layout JSX / i18n keys / 组件保留 + notice / 守门测试 + E2E 翻转）|
| 反 anti-pattern | "deploy.sh check 已够" 假设漏 bootstrap-env.yml | "env flag = false 已够" 假设漏 layout + i18n + tests |
| Codex 发现机制 | L2 production VM `cat /etc/workbench/workbench.env` grep | L2 production HTML grep 组件名 + i18n 字面值 |

**预防价值：** Phase 3 Home UI 重构（B037+）/ Phase 4 长尾 batches 任何 layer 切换 / sleeve decommission / vendor 切换都直接受益。Generator 主动按 §16 4 处清理 ≈ 1 个 fix-round 节省。

**来源：** B030 F004 fix-round 1 commits `abf2ec4` （F001 floor recovery + B026 banner truly off）+ `095e91d` （Playwright spec presence→absence）+ B030 signoff §Framework Learnings 三条候选（**Codex first-class 主动列入**，与 B027/B028/B029 Codex 标"无 learnings"模式不同）。配套 evaluator.md §22 + signoff-report.md §Decommission Checklist。

## 17. 用户输入必须能追踪到执行层真正消费——「装饰性控件 / plumbed-but-ignored 字段」反模式（v0.9.41 — B050 三例沉淀）

**反模式：** 一个用户输入（UI 控件值 / 请求体字段 / 落库列）被**接收·校验·存储**，却被**真正算结果的执行层忽略**——于是控件成摆设、参数对输出无影响，用户以为在控制系统、实则没有。schema 有字段 / 校验通过 / 入库成功 **≠ 该输入生效**。

**三例（B050 一批同源，远超「等二例」门槛）：**

| 实例 | 输入被接收/存储处 | 执行层忽略处 | 用户症状 |
|---|---|---|---|
| backtest `strategy_id`（根因）| `services/backtests.py` 校验 + `enqueue(strategy_id=…)` 落库 `backtest_run.strategy_id` | `worker.py` `run_backtest_job` 写死 `run_master_portfolio_quarterly_backtest`，从不读 strategy_id | 选任何策略相同时段结果都一样 |
| backtest `parameters` | schema 收 + 入队 `params["parameters"]` | worker 不解析 | 调参数结果不变（前端尚无编辑器故潜伏）|
| backlog `status` | `BacklogUpdateRequest.status` 收 | `services/backlog.py` 显式不存 + 读时硬编码 `"open"` | 改状态刷新后恢复 open |

**规约：**

1. **Generator 实现一个新请求字段 / UI 控件时，必须一路追踪到「算输出的那行代码」确认它被读**——不是「存进 DB / params 就完」。worker/job/precompute 的入参协议（如 `BacktestRunLike`）若只暴露部分字段，是高危信号（结构上就读不到被忽略的字段）。
2. **要么接线、要么删字段**——不留「plumbed but ignored」。产品暂不需要就从 schema/控件移除，别留装饰性入口误导用户（与 §16 decommission 同源：留半截 = 误导）。
3. **Planner pre-impl 审计**：spec 写新控件/参数时，acceptance 必含「该输入 X 改变 → 输出 Y 改变」的正面断言项。
4. **Evaluator 验收**：见 evaluator.md §26——核「输入真影响输出」（选不同值结果须不同），不止「接口收了 200」。

**反向自查（一句话）：** 「这个控件/参数，用户改了它，**屏幕上的数字会变吗**？」答不出「会，因为执行层第 N 行读了它」就是装饰性控件。

### §17.1 变体：同一实体两张表读写分裂（v0.9.42 B051 二例 → v0.9.44 B058 三例强化）

同族反模式的镜像形态：写入确实生效了，但**读路径读的是另一张表/另一个源**——「UI 写 A 表、功能读 B 表」，写入永远到不了读取。与主形态（输入被执行层忽略）同根：**写入面与消费面没有同源核验**。

**案例（B051，生产用户报障）：** UI Account 页 PUT 写 `account_snapshot`（执行流 7 处读它），但 `nav.aggregate_nav` + `recommendations._aggregate_account_state` 读另一张 `account` 表（仅由 `accounts/me.json` bootstrap 填，空）→ 用户 UI 设了账户，Recommendations 仍「尚未配置账户」+ home nav=0.0（B046 S1 长期遗留同根因）。

**规约（在 §17 规约 1 上加强）：**

1. **新增/修改一个写入面时，grep 该实体的所有读路径，确认全部读同一来源**；发现两张表/两个源承载同一实体（如 `account` vs `account_snapshot`），即为高危信号——要么统一单一真相源，要么写入双写保持同步，**不允许「各读各的」**。
2. **同实体多源是 §17 反向自查的表级版本**：「用户在 A 处写入，B 处的显示会变吗？」答不出「会，因为 B 读的就是 A 写的那张表」就是读写分裂。
3. 历史成因常是「bootstrap/种子路径先建了一张表，UI 路径后建了另一张」——新建写入路径时必查既有表是否已承载同一实体。
4. **（v0.9.44 — B058 三例新增）修一个 ≠ 修另一个**：当同一逻辑数据有两个物理存储、读写方分属不同子系统时，**修了一个不代表修了另一个**。修复/扩覆盖某数据源前，先列出「同一数据还有哪些物理存储 + 各自谁读」，对**每个生产实际读取的源**分别确认。**案例（B058 三例）：** 模拟盘 mark 源 `price_snapshot`（workbench 侧）与目标生产者读的「统一价格文件」`prices_daily.csv`（trade 侧）是两个库；B058 F002 只修了 `price_snapshot` 覆盖，regime 生产者读的统一文件没动 → 部署后 data-refresh 未带新 universe 重跑 → regime 刷新报错。**配套**：新增/扩 universe 的部署有「代码已更新但数据未重跑」时序窗口，错误须 actionable（B058 加 error_kind=data_not_covered + coverage_hint）。

**来源：** 用户 2026-06-09 报「回测页选任何策略结果都一样」→ B050 根因 + 两次系统审查（`docs/product/b050-class-decorative-control-audit-2026-06.md` + `trade-recommendation-fidelity-audit-2026-06.md`）连带挖出 parameters/backlog status 同源；§17.1 二例 来源：用户 2026-06-10 报「UI 设账户 Recommendations 不认」→ B051 根因（signoff `docs/test-reports/B051-account-source-unification-signoff-2026-06-10.md`）；§17.1 三例 来源：用户 2026-06-13 报「regime 立即刷新失败 producer_error」→ B058-F003 根因（signoff `docs/test-reports/B058-mode-data-and-manual-control-signoff-2026-06-13.md`）。配套 evaluator.md §26 + §28。

## 18. 幂等/缓存复用必须区分「真实产物」vs「占位/降级值」（v0.9.43 — B043+B053 二例沉淀）

**反模式：** 一个 precompute / 缓存 / 幂等 skip 逻辑，用「这条记录存在/非空/今天已生成」来决定「跳过重生成」——但**没区分这条记录是真实成功产物，还是占位/降级/拒答产物**。结果：一旦某次生成落了降级值，幂等检查就把它当「已完成」永久复用，**真实产物永远生不出来**。

**二例：**

| 实例 | 幂等判据（错）| 后果 |
|---|---|---|
| B043 recommendations rationale | `rationale != null` 就跳过 | 部署前存的是确定性占位文案 → 幂等当它"已生成" → **整季度永卡占位**，LLM rationale 永不生成（信号日季度才变）|
| B053 advisor precompute（advisor/precompute.py:66）| `generated_at.date()==today` 就跳过，**不看 status** | LLM 拒答日落 `INSUFFICIENT_GROUNDING` 行 → 当日重跑被 skip → **整天卡拒答**，LLM 恢复了也不重试 |

**规约：**

1. **幂等 skip 条件必须断言「是真实成功产物」**，不是「记录存在」：
   - B043 修法：`existing.rationale != deterministic_placeholder(...)` 才复用（等于占位 → 重生成）。
   - B053 修法：skip 条件加 `and latest.status == STATUS_OK`（降级/拒答行不算已生成）。
2. **降级产物要么不写、要么标记可重试**：写降级值时确保下次自然重试窗口能覆盖它（status 字段 / 占位可识别 / 时间窗）。
3. **自查**：「如果这次生成失败/降级落了个占位，下次 run 会重试它，还是会把占位当成品永久复用？」——后者就是本反模式。
4. **与 §17 同源**：都是「写入面与读取/复用面没核验产物真实性」——§17 是装饰性输入，§18 是装饰性产物（占位被当真）。

**来源：** B043 fix-round 1（recommendations 幂等复用占位 rationale）+ B053 F002（advisor 幂等不看 status，BL-AUDIT-S1，第四轮审计 `docs/product/post-b052-hidden-bug-audit-2026-06.md` §2 发现并修）。配套 §17 反模式族。

## 19. 本地门禁必须 CI-exact——mypy 扫 `workbench_api + tests`（v0.9.44 — B057+B059 二例沉淀）

CI 的 mypy 步骤是 **strict 扫 `workbench_api` AND `tests`**（见 `workbench-backend.yml` "Mypy (strict — workbench_api + tests)"），不止 `workbench_api`。本地只跑 `mypy workbench_api`（0 error）就推码，会漏掉 test helper 的类型问题（如 `no-untyped-def` 缺返回注解）→ CI 红 → 多一次 fix-push。

**规约：** push 前本地必跑 **CI-exact** 的 `mypy workbench_api tests`（或固化进 pre-push 门禁脚本），不要只跑 `mypy workbench_api`。泛化：**本地门禁命令必须与 CI 步骤逐字一致**（包括扫描范围），CI 配置即真相源——见测试策略「CI matches local」原则。

**来源：** B057 F004（第一实例，记入 proposed-learnings 未沉淀）+ B059 F001（第二实例，本地只跑 `mypy workbench_api` 漏 test helper `no-untyped-def`，一次 fix-push）。

### §19.1 ruff 本地必须**目录上下文** `python -m ruff check .`，勿对单文件/子集跑 check 或 `--fix`（v0.9.47 — B065 F001 沉淀）

**坑：** `ruff` 的 isort first-party 检测**依赖 project 上下文**：`ruff check <单文件>`（或对子集跑 `--fix`）从 `workbench/backend` 跑时**不把 `workbench_api` 识别为 first-party** → 不要求 third-party(`pytest`) 与 first-party(`workbench_api`) import **组间空行**；而 CI（Backend `python -m ruff check .` + Python CI 根 `ruff check .`，都是**目录上下文**）能识别 first-party → 要求空行 → `I001`。B065 F001 对单测单文件跑 `ruff check --fix` 反而**删掉**了该空行，本地单文件 "All checks passed!"，push 后 Backend CI + Python CI **双红 I001**。

**规约：** push 前本地 ruff 门禁**必须 `python -m ruff check .`（目录上下文，与 CI 完全一致）**，**不要对单文件 / 子集跑 `check` 或 `--fix`**——单文件模式因缺 project 根而漏检 import 分组，造成"本地绿 CI 红"。这是 §19「本地门禁 CI-exact」对 ruff 的具体落点（与 environment.md §CI 分层 同族）。

**来源：** B065 F001（commit `e3705a6` 修 I001 import 分组）。

## 20. 新增后端路由的配套清单（v0.9.44 — B057+B059 二例沉淀）

新增一个后端路由前缀（如 `/api/symbols`）时，**仅加路由 + 实现是不够的**，必须同步：

1. **`next.config.mjs` 的 `PROXIED_PREFIXES`** 加该前缀——否则 dev 服务器对它返 404（不代理到后端），Playwright E2E 的「零 console error」断言会因 404 资源加载报错而红（vitest 单测不覆盖，dev/E2E 才暴露）。
2. **`dev-rewrites-cover-backend-api` 守门测试**的 `REQUIRED_PREFIXES` 加该前缀（pin 约定：每个后端路由前缀须同时在 config 与该 guard 中）。
3. **新 navigable 前端页**须渲染 canonical disclaimer（`disclaimer-present` safety 守门）。
4. 若 schema 变更，`api.ts` 重生 + drift 检查。

**来源：** B057 F005（第一实例，post-signoff Frontend CI 红，commit 5762dd0 补 next.config + guard）+ B059 F001（第二实例，开工即正确同步 PROXIED_PREFIXES + guard，引用 B057 教训，signoff 记 PASS）。

## 21. merge/upsert 不应用 column default（v0.9.44 — B057 F004 沉淀）

deterministic-id upsert（SQLAlchemy `merge`）模型新增 **NOT NULL + server_default** 列时：**column default 仅在 INSERT 生效，幂等 re-run 的 `merge→UPDATE` 不应用 default**，会把列写成 NULL 触发约束失败。

**规约：** 构造 ORM 对象时**显式设该列值**，不能依赖 column default。症状典型为「idempotent bootstrap 第二次 run SystemExit/rollback」。

**来源：** B057 F004（bootstrap `_coerce_account_snapshot` 加 strategy_id 列后二次 run 触发）。

## 22. spec「复用现有 X」与现实冲突时的偏离裁定（v0.9.44 — B059 F003 沉淀）

spec 写「复用现有 X」时，X 可能对**本批的新输入域不适用**——X 可能是 universe-bound / fair-access 限流 / 对错误输入有 IP 封禁等约束，对「任意输入」不安全。

**规约（Generator 遇此冲突）：** 偏离合理，但须 ①**报 planner 裁定**；②**诚实标注实际用的源**（不冒充 spec 写的源）；③**不污染原权威路径**（偏离只限本功能，不动既有依赖 X 的关键路径）。

**案例（B059 F003）：** spec 写「复用 SEC fundamentals_loader」，但 SEC EDGAR universe-bound(27-CIK)+错误/高频请求封 IP 30 天 → 对任意 ticker lookup 不适用，且强行用会 IP 封禁**危及共享 SEC 访问=污染真实策略基本面管道**。偏离改用 yfinance .info（任意 ticker，保留 US-only 门禁 + 诚实标源），planner 裁定接受（偏离只限 lookup 展示，策略权威 SEC 路径未动）。

**配套：** planner.md 铁律 8（spec 写「复用 X」前应标注 X 的适用域）。

**来源：** B059 F003（signoff `docs/test-reports/B059-symbol-price-lookup-signoff-2026-06-13.md`）。

### §22.1 扩展：spec 校验/检查条款须核「实际实现的粒度」，现实已隐含满足则不造装饰机制（v0.9.45 — B061 F003 沉淀）

§22 是「X 是否适用」；本条是「X 的**实现是否已隐含满足**新需求」——避免为字面满足 spec 而构建无行为差异的 variant / market-aware 机制（= §17 plumbed-but-ignored 反模式）。

**案例（B061 F003）：** spec §9.6 假设一个 *daily* 交易日 gap 检查会把 CN 节假日误判为缺口，要求按市场选日历。但 `trade/data/loader._calendar_gaps` 实际是**月粒度**启发（连续交易日 >1 自然月才标 gap），对任何最长休市远短于一月的市场（含 CN，春节~1 周）**天然安全** → §9.6 担心的误判不会发生。故 Generator 裁定：(1) **不**把需 akshare 网络源的 daily CN 日历塞进离线确定性的 `trade` 引擎（零收益 + 过度耦合）；(2) **不**加装饰性 `market` 参数（US/CN 月粒度下无行为差异 → 触 §17）；(3) 交付=命名日历模块（loader 真消费）+ 市场检测工具 + CN 安全回归测试（春节周不误标 / 真 >1 月洞仍标）。planner 裁定接受。

**规约：** 实施 spec 的校验/检查条款前，**先核实际实现的粒度/行为**；现实已隐含满足 spec 意图时，不要为字面满足而造无行为差异的机制（over-engineering + §17 装饰代码）。**配套：** planner.md（写「按 X 维度处理」前先核 X 在代码里是否真有行为差异）。

**来源：** B061 F003（planner 已批裁定，规律 v0.9.45 沉淀）。

## 23. 新数据 provider/端点：本地实跑真调用验可达+格式，勿因兄弟端点通而推定（v0.9.45 — B062 F001 沉淀）

**坑：** 扩展新市场/数据端点时，**不能假设「兄弟端点」（同 lib 不同函数）可达且行为一致**——每个新端点须实际验证可达 + 符号格式 + 真返回 shape，不能因相邻端点通就推定。

**案例（B062 F001）：** HK provider 把 akshare `stock_hk_hist` 当作 A 股 `stock_zh_a_hist` 的港股镜像直接用（同为 akshare，假设同源可达），但**两者命中不同主机**：A 股走 eastmoney 常规主机（可达），HK 走 `33.push2his.eastmoney.com`（**可复现 ReadTimeout**，本地 + prod 都坏，非 geo）。结果 prod 查 0700.HK 全失败。修复=换 akshare `stock_hk_daily`（**sina 端点**，B060 spike 已验从 VM 可达）→ 真返回 5405 行腾讯；该函数无 date 参（返全历史）须 provider 端按窗过滤。

**规约：**

1. 写新数据 provider/端点时，**本地实跑一次该端点的真调用**（不只单测 mock），确认函数名 / 符号格式 / 可达 / 返回 shape——B062 若 F001 当时本地跑过 `stock_hk_hist(00700)` 就当场暴露。
2. 同一数据 lib 的不同市场/函数可能走**不同主机、不同可达性、不同参数**（有无 date 参 / 列名中英文），不可结构类推。
3. 选端点时**优先已被 spike 验过可达的源**（B060 验了 sina / eastmoney-A股 / tushare，HK 端点从没验）。

**与 evaluator §25.1 互补：** 那条是「验收没真做」，这条是「实现建在未验证端点假设上」——两侧都指向「真数据/真端点须实跑」。

**来源：** B062 F001 fix-round 1（HK lookup prod 坏，commit `af57842`）。配套 planner.md（spec 扩新市场须含「先验该端点可达」任务）。

## 24. 决策级/对比类 harness 须过 adversarial「公平性/诚实性」复审——绿门禁抓不到不对称（v0.9.45 — B063 F003 沉淀）

**规律：** 当交付物是**会被用来做决策的数字/对比**时，pytest + mypy + ruff 全绿 + 单测全过**只证明「能跑、类型对、风格对」，不证明「比较公平、归因诚实、边界对称」**。须专门跑一轮 adversarial fairness/honesty 复审。

**案例（B063 F003）：** 对比 harness 全门禁绿 + 13 单测过，但 adversarial workflow（3 维度）抓出 9 个 confirmed，含 1 个 **CRITICAL 公平性**：proxy 信号自磁盘独立加载价格、与 execution 不同源，而 real 信号读传入帧（hermetic）→ 两侧「同口径」承诺被悄悄破坏，会让「real vs proxy」决策报告失真。其余高价值修正：CAGR wipeout 返 0.0 掩盖巨亏（→ −1.0）、top_n 默认不同（2 vs 6）静默混淆集中度与数据源（→ 显式 surface）、PIT universe 随时间增长未披露（→ avg_candidates）、defensive 混淆 data-gap 与策略规则（→ forced_defensive 分离）。

**对比类工具检查清单：**
- [ ] 两侧**同 inputs 同源**（signal + execution 读同一帧 / 同一价格源）
- [ ] **同参数**（或差异**显式披露**，不静默）
- [ ] **同年化 / 同口径**指标
- [ ] **edge-case 同处理**（wipeout / 空选股 / 缺数据）
- [ ] **provenance 可审计**（每个数字能追到来源）
- [ ] **残余偏差 caveat 入产物**（报告自带诚实声明）

**做法：** 值得用多 agent workflow（每维度独立 + 逐 finding 对抗验证），单一视角易漏对称性问题。

**来源：** B063 F003（adversarial review 9 修，1 CRITICAL 公平性）。配套 evaluator §25.1（决策级批次验收纪律）。

## 25. async job 范式（请求路径 enqueue → 长驻 worker → 前端轮询）（v0.9.45 — B047 沉淀）

当出现「on-demand 重计算」需求但请求路径禁 `import trade`（§12.10.2）时，用 async job 范式：请求路径 `enqueue`（202 + run_id）→ 长驻 worker service（`import trade`）原子 `claim_next_queued` 领取 → 跑 → `save_result` → 前端轮询 GET。守 §12.10.2（请求路径只读 DB，worker 在 allowlist 里 import trade）。

**来源：** B047 backtest on-demand（首个 async 模式，`workbench-backtest-worker.service` 长驻 `Restart=always`）。单例记录，未来同类（on-demand 重计算撞请求路径禁 import）可复用。

## 26. v0.9.45 小坑合集（单例，用户 2026-06-18 批一并沉淀）

**26.1 改 JSON 状态文件长字符串值，用整值替换或程序化边界切片——勿前缀 Edit（B063）：** 覆盖写 progress.json 的 `session_notes`（长中文值）时，若用 Edit 只匹配值的「前缀」来替换，旧值尾部会残留在新闭合引号之后 → `"key": "<新>"<旧尾>",` = JSON 损坏（`Expecting ',' delimiter`）。规约：(1) 要么 `old_string` 覆盖**整个旧值**（含结尾），要么**程序化替换**（读原始文本、用无歧义边界锚点切片重写、写回前 `json.loads` 校验，对长值更稳）；(2) 铁律 #11（commit 前 `json.load` 校验）是这次的安全网，务必保留；建议 `.git/hooks/pre-commit` 真挂自动校验。

**26.2 禁用包黑名单扫 loaded modules 用精确 import-root，子串匹配只对 pip dist 名安全（B060 F002）：** A 股探针依赖卫生自审扫 `sys.modules` 确认未引入券商 SDK（futu/tiger/ib/alpaca）。初版用子串 `"futu" in mod.lower()`，而 `__future__`（`from __future__ import annotations` 几乎每个 .py 都有）含子串 `"futu"` → 误报 hygiene FAIL。规约：扫 **loaded modules / import** 用**精确 top-level import-root 匹配**（`mod.split(".")[0] in {禁用根集合}`）；**子串匹配只对 pip distribution 名安全**（`__future__` 不是 dist）。同源：早期 `grep -rn "futu" trade/` 命中的全是 `from __future__ import annotations`。

**26.3 改 `trade/` 后 workbench venv 的 trade 是 copy 装，须 force-reinstall 刷新才能本地测（B057 F004 残留，与 §19 同族）：** workbench venv 里的 trade 是 copy 安装（非 editable），改了 `trade/` 包的代码后本机 workbench venv 测的仍是旧拷贝 → 须 `python -m pip install --force-reinstall --no-deps <repo>` 刷新才能本地复现 CI。与 §19（本地门禁 CI-exact）同族：本地环境须与 CI 真实状态一致。

**来源：** B063 F002/F003（JSON Edit 坑）+ B060 F002（banlist 子串误判）+ B057 F004（venv copy 刷新残留）。均单例小坑，用户批 v0.9.45 一并沉淀。

## 27. 前端「本机绿 ≠ CI 绿」二坑（v0.9.46 — B064 F003 沉淀）

> 共同根因：前端**本机单测/渲染绿，不代表 CI 绿**——环境的 ICU 版本、异步 fetch 时序在 CI 慢环境下会暴露本机掩盖的缺陷。与 evaluator.md §27（CI flake 放行纪律）互补：那条是「遇到 flake 怎么放行」，本条是「实现/测试时怎么不写出 flake」。

**27.1 被断言的金额/数字显示用确定性符号前缀，勿 `Intl` compact+currency / narrowSymbol（货币显示）：** `Intl.NumberFormat` 的 `notation:"compact"` 与 `style:"currency"` 组合**渲染依赖运行环境的 ICU 版本/数据**——本机产 `"$3T"`、CI 的 Node ICU 产不含 `"3T"` 的串 → 断言子串（如 `"3T"`）的测试会 flake（B064 US 基本面断言两连红）。**且** `currencyDisplay:"narrowSymbol"` 把 HKD 解析成裸 `$`（与 USD 混淆，同卡市值显 `HK$` 却 narrowSymbol 显 `$` → 不一致）。**规约：**（1）任何会被**断言子串**的金额/紧凑数字显示，**别用 `Intl` compact+currency 组合**；用**确定性符号前缀映射**（`¥`/`HK$`/`$`）+ 稳定 plain 数字格式（decimal grouping 跨 ICU 稳）。（2）多币种 UI 不依赖 `narrowSymbol`（HKD→`$`、其它币种亦可能歧义）；显式维护 `currency→symbol` 映射。（3）被测试断言的格式化函数：本机绿 ≠ CI 绿，须确定性实现 + **跨币种 fixture**（B064 CN-only fixture 漏掉 HKD `$` 歧义，补 HKD fixture 才抓到）。

**27.2 测试 `waitFor` 等被断言的目标元素本身，勿等容器后同步查异步子元素（前端测试）：** `await waitFor(() => getByTestId("容器"))` 后**紧接** `getByTestId("仅 fetch 完成后渲染的子元素")` 会 race：容器（如 fundamentals 卡片）在 loading 态就渲染，waitFor 立即通过，但子元素（依赖二段 fetch）尚未出现 → 本机 fetch 快侥幸过、CI 慢则 `Unable to find element` 红（B064 新 CN 用例正中此坑：等卡片后同步查 standard note）。**规约：** `waitFor` 必须**等真正要断言的目标元素本身**（`await waitFor(() => expect(getByTestId("目标子元素")).toBeInTheDocument())`），不要等一个「总会先渲染」的祖先容器再同步取子元素。

**来源：** B064 F003 自评 adversarial review（commit `178be1e` 确定性货币前缀 + `f7e93d6` waitFor 时序修复 + HKD fixture）。两条单例前端坑，用户批 v0.9.46 一并沉淀。

## 28. 回测引擎真实数据缺口——停牌 ffill + NaN 安全读价（禁 `or 0.0`）+ 缺价回归测试（v0.9.48 — B066 F002 沉淀）

**坑：** 真实价格数据里 **停牌（停盘）= 某 (ticker, 日) 行缺失** → pivot 出 **NaN**。两个被合成测试（每个 ticker 每日都有价）系统性掩盖的真实 bug（B066 F002 自跑对抗审查抓到，均 HIGH）：
1. **rebalance 分支只从「有价目标」重建持仓** → 停牌持仓被丢弃、市值凭空蒸发（权益守恒被破，实测 100k→50k）。
2. **`float(row.get(t, 0.0) or 0.0)` 不能把 NaN 归零**——**`nan or 0.0 == nan`（NaN 在 Python 为真值！）** → 停牌名污染 mark-to-market → equity 出 NaN → `pct_change` 吞掉跨 NaN 的真实收益、`cummax` 被毒化致 `max_drawdown` 失真。

**规约：**
1. 回测引擎对停牌/缺价名须 **ffill 结转最后已知价**（标准处理，价值守恒）；**持仓 carry-forward，永不让持仓静默消失**。
2. 任何按价估值/读价处须**显式 NaN 安全读价**（`v is None or pd.isna(v) or v <= 0`），**禁用 `v or 0.0`**（NaN 真值陷阱）。
3. **合成回测数据若每格都有价，会系统性掩盖停牌路径**——真实数据批次须专门构造**缺价/停牌回归测试**。

**来源：** B066 F002 自评 adversarial review（A股 停牌缺价，commit `3228c06` 系）。同族于 §17/§18（合成掩盖真实缺口）。

## 29. 多变体研究报告：退化空仓变体必须红旗，勿静默报 0.00%（v0.9.48 — B066 F003 沉淀）

**规律：** 多变体对比报告里，一个变体若**空截面/缺因子数据**（如 A股 质量因子在 fundamentals 稀薄时选不出股）→ 退化为满仓现金、CAGR/Sharpe/换手全 0、never traded。报告若把这个干净的 **0.00% 当真实结果展示**（尤其它驱动 headline 图表 + payload metrics），**研究判定被悄悄破坏**——分不清「故意持现金」vs「数据缺失没测到」。

**规约（研究报告红旗体系，除「样本内≠样本外 winner / 夏普离谱 / 全变体无差异」外）：**
1. **必须含 `no_activity` 红旗**：`rebalance_count == 0` / 换手 0 + 曲线平 → 标「never traded，0.00% 非真实结果」，命中 headline 时尤其响亮。
2. **同子族内 toggle 失效红旗**：同因子的 N 个退出变体结果**字节相同** = 退出规则从未生效；注意全局 spread 测试在「两族发散」时会漏掉同族内的 toggle-inert，须分子族检测。

**来源：** B066 F003 自评 adversarial review（A股 质量变体本地退化等值）。同族于 evaluator.md §29/§25（真值=不得 done / 0-result 不判 non-blocking）——本条是其在「多变体研究报告」的对偶。

## 30. 回测引擎复权口径必须一致——raw-open 买 / adj-close 估值混用 = bug，合成 fixture `adj==close` 系统性掩盖（v0.9.49 — B071 F003 沉淀）

**坑：** 回测引擎**执行（买股数）与估值（mark）必须用同一复权口径**。`us_quality engine.py` 用**未复权 `open`** 算买入股数、却用**复权 `adj_close`** 估值 → 真实数据上 `close` 与 `adj_close` 因累计拆股+分红回调差极大（NVDA close 751 vs adj_close 18.7，~40×）→ 每期持仓系统性错配 → golden 真数据上 us_quality **假亏 −99.4%**（ending 557 / 起始 10 万）。

**★为什么没被早抓到（本批 golden 使命的活教材）：** **合成 fixture 的 `adj_close == close`**（B025 us_quality fixture 全 86790 行 adj==close）→ raw/adj 口径混用在合成数据上**零差异、完全掩盖**。**只有真实复权数据才暴露**——这正是「golden 真数据下沉 CI」要解决的：correctness 高度依赖真实市场数据特性（复权/拆股/停牌）的 bug，合成 fixture 抓不到。

**规约：**
1. 回测引擎执行与估值**用同一复权列**（要么全 raw，要么全 adj）；信号若用 adj（动量需复权），执行/估值也须 adj 对齐，**禁 raw-open 买 + adj-close 估值混用**。
2. **真实数据批次须有 golden 真数据 acceptance**（合成 fixture `adj==close` 会掩盖复权口径 bug）。
3. **§30.1 同族潜伏实例（B071 F003，已裁本批不修）：** records-based 引擎（`monthly.py` / `risk_parity.py`）执行用 raw-open、估值用 raw-close（内部一致），但信号 momentum 用 adj_close → **持有一个拆股个股穿越其拆股月**时 raw-open(拆股前)→raw-close(拆股后)显示假期亏（如 AMZN 2022-06 20:1 拆股）。golden 上 master/momentum/risk_parity 结果合理（±22%，ETF 为主、个股拆股月恰未持有）故**非阻断、本批不修**（用户 2026-06-21 裁定）；记为已知非阻断限制,未来若个股策略持有拆股名穿越拆股月须修。

**来源：** B071 F003 golden 真数据首跑抓到（commit `cb69763` 修 `_wide_open` 用复权 open + 合成 adj==close 向后兼容;**亦影响生产 VM us_quality 回测,已随绿 CI 自动部署**）。同族于 §28（停牌 ffill/NaN，亦"合成数据掩盖真实数据缺陷"）。

## 31. 验收即代码常态化——每批新颖 L2 真实数据检查写成 acceptance 断言（v0.9.49 — B071 F004 沉淀）

**约定：** B071 建了 `tests/acceptance/` 永久不变量回归层（golden 真数据跑）。**每批 Generator/独立 agent 把本批新颖 L2 真实数据检查写成 acceptance 断言**（用 golden 跑），使「一次性 Codex 真机验收」沉淀为**永久 CI 回归**（做一次永远守）。复发不变量（权重和=1 含 cash buffer / 无负现金 / 账户源单一 / N 策略同时段两两不同 / Master 向后兼容 / 防守 shares×市价≈equity）已在 acceptance 层。

**守铁律 4（不削弱独立评审）：** 断言由写码方写，存"测试与 bug 同向错"盲点 → 故 (a) **独立评审面积缩到「新颖/模糊」判断**（机械复发不变量由 CI 绿 by construction）;(b) **F005 mutation-check 对冲**（故意改坏每条不变量 → 对应 acceptance 必须红，证明有牙齿，B071 10/10 mutation 全红）。

**来源：** B071 F004（`tests/acceptance/` 两处 + 6 不变量 + CI step）+ F005 mutation 验收。已记 `docs/dev/workbench-testing-strategy.md`「Acceptance tier」节。配套 evaluator.md §30（verifying 可跳 L1）。

## 32. paper「搁浅现金 / build_complete 永 False」诊断 family——双查证券 mark + 无 mark 的 cash sentinel（v0.9.50 — B074 沉淀）

**坑（§17.1/B058 隐形变体）：** paper 模拟盘建仓失败/搁浅现金可能有**两个独立根因,须都查**：
1. **目标证券缺 mark**：target 持仓在 paper 价格源（`price_snapshot` via `DbPriceProvider`）无 close → skipped → 搁浅现金（B058 regime ETF / B074 #1 A股 价缺）。
2. **目标含无 mark 的 sentinel/现金伪符号**：target 里一行字面 `CASH`（weight>0、无价）被 `compute_rebalance` 计入 `skipped_symbols`,`_apply_rebalance` 的 `fully_built = traded and not skipped` 因 CASH 永为 False → **即便所有真证券 mark 齐,build_complete 也永 False**（B074 #2,planner VM 诊断漏了这条）。

**规约：**
1. **诊断 paper build 失败/搁浅现金,必同时核 (a) 真证券 mark 是否齐 + (b) target 里是否有无 mark 的 sentinel/cash 伪符号被 engine 误判 skipped**。只查 (a) 会漏 (b)。
2. **现金缓冲用实 ETF（SGOV 等,有 mark）优于字面 CASH sentinel**（Master/regime 用 SGOV 故无此坑）;若策略发布字面 CASH,`paper/targets.load_strategy_targets` 须剥离 cash sentinel（`target_key` 保留全目标指纹,只影响发布字面 CASH 的策略=零回归）。
3. **快速锁死**：用 `compute_rebalance` 直接实跑（含/剥 CASH 对照）,立见 skipped 差异。
4. **配套数据侧**：A股/非 Tiingo 价从统一 CSV 同步进 price_snapshot（B074 F001 `cn_snapshot_sync`,不碰 Tiingo/price_universe=零回归）;acceptance 守门「active paper 目标可估价」永久回归（B074 F002,§31 验收即代码）。

**来源：** B074（cn_attack A股 模拟盘双根因:#1 A股 价缺 mark + #2 CASH sentinel→build_complete 永 False;commit `81ee5e9`+`8b7ea21`,Codex L2 验两账户 build_complete=1/25 持仓）。同族 §17.1/§28（合成/默认掩盖真实数据行为）+ B058 F002（price_snapshot 缺目标）。配套 planner.md §「paper build 诊断须查 sentinel」。
