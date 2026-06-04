# [批次名称] Signoff YYYY-MM-DD

> 状态：**待 Evaluator 验收**（progress.json status=verifying）
> 触发：[触发原因一句话]

---

## 变更背景

[描述本批次改动的背景和动机]

---

## 变更功能清单

### F-XXX-01：[功能标题]

**Executor：** generator / codex

**文件：**
- `path/to/file.ts`（新增 / 修改）

**改动：**
[描述具体改动内容]

**验收标准：**
- [可验证的标准1]
- [可验证的标准2]

---

<!-- 重复上面的块，每个功能一块 -->

## 未变更范围

| 事项 | 说明 |
|---|---|
| [未改动模块] | [为什么不改] |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| [指标] | [数值] | [数值] |

---

## 类型检查 / CI

```
[tsc / eslint 执行结果]
[gh run list --limit 1 --branch main 输出]
```

---

## L2 实测记录（v0.9.9 — BL-031 沉淀）

> 本节由 Evaluator 在签收时填写。staging 浏览器 / SSH 实测的具体行为证据，区别于 L1 静态走查。**有 staging 部署的批次必填**；纯文档 / 纯框架批次可写"无 staging 影响 — N/A"。

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | `curl https://staging.kol.guangai.ai/api/health \| jq .git_sha` 输出 = `<sha>` |
| 端到端流验证 | [描述 Reviewer 走完的真实 UX 流：登录 → 操作 → 观察 / 收件箱 / DB 查询结果] |
| 关键 invariant | [如 send test 真发出 + Resend providerMessageId / FK 不撞 / count 验证等] |
| 新增 user-facing 路由真 VM authenticated 200（v0.9.32 — B034 沉淀）| [对每条核心新路由发真 VM authenticated 请求断言 200 + payload 形状，不止 /api/health；带典型 query 触达请求路径真实依赖。若 500 先查请求路径是否依赖 deploy artifact 之外资源（generator.md §12.10）。无新路由写 N/A] |
| 浏览器手动验（如 UI 类）| [DevTools 截图 / 字段渲染 / 网络面板] |

> **RSC server action / 不可 curl-simulate 类 endpoint（v0.9.11 — BL-020-F005 沉淀）：** 走 `Content-Type: text/x-component` + CSRF + RSC payload 的 endpoint（如 login form / OAuth callback / mutation 提交）curl 不能简洁模拟。L2 实测时应明示该限制，退到「unit + integration testcontainer + health endpoint 联合背书 + prod 灰度浏览器手验」模式，物理验证作 Soft-watch 入项目状态由用户驱动，不阻塞 done。

---

## Ops 副作用记录（v0.9.9 — BL-030/BL-031 沉淀）

> 本节记录批次中**任何角色**（Generator / Evaluator / Planner）在 prod / staging 数据库执行的 SQL ops（包括用户授权的越界 ops）。**无 ops 操作时本节可写"本批次无数据库 ops"**。
> 来源：BL-030 Planner SQL ops 漏 dual-write 致 BL-031 暴露 FK orphan 后教训沉淀。

| Agent | 阶段 | 操作摘要 | 副作用对齐 | 用户授权 |
|---|---|---|---|---|
| [Planner/Reviewer/Generator] | [done/verifying/...] | 例：UPDATE asset SET content=... WHERE source='ai_generated' (15 行) | 同 SQL 跑 dualWriteOnUpdate 等价 UPDATE email_template (15 行) ✓ | 用户对话 [时间戳] 授权 |

**Planner done 阶段必查：** Ops 副作用记录中每条是否含"副作用对齐"列且非空？空 = 复查 mutation 函数所有副作用是否同步执行。

---

## Harness 说明

本批改动经 Harness 状态机完整流程（planning → building → verifying → reverifying → done）交付。
`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

---

## Production / HEAD 等价性（v0.9.25 — B022 沉淀）

> 本节由 Evaluator 在签收时填写：对比生产 deployed SHA 与签收时 `main` HEAD SHA。
> 适用对象：任何 cloud-deployed 批次（B021 及以后含 cloud deploy 的批次）。
> 纯本地研究批次（B017/B018/B019 等无 deploy step）本节可写"批次不含 cloud deploy"。

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | [SHA] |
| Main HEAD (`git rev-parse HEAD`) | [SHA] |
| Diff (`git log --oneline <deployed>..HEAD`) | [N commits 或 "0 commits"] |

**等价性判断规则：**

- **同 SHA：** 直接 PASS。
- **不同 SHA**：检查 `git diff <deployed>..HEAD --name-only`：
  - 仅含状态机文件（`progress.json` / `features.json` / `.auto-memory/**` / `docs/test-reports/**-blocker-*.md` 等签收周期产生的元数据） → **接受不同步**，标注"产品代码无漂移"。
  - 含任何 `workbench/**` / `trade/**` / `docs/specs/**` / `docs/prd/**` / framework 类产品/spec 文件 → **必须重新触发 deploy**（push commit 或 manual workflow_dispatch）让 production 与 HEAD 对齐后再签 PASS。

来源：B022 F014 round-4 signoff Codex 模板修订建议（commit `3543abf`）。

---

## Post-signoff Deploy（v0.9.27 — B025 沉淀）

> 本节由 Evaluator 在签收时填写。**签收 commit 本身会推进 `main` 而引入一个新的状态机/元数据 commit**，让 production 自动落后一个 SHA。本段显式记录是否需要 post-signoff 手动 dispatch deploy，避免 v0.9.25 §Production/HEAD 等价性 在下一轮被反复打破。
>
> 适用对象：任何 cloud-deployed 批次（B021 及以后含 cloud deploy 的批次）。
> 纯本地研究 / 纯框架 / 纯文档批次本节可写"批次不含 cloud deploy"。

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff-report only` / `signoff + status machine` / `signoff + product change` |
| Post-signoff dispatch 是否需要 | **是 / 否** |
| Dispatch 命令（若是） | `gh workflow run "<App> Deploy" -r main`（含具体 workflow 名） |
| Workflow run 链接（若是） | `https://github.com/<owner>/<repo>/actions/runs/<id>` |
| Production 最终 SHA = signoff commit SHA | `<sha>`（dispatch deploy 完成后填写） |
| 接受不同步声明（若否） | 如：`本签收 commit 仅含 signoff 报告，未推产品代码；按 v0.9.25 §Production/HEAD 等价性 接受不同步，无需 dispatch。` |

**判断规则（必须二选一）：**

1. **必须 dispatch**：signoff commit 含**任何**会改变 `workbench/**` / `trade/**` / `docs/specs/**` / `framework/**` 之 production runtime behavior 的改动；或者 signoff commit 含 deploy script / Dockerfile / nginx / systemd unit / env 模板等 deploy-impacting 配置改动。
2. **可不 dispatch**：signoff commit 仅含 `progress.json` / `features.json` / `.auto-memory/**` / `docs/test-reports/**` / `docs/screenshots/**` 等纯状态机/证据文件，按 v0.9.25 §Production/HEAD 等价性 接受不同步。

**Evaluator 强制：** 选 "必须 dispatch" 时，必须在 signoff PR / commit 推到 main 后立即执行 `gh workflow run` 并等 deploy run 绿，再把 Production 最终 SHA 填回本段。**不要让 Generator 起新 fix-round 做这件事**——状态机 race 由 Evaluator 闭环。

来源：B025 F006 round-3 / round-4 deploy drift 实战；signoff `docs/test-reports/B025-us-quality-signoff-2026-05-25.md` §Soft-watch S2 + §Framework Learnings 模板修订；配套 `framework/harness/generator.md` §12.7（Generator chore commit 后 dispatch 规约）+ `framework/harness/evaluator.md` §21（Evaluator signoff 模板使用规约）+ `framework/harness/planner.md` §Cloud-deploy spec checklist v0.9.27 扩展。

---

## Decommission Checklist（v0.9.31 — B030 沉淀）

> 本节由 Evaluator 在签收时填写。**适用对象：含 UI feature 退役 / layer 切换 / 组件 decommission 的批次**（如 B030 关 B026 banner / Phase 3 UI 重构旧组件退役 / 切 sleeve / 切 vendor）。非 decommission 批次本节可写 "本批次不含 decommission"。
>
> 仅靠 env flag = false 不够 — 需要 4 处清理（详见 `framework/harness/generator.md` §16 + `framework/harness/evaluator.md` §22）。

| 检查项 | 状态 | 证据 |
|---|---|---|
| (1) 退役组件 import + JSX 已从 layout / page 移除 | **是 / 否 / N/A** | grep `<ComponentName` in `src/app/` → 0 hits |
| (2) i18n messages JSON 中 namespace keys 已删除 | **是 / 否 / N/A** | grep `<namespace>\.` in `messages/{zh-CN,en}.json` → 0 hits |
| (3) 组件文件保留 + decommission notice + 重启路径 | **是 / 否 / N/A** | 文件开头含 `DECOMMISSIONED YYYY-MM-DD by B0XX, see <component>-component.spec.tsx for reactivation` 注释 + hardcoded 双语 + useLocale 替代 useTranslations |
| (4a) 守门测试：`tests/safety/<feature>-decommissioned.spec.ts` 存在 | **是 / 否 / N/A** | 断言 layout 无 import + messages 无 keys |
| (4b) 隔离测试：`tests/unit/<feature>-component.spec.tsx` 存在 | **是 / 否 / N/A** | 组件 isolation 测试验证重启路径仍可用 |
| (4c) Legacy E2E presence → absence 翻转 | **是 / 否 / N/A** | grep 旧 E2E spec 名是否含被退役组件 / feature 名；若有命中必须翻转 |
| Production HTML grep 组件名 / i18n keys 字面值 | **0 hits / N hits** | L2 验证：浏览器拉 protected 页面 HTML grep 0 命中 |

**Evaluator 强制：** 任一 "否" 必须在同 batch 内修（不能留 Soft-watch）。"N/A" 必须说明原因（如 feature 没有 i18n keys）。

**来源：** B030 F004 fix-round 1 banner truly off + legacy E2E presence→absence；signoff `docs/test-reports/B030-real-data-cutover-signoff-2026-05-27.md` §Framework Learnings 模板修订；配套 `framework/harness/generator.md` §16（Generator 四处清理铁律）+ `framework/harness/evaluator.md` §22（E2E 翻转规约）。

---

## Soft-watch（不阻塞 done，需后续跟进）

> 本节由 Evaluator 在签收时填写。低-中风险或边界条件遗留事项列入此处，记录"非 bug 但要记账"的事实。每条声明 ID / 描述 / 风险等级 / 建议处置。
> 无 Soft-watch 项时本节可写"无"但不可删。

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | [描述] | low / medium / high | [建议] |

---

## Framework Learnings

> 本节由 Evaluator 在签收时填写提案，Planner 在 done 阶段消化、与用户确认后写入 `framework/`，并在 `framework/CHANGELOG.md` 追加记录。
> 不紧急的提案应先追加到 `framework/proposed-learnings.md`，由 Planner 在 done 阶段集中处理。
> 无 learnings 时三小节可整体删，但保留本 H2 标题 + 一行"本批次无 framework learnings"。

### 新规律
- [描述：发现了什么新的规律或最佳实践]
  - 来源：[哪个 feature / 哪次故障]
  - 建议写入：`framework/README.md` §经验教训 / `framework/harness/evaluator.md`

### 新坑
- [描述：踩到了什么坑，下次怎么避免]
  - 来源：[哪个 feature / 哪次故障]
  - 建议写入：`framework/README.md` §经验教训

### 模板修订
- [描述：某个模板文件需要补充或修改]
  - 建议修改：`framework/templates/xxx.md` 第 N 行
