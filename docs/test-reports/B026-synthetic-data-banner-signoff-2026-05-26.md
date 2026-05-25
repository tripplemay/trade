# B026-synthetic-data-banner Signoff 2026-05-26

> 状态：**PASS**
> 触发：F002 fix-round-2 后，production dismiss blocker 已解除，B026 最终复验完成

## 变更背景

B026 在 Layer 0 的所有 protected 页面顶部加入 synthetic data 提示 banner，目的是明确告知当前 workbench 仍基于 research prototype / synthetic data，防止用户把页面上的数字误解为真实投资依据。F002 的职责是对 F001 做 L1 + L2 验收，并在 production 交互、错误缓冲和 SHA 等价性满足要求后完成签收。

## 变更功能清单

### F002：Codex L1 + L2 真 VM 验收 + signoff

**Executor：** codex

**文件：**
- `docs/test-reports/B026-synthetic-data-banner-signoff-2026-05-26.md`
- `docs/screenshots/B026-banner/{zh-CN,en}/*.png`
- `progress.json`
- `features.json`
- `.auto-memory/project-status.md`

**改动：**
- 完成 fix-round-2 后的本地 targeted 回归
- 完成 production dismiss focused reverify
- 补充 current-session 生产截图证据
- 产出 signoff 报告并推进状态到 `done`

**验收标准：**
- 本地 banner 相关 smoke 通过
- production 上 banner 可见、点击即隐藏、reload 后重现
- `/api/debug/recent-errors` 为 0
- production SHA 与签收前 `main` HEAD 等价

## 未变更范围

| 事项 | 说明 |
|---|---|
| `trade/**` / `workbench/**` 产品实现代码 | 本轮仅做复验与签收，不修改任何产品实现 |
| backend / trade 业务逻辑 | B026 fix-round-2 只影响前端 banner dismiss 路径 |
| account state / execution 数据 | 本批次未做任何写操作，无需恢复副作用 |

## 类型检查 / CI

```text
Generator fix-round-2（commit d02ad79）已完成完整本地门禁：
- vitest 166 passed
- lint / typecheck / build / npm audit green
- safety regression unchanged
- local prod-mode Playwright b026 6/6 passed

Evaluator 本轮补做 targeted L1：
- git diff --name-only d02ad79..c4221d0
  .auto-memory/project-status.md
  progress.json
- frontend: npm run build -> green
- frontend: npx vitest run tests/unit/synthetic-data-banner.spec.tsx -> 9 passed
- frontend: npx playwright test tests/e2e/b026-synthetic-banner.spec.ts -> 6 passed

结论：d02ad79 之后到签收前 HEAD c4221d0 无产品代码漂移，focused L1 回归足以覆盖 fix-round-2 风险面。
```

## L2 实测记录

| 项 | 证据 |
|---|---|
| Production git_sha == main HEAD | `curl https://trade.guangai.ai/api/health` 在签收前返回 `version=c4221d0afd5a9660ec576075978975ec9195723a`，与当时 `git rev-parse HEAD` 一致 |
| 端到端流验证 | 复用本机已登录的 production Chrome 会话，打开 `https://trade.guangai.ai/strategies`；zh-CN banner 初始可见，点击右上角 `×` 后同页立刻消失，reload 后再次出现 |
| 关键 invariant | 访问 `https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}` |
| 浏览器手动验 | 当前轮 focused 截图已落盘：`docs/screenshots/B026-banner/zh-CN/strategies-before-close.png`、`strategies-after-close.png`、`strategies-after-reload.png`、`recent-errors.png`；既有双语截图保留在 `docs/screenshots/B026-banner/{zh-CN,en}/` |
| 双语 surface 背书 | 上一轮 L2 已确认 zh-CN / en 页面 banner surface 正常；本轮 fix-round-2 后 `d02ad79..c4221d0` 无产品代码差异，因此本轮仅对唯一 blocker（dismiss）做 focused production 回归 |

## Ops 副作用记录

本批次无数据库 ops。

## Harness 说明

本批改动经 Harness 状态机完整流程（building → verifying → fixing/reverifying 多轮循环 → done）交付。
`progress.json` 已设为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

## Production / HEAD 等价性

| 项 | 值 |
|---|---|
| Production version (from `/api/health.version`) | `c4221d0afd5a9660ec576075978975ec9195723a` |
| Main HEAD (`git rev-parse HEAD`) | `c4221d0afd5a9660ec576075978975ec9195723a` |
| Diff (`git log --oneline <deployed>..HEAD`) | `0 commits` |

## Post-signoff Deploy

| 项 | 值 |
|---|---|
| 签收 commit 类型 | `signoff + status machine` |
| Post-signoff dispatch 是否需要 | **否** |
| Dispatch 命令（若是） | `N/A` |
| Workflow run 链接（若是） | `N/A` |
| Production 最终 SHA = signoff commit SHA | `N/A` |
| 接受不同步声明（若否） | `本次签收 commit 仅包含 progress/features 元数据、signoff 报告、project-status 与截图证据，不含任何产品代码或 deploy-impacting 配置；按 v0.9.25 §Production/HEAD 等价性 接受 signoff 后的 metadata-only 不同步，无需 dispatch。` |

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | 当前 production focused L2 依赖本机已有登录态的 Chrome 会话；机器侧没有可直接复用的 `NEXTAUTH_SECRET` 或自动化 token minting 入口 | low | 后续若希望完全脚本化 production L2，可单独沉淀一个经授权的 auth helper 或开启 Chrome Apple Event JS |

## Framework Learnings

本批次无 framework learnings。
