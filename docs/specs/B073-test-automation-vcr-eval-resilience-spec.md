# B073 — 测试自动化基建 Phase 2.1：VCR 录放 + AI Safety Eval 网关韧性 Spec

**批次定位：** 测试自动化路线图 Phase 2.1（B072 延后的 VCR + 本次外部故障暴露的 gate 韧性）。核心动机=**一个外部 LLM 网关宕机（2026-06-21 aigc.guangai.ai 503/429）不应该能拖红 CI / 阻断不相关代码的部署**。两件事：① **VCR 录放** 外部 HTTP 调用 → CI 离线确定性可复现；② **AI Safety Eval 网关韧性** → 区分「网关不可达（基础设施）」vs「advisor 真不安全（安全失败）」，前者不硬阻断部署、后者硬阻断不变。

**来源：** 2026-06-22 用户 B072 done 后选「直接下一批」（采纳 planner 推荐 Phase 2.1）。**触发**:B072 期间 AI Safety Eval 因 LLM 网关 503/429 宕机变红、阻断 deploy gate（F003 时钟与 AI 无关）——活证 Phase 2.1 价值。

---

## 0. ★安全约束（焊死，F002 不可削弱安全门）

- **真安全失败必须仍硬阻断**：网关可达 + advisor 返回不安全内容（收益预测 / 执行指令 / 替代 quant / 越界）→ 红 → 阻断部署，**与现在完全一致,不放松**。
- **只对「网关不可达」放松**：503/429/超时/ConnectError（重试后仍失败）= 基础设施故障,不是安全结论 → 不应红阻断不相关部署。
- **不让未验证的 AI advisor 变更蒙混过关**：若本次变更**触及 AI advisor 逻辑**（llm/advisor 路径）且网关不可达 → 无法验证安全 → **仍须阻断**（或部署等网关恢复）;只有变更**不触及 AI advisor** 时网关不可达才放行（advisor 没变,无需重验）。
- **Codex F003 重点审此约束**：mutation 证明真不安全仍被抓 + 网关不可达不误判为安全 pass（不可达 ≠ 安全）。

---

## 1. 现状（B072 Explore + 本批核）

- **3 httpx loader 都有 `client=` 构造注入 seam**：`tiingo_loader.py:126`、`sec_edgar_loader.py:211`、`llm/gateway.py:182`。无 vcrpy/respx（`pyproject` 无）。akshare/yfinance = lazy module 注入(非 HTTP)。
- **red-team eval = live**：`tests/safety/test_ai_advisor_red_team.py:70 gateway=LLMGateway()` + advisor + Sonnet judge,`skipif(AIGC_GATEWAY_API_KEY 未设)`(`:47`);deploy gate workflow 设 key 跑 live → 网关宕则 httpx 错误冒泡 → 红。dataset-shape guard(`:89`)无 key 也跑。
- **ai-safety-eval.yml**:path-scoped(llm/advisor/red-team/safety-evals);push+PR;是 deploy 链 gate(`workbench-deploy.yml` workflow_run after AI Safety Eval)。

---

## 2. Feature 拆解（3 features：2 generator + 1 codex）

### F001 — VCR 录放外部 HTTP（Tiingo/SEC/LLM gateway）→ CI 离线确定性（executor: generator）

1. 引入 VCR 方案（`vcrpy`/`pytest-recording` 或 `respx`,选一,记 dev-dep）;cassette 目录 `tests/cassettes/`(committed)。
2. 三 httpx loader（Tiingo/SEC/LLM gateway）的真 `httpx.Client` 构造点挂录放 transport;现有 in-process fake 测试保留（VCR 是补充,catches API-shape drift=B031 教训)。
3. akshare/yfinance 走 **frame fixture 录放**（`akshare_frames.frame_records` 抽象录 CSV,非 HTTP)。
4. **CI 离线可复现**：cassette 在,无 key/无网络也跑出确定性结果(标志:CI 不再依赖 live 外部 API)。

**Acceptance：** VCR 方案接入;3 loader cassette 录放;断网/无 key 下 loader 测试用 cassette 跑过(确定性);现有 fake 测试不破。Gates：backend pytest/ruff 目录上下文/mypy CI-exact 0。

### F002 — AI Safety Eval 网关韧性（区分 infra-unreachable vs advisor-unsafe）（executor: generator，触 safety 门）

**两件（守 §0 安全约束）：**
1. **VCR'd 确定性 red-team eval（always-on hard gate）**：录放 gateway 的 advisor+judge 响应 → 常规 CI **离线确定性**跑红队样本 → catches **我方代码**安全回归（advisor prompt / judge 逻辑 / 守门）;不依赖 live 网关 → 外部宕机不影响这道门。**这是新的硬安全门（确定性、always 跑）。**
2. **live red-team eval 韧性（best-effort 补充,catches LLM-side drift）**：保留 live eval(有 key 时),但**区分**：
   - 网关可达 + advisor 不安全 → **红硬阻断**（§0,不变）。
   - 网关不可达（503/429/超时/ConnectError 重试后）→ **skip-with-warning（非红）**,清晰报告「infra-unavailable,安全未验证」;**deploy gate 不因此硬阻断不相关部署**。
   - **但**：若本次变更触及 AI advisor 逻辑(llm/advisor 路径)且 live 不可达 → 仍阻断(无法验证变更安全)。靠 path-scope + 一个「AI advisor 变更时 live eval 必须真跑」断言实现。

**Acceptance（§29 + 安全）：** VCR'd 确定性 eval 在无网关下跑红队样本通过 + mutation(改坏 advisor 安全)→红;live eval 网关不可达→skip-with-warning 非红(模拟 503/429);advisor 不安全→硬红(不变);AI advisor 路径变更+网关不可达→阻断。Gates 同 F001 + safety 守门。

### F003 — Codex 验收 + signoff（executor: codex，安全相邻重点审）（executor: codex）

**安全相邻批次——signoff 含实测证据 + 安全不削弱证明（§29 + §0）：**
- L1 全门禁（verifying 可跳 L1 复跑,B071 §30）。
- **★安全不削弱 mutation 核**：① 改坏 advisor 使其返回不安全内容 → VCR'd eval **必须红**（确定性门有牙齿）;② 模拟网关 503/429 → live eval **skip-with-warning 非红**（韧性生效）;③ 模拟网关可达但 advisor 不安全 → **硬红**（不放松）;④ AI advisor 路径变更 + 网关不可达 → **阻断**（不蒙混）。
- **VCR 离线**：断网/无 key 下 CI 全跑过（cassette 确定性）。
- 零回归;research-only/no-AI 边界;HEAD≡prod。signoff 实测证据逐条 + **明确「安全门未削弱」结论**。

---

## 3. 状态流转 + 不变量

- 混合批次：`planning → building(F001→F002) → verifying(F003) → done`。
- **不变量**：① **安全门不削弱**（真 advisor 不安全仍硬阻断;网关不可达 ≠ 安全 pass）;② 生产/B067/B071/B072 + AI 功能运行时零回归（VCR 仅测试层,生产仍 live 网关 + 优雅降级）;③ research-only / no-AI 预测;④ §12.10.2 / ruff 目录上下文 / mypy CI-exact;⑤ cassette committed 且不含密钥（录放前 scrub API key / token）。
- **诚实边界**：VCR'd eval 测我方代码安全回归(确定性),live eval 测 LLM-side drift(best-effort);两者互补,不互替。F003 mutation 对冲「VCR cassette 录了就过」假绿。
- **后续**：Phase 3（prod synthetic+canary）/ Phase 4（LLM-judge 扩）/ Phase 5（瘦身评审）待按需。
